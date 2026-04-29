"""TourRank-style tournament reranker (Chen et al., WWW 2025).

Core algorithm. Pure-async, no I/O other than the LLM call. The service
layer is responsible for fetching rerank_docs, building Doc records,
finalizing metrics, and producing ProductJudgment results.

Per published Appendix G, candidate sets are reranked by a multi-stage
selection cascade ending in 20→10→5→2, repeated R times in parallel
under one semaphore. Surviving a stage = +1 point; final score = Σ
points across tournaments. The paper finds R=10 saturates returns; we
run R=5 to keep wall-clock and cost down — cuts total LLM calls in
half at the cost of √2x more variance per product score.

The schedule is bucket-driven via `make_schedule(n)`. Buckets cover
N ∈ {2..320}; actual N snaps DOWN to the nearest bucket so the
divisibility invariant g*n == len(survivors) holds at every stage.
Current call-site caps (see `rerank/graph.py`) land us at the 50
bucket in default mode and the 160 bucket in think mode; the larger
200/320 buckets remain in the table for future widening.

Position bias is mitigated via per-tournament shuffles with distinct
RNG seeds (Shi et al. AACL 2024 — repetition + shuffle is the cheapest
effective mitigation). Temperature is held at 0: diversity comes from
the shuffle, not sampling noise.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import openai

from ai._xai import get_xai_client
from ai.judge.log import _LlmUsage
from ai.judge.prompt import build_selection_prompt
from ai.judge.schema import Selection

MODEL_DEFAULT = "grok-4-1-fast-non-reasoning"
# Reasoning variant. In think mode it runs only on endgame stages —
# the schedule entries with g == 1, where the cascade has converged
# to a single group and the actual ordering is decided. Head stages
# (g > 1) stay on MODEL_DEFAULT so wall-clock doesn't blow up; per
# bench, full-cascade reasoning was ~10x slower than non-reasoning.
# `service.py::_stage_models` owns the policy; this module just
# consumes the per-stage tuple it builds.
MODEL_REASONING = "grok-4-1-fast-reasoning"

if TYPE_CHECKING:
    from ai.judge.log import _RunAccumulator
    from profiles.models import HairProfile

_log = logging.getLogger(__name__)

# Per-bucket schedules. Each tuple is `(G, n, m)`: G groups of n docs,
# pick top m from each, survivors = G*m. The endgame 20→10→5→2 is fixed
# across every bucket large enough to reach it. Pick rates and group
# sizes were chosen so each bucket stays inside all-stage pick-rate
# ≥25% with paper-standard n=20.
_BUCKETS: dict[int, tuple[tuple[int, int, int], ...]] = {
    # Tiny buckets — single-stage picks. The chat layer's `surfaced >= 2`
    # guard already caps below this; we still maintain schedules so a
    # confirmed low-count gate runs the tournament instead of crashing.
    2:   ((1, 2, 1),),
    3:   ((1, 3, 2),),
    4:   ((1, 4, 2),),
    # Endgame-only buckets.
    5:   ((1, 5, 2),),
    10:  ((1, 10, 5), (1, 5, 2)),
    20:  ((1, 20, 10), (1, 10, 5), (1, 5, 2)),
    # 1-stage head + endgame.
    40:  ((2, 20, 10), (1, 20, 10), (1, 10, 5), (1, 5, 2)),
    50:  ((5, 10, 4),  (1, 20, 5),  (1, 5, 2)),
    80:  ((4, 20, 5),  (1, 20, 10), (1, 10, 5), (1, 5, 2)),
    # 2-stage head + endgame (K=5).
    100: ((5, 20, 10), (1, 50, 10), (1, 10, 5), (1, 5, 2)),
    160: ((8, 20, 5),  (1, 40, 10), (1, 10, 2)),
    200: ((10, 20, 5), (5, 10, 4),  (1, 20, 10), (1, 10, 5), (1, 5, 2)),
    320: ((16, 20, 5), (4, 20, 5),  (1, 20, 10), (1, 10, 5), (1, 5, 2)),
}

# The bucket table tops out at N=320 (K=5 ceiling under our pick-rate /
# group-size discipline). The current think-mode cap is well below this
# — see `rerank/graph.py::MAX_TOURNAMENT_N_THINKING`. The upper buckets
# stay in the table so the cap can be widened without retuning.
MAX_BUCKET = max(_BUCKETS)


def make_schedule(n: int) -> tuple[tuple[int, int, int], ...]:
    """Return the bucket schedule for `n` candidates.

    Snaps `n` DOWN to the largest hand-tuned bucket ≤ n. Caller is
    expected to truncate the candidate list to the bucket size before
    feeding it through the cascade — `_chunk` will assert otherwise.
    """
    eligible = [b for b in _BUCKETS if b <= n]
    if not eligible:
        raise ValueError(f"need at least 2 docs for a tournament (got {n})")
    return _BUCKETS[max(eligible)]


def calls_per_tournament(schedule: tuple[tuple[int, int, int], ...]) -> int:
    """Total LLM calls one tournament makes across all stages."""
    return sum(g for g, _, _ in schedule)


_TEMPERATURE = 0.0

# Network errors that justify a retry. Auth / quota / invalid-request
# bubble up — those mask config bugs. Rate limits are handled in their
# own branch (see `select_top_m`) so they don't burn the small retry
# budget reserved for transient network/server errors.
_RETRIABLE_NETWORK = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)

# Rate-limit handling. Each 429 is its own retry that does NOT count
# against `max_attempts`; we wait `Retry-After` (when the API surfaces
# it) or exponential backoff capped at 60s, and only give up after a
# very long absolute streak (~1h of waiting). The deterministic
# input-order fallback should not fire because of a transient 429.
_RATE_LIMIT_MAX_RETRIES = 60
_RATE_LIMIT_BASE_WAIT = 5.0
_RATE_LIMIT_MAX_WAIT = 60.0


def _retry_after_seconds(err: openai.RateLimitError) -> float | None:
    """Pull `Retry-After` (seconds form) off a 429 response.

    Returns None when the header is absent or in HTTP-date form; the
    caller falls back to exponential backoff in that case.
    """
    response = getattr(err, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Doc:
    """One candidate carried through the tournament."""

    product_id: UUID
    rerank_doc: str


# --------------------------------------------------------------------
# Selection — one LLM call.
# --------------------------------------------------------------------

def _extract_usage(usage: object | None) -> _LlmUsage:
    """Pull token counts off an OpenAI-SDK usage block, defensively.

    xAI surfaces usage through the standard OpenAI shape;
    `prompt_tokens_details.cached_tokens` is the cache-hit token count
    when the API reports it, otherwise zero. All fields default to
    zero so a missing / malformed usage block can't crash the run.
    """
    if usage is None:
        return _LlmUsage()
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) if details is not None else 0
    return _LlmUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        cached_tokens=cached or 0,
    )


async def _call_llm(
    system: str, user: str, *, model: str, conv_id: str,
) -> tuple[Selection, str, _LlmUsage]:
    """One selection call. Returns (parsed, raw_text, usage).

    `conv_id` becomes the `x-grok-conv-id` header — xAI uses it as a
    sticky-routing key so all calls in the same /filter request land on
    the same server, where the cached system prefix lives. Without it,
    parallel calls scatter across servers and most start cold.

    Raises ValidationError on schema mismatch, openai.* on network /
    429 / 5xx, or other Exception on auth / quota / invalid-request.
    """
    client = get_xai_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=_TEMPERATURE,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "Selection",
                "schema": Selection.model_json_schema(),
                "strict": True,
            },
        },
        extra_headers={"x-grok-conv-id": conv_id},
    )
    raw = resp.choices[0].message.content or "{}"
    usage = _extract_usage(getattr(resp, "usage", None))
    return Selection.model_validate_json(raw), raw, usage


def _clean_int_list(xs: list[int], *, n: int, m: int) -> list[int] | None:
    """Validate one selection list. None on failure.

    Rules: exactly m entries, each in [1, n], no within-list duplicates.
    """
    if len(xs) != m:
        return None
    seen: set[int] = set()
    for x in xs:
        if x < 1 or x > n or x in seen:
            return None
        seen.add(x)
    return list(xs)


def _validate_selection(
    sel: Selection, *, n: int, m: int,
) -> list[int] | None:
    """Return `selected` cleaned, or None if invalid.

    Rules: length=m, ints in [1,n], no within-list duplicates.
    Validation failure flows through the existing `Validation` retry
    branch.
    """
    return _clean_int_list(sel.selected, n=n, m=m)


async def select_top_m(
    *,
    query: str,
    profile: HairProfile,
    group_docs: list[Doc],
    m: int,
    model: str,
    max_attempts: int,
    semaphore: asyncio.Semaphore,
    accumulator: _RunAccumulator,
    tournament_seed: int,
    stage_index: int,
    conv_id: str,
    thinking: bool,
) -> list[Doc]:
    """Run one selection call for one group. Returns m surviving Docs.

    The LLM sees `Document 1..n` labels in the order the caller passed
    them; we map back to UUIDs after parsing. Rate limits (429) are
    handled in their own branch — they wait `Retry-After` (or a long
    exponential backoff) and DO NOT count against `max_attempts`, which
    is reserved for genuine transient failures (timeout / 5xx /
    validation). Only after exhausting `max_attempts` (or
    `_RATE_LIMIT_MAX_RETRIES` of pure 429s) do we fall back to input
    order, with a loud entry in log.txt.
    """
    n = len(group_docs)
    labeled = [(i + 1, d.rerank_doc) for i, d in enumerate(group_docs)]
    system, user = build_selection_prompt(
        query=query, profile=profile, group_docs=labeled, m=m,
        thinking=thinking,
    )

    last_error: str | None = None
    failed_attempts = 0
    rate_limit_hits = 0

    while (
        failed_attempts < max_attempts
        and rate_limit_hits < _RATE_LIMIT_MAX_RETRIES
    ):
        sleep_after: float | None = None  # set inside the semaphore block

        async with semaphore:
            started = time.perf_counter()
            try:
                sel, _raw, usage = await _call_llm(
                    system, user, model=model, conv_id=conv_id,
                )
            except openai.RateLimitError as e:
                duration_ms = (time.perf_counter() - started) * 1000
                rate_limit_hits += 1
                last_error = f"RateLimit: {type(e).__name__}: {e}"
                accumulator.record_call(
                    success=False, error_type="RateLimit",
                    duration_ms=duration_ms, stage_index=stage_index,
                    tournament_seed=tournament_seed,
                )
                retry_after = _retry_after_seconds(e)
                if retry_after is not None:
                    sleep_after = retry_after
                else:
                    sleep_after = min(
                        _RATE_LIMIT_BASE_WAIT * (2 ** (rate_limit_hits - 1)),
                        _RATE_LIMIT_MAX_WAIT,
                    )
            except _RETRIABLE_NETWORK as e:
                duration_ms = (time.perf_counter() - started) * 1000
                failed_attempts += 1
                last_error = f"Network: {type(e).__name__}: {e}"
                accumulator.record_call(
                    success=False, error_type="Network",
                    duration_ms=duration_ms, stage_index=stage_index,
                    tournament_seed=tournament_seed,
                )
                if failed_attempts < max_attempts:
                    sleep_after = min(2 ** (failed_attempts - 1), 4)
            except Exception as e:
                duration_ms = (time.perf_counter() - started) * 1000
                failed_attempts = max_attempts  # short-circuit the loop
                last_error = f"Other: {type(e).__name__}: {e}"
                accumulator.record_call(
                    success=False, error_type="Other",
                    duration_ms=duration_ms, stage_index=stage_index,
                    tournament_seed=tournament_seed,
                )
                # Auth / quota / invalid-request: don't burn more attempts.
                _log.warning(
                    "select_top_m non-retriable failure: %s", last_error
                )
            else:
                duration_ms = (time.perf_counter() - started) * 1000
                cleaned = _validate_selection(sel, n=n, m=m)
                if cleaned is None:
                    failed_attempts += 1
                    last_error = (
                        f"Validation: selected={sel.selected} "
                        f"(expected {m} unique ints in [1,{n}])"
                    )
                    accumulator.record_call(
                        success=False, error_type="Validation",
                        duration_ms=duration_ms, stage_index=stage_index,
                        tournament_seed=tournament_seed,
                    )
                    if failed_attempts < max_attempts:
                        sleep_after = min(2 ** (failed_attempts - 1), 4)
                else:
                    final_picks = cleaned
                    accumulator.record_call(
                        success=True, error_type=None,
                        duration_ms=duration_ms, stage_index=stage_index,
                        tournament_seed=tournament_seed,
                        usage=usage,
                    )
                    return [group_docs[i - 1] for i in final_picks]

        # Sleep OUTSIDE the semaphore so other concurrent calls can
        # progress while this one is waiting for a 429 cooldown.
        if sleep_after is not None:
            await asyncio.sleep(sleep_after)

    # Exhausted retries: deterministic fallback. Loud in log.txt via
    # the recorded failures, never silent.
    accumulator.record_fallback(
        stage_index=stage_index, tournament_seed=tournament_seed,
        reason=last_error or "unknown",
    )
    _log.warning(
        "select_top_m fell back to input order at stage %d (seed %d) "
        "after %d failed attempts and %d rate-limit waits: %s",
        stage_index, tournament_seed,
        failed_attempts, rate_limit_hits, last_error,
    )
    return list(group_docs[:m])


# --------------------------------------------------------------------
# Tournaments.
# --------------------------------------------------------------------

def _chunk(seq: list[Doc], g: int, n: int) -> list[list[Doc]]:
    """Split `seq` into `g` groups of `n` each.

    `len(seq)` must equal `g * n` — invariant of the schedule table.
    """
    assert len(seq) == g * n, (
        f"chunk size mismatch: len={len(seq)} g={g} n={n}"
    )
    return [seq[i * n:(i + 1) * n] for i in range(g)]


async def one_tournament(
    *,
    query: str,
    profile: HairProfile,
    docs: list[Doc],
    schedule: tuple[tuple[int, int, int], ...],
    seed: int,
    models: tuple[str, ...],
    max_attempts: int,
    semaphore: asyncio.Semaphore,
    accumulator: _RunAccumulator,
    conv_id: str,
    thinking: bool,
) -> dict[UUID, int]:
    """Walk the selection cascade once. Returns per-doc points (0..stages).

    `models` is per-stage and must be the same length as `schedule`. This
    is what lets think mode put the reasoning variant on endgame stages
    only — see `service.py::_stage_models`.
    """
    assert len(models) == len(schedule), (
        f"models length {len(models)} != schedule length {len(schedule)}"
    )
    rng = random.Random(seed)
    points: dict[UUID, int] = {d.product_id: 0 for d in docs}
    survivors = list(docs)

    for stage_index, (g, n, m) in enumerate(schedule):
        rng.shuffle(survivors)
        groups = _chunk(survivors, g, n)
        picks = await asyncio.gather(*[
            select_top_m(
                query=query, profile=profile, group_docs=group, m=m,
                model=models[stage_index],
                max_attempts=max_attempts, semaphore=semaphore,
                accumulator=accumulator, tournament_seed=seed,
                stage_index=stage_index, conv_id=conv_id,
                thinking=thinking,
            )
            for group in groups
        ])
        survivors = [d for sub in picks for d in sub]
        for d in survivors:
            points[d.product_id] += 1

    return points


async def run_tournaments(
    *,
    query: str,
    profile: HairProfile,
    docs: list[Doc],
    schedule: tuple[tuple[int, int, int], ...],
    R: int,
    models: tuple[str, ...],
    max_attempts: int,
    semaphore: asyncio.Semaphore,
    accumulator: _RunAccumulator,
    conv_id: str,
    thinking: bool,
) -> dict[UUID, int]:
    """Run R tournaments in parallel and sum points across them.

    `models` is per-stage; see `one_tournament` for shape requirements.
    `conv_id` is shared across every call in the run — it's the
    `x-grok-conv-id` sticky-routing key for xAI's prompt cache.
    """
    rounds = await asyncio.gather(*[
        one_tournament(
            query=query, profile=profile, docs=docs,
            schedule=schedule, seed=r, models=models,
            max_attempts=max_attempts, semaphore=semaphore,
            accumulator=accumulator, conv_id=conv_id,
            thinking=thinking,
        )
        for r in range(R)
    ])
    summed: dict[UUID, int] = {d.product_id: 0 for d in docs}
    for per_round in rounds:
        for pid, pts in per_round.items():
            summed[pid] += pts
    return summed
