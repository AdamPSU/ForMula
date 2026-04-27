"""TourRank-style tournament reranker (Chen et al., WWW 2025).

Core algorithm. Pure-async, no I/O other than the LLM call. The service
layer is responsible for fetching rerank_docs, building Doc records,
finalizing metrics, and producing ProductJudgment results.

Per published Appendix G, top-100 is reranked by a 5-stage selection
cascade (100→50→20→10→5→2), repeated R times in parallel under one
semaphore. Surviving a stage = +1 point; final score = Σ points across
tournaments. R=10 saturates returns; we default to that.

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
from ai.judge.prompt import build_selection_prompt
from ai.judge.schema import Selection

MODEL = "grok-4-1-fast-non-reasoning"

if TYPE_CHECKING:
    from ai.judge.log import _RunAccumulator
    from profiles.models import HairProfile

_log = logging.getLogger(__name__)

# Per-stage configuration, verbatim from TourRank Appendix G for N=100.
# (G groups, n per group, m to select from each group). Sum of m * G is
# the number of survivors entering the next stage.
GROUPS: tuple[tuple[int, int, int], ...] = (
    (5, 20, 10),   # 100 → 50
    (5, 10, 4),    # 50 → 20
    (1, 20, 10),   # 20 → 10
    (1, 10, 5),    # 10 → 5
    (1, 5, 2),     # 5 → 2
)
STAGES_PER_TOURNAMENT = len(GROUPS)
CALLS_PER_TOURNAMENT = sum(g for g, _, _ in GROUPS)   # 5+5+1+1+1 = 13

_TEMPERATURE = 0.0

# Network errors that justify a retry. Auth / quota / invalid-request
# bubble up — those mask config bugs.
_RETRIABLE_NETWORK = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


@dataclass(frozen=True)
class Doc:
    """One candidate carried through the tournament."""

    product_id: UUID
    rerank_doc: str


# --------------------------------------------------------------------
# Selection — one LLM call.
# --------------------------------------------------------------------

async def _call_llm(system: str, user: str) -> tuple[Selection, str]:
    """One selection call. Returns (parsed, raw_text).

    Raises ValidationError on schema mismatch, openai.* on network /
    429 / 5xx, or other Exception on auth / quota / invalid-request.
    """
    client = get_xai_client()
    resp = await client.chat.completions.create(
        model=MODEL,
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
    )
    raw = resp.choices[0].message.content or "{}"
    return Selection.model_validate_json(raw), raw


def _validate_selection(
    sel: Selection, *, n: int, m: int,
) -> list[int] | None:
    """Return the cleaned selection list, or None if invalid.

    Validates: exactly m entries, each in [1, n], no duplicates.
    """
    if len(sel.selected) != m:
        return None
    seen: set[int] = set()
    for x in sel.selected:
        if x < 1 or x > n or x in seen:
            return None
        seen.add(x)
    return list(sel.selected)


async def select_top_m(
    *,
    query: str,
    profile: HairProfile,
    group_docs: list[Doc],
    m: int,
    max_attempts: int,
    semaphore: asyncio.Semaphore,
    accumulator: _RunAccumulator,
    tournament_seed: int,
    stage_index: int,
) -> list[Doc]:
    """Run one selection call for one group. Returns m surviving Docs.

    The LLM sees `Document 1..n` labels in the order the caller passed
    them; we map back to UUIDs after parsing. On parse / network
    failure, retry up to `max_attempts`; on exhaustion, fall back to
    the first m docs in input order (deterministic, logged via
    `accumulator.record_call(success=False)` so failures show up in
    log.txt).
    """
    n = len(group_docs)
    labeled = [(i + 1, d.rerank_doc) for i, d in enumerate(group_docs)]
    system, user = build_selection_prompt(
        query=query, profile=profile, group_docs=labeled, m=m,
    )

    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        async with semaphore:
            started = time.perf_counter()
            try:
                sel, _raw = await _call_llm(system, user)
            except _RETRIABLE_NETWORK as e:
                duration_ms = (time.perf_counter() - started) * 1000
                last_error = f"Network: {type(e).__name__}: {e}"
                accumulator.record_call(
                    success=False, error_type="Network",
                    duration_ms=duration_ms, stage_index=stage_index,
                    tournament_seed=tournament_seed,
                )
            except Exception as e:
                duration_ms = (time.perf_counter() - started) * 1000
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
                break
            else:
                duration_ms = (time.perf_counter() - started) * 1000
                cleaned = _validate_selection(sel, n=n, m=m)
                if cleaned is None:
                    last_error = (
                        f"Validation: selected={sel.selected} "
                        f"(expected {m} unique ints in [1,{n}])"
                    )
                    accumulator.record_call(
                        success=False, error_type="Validation",
                        duration_ms=duration_ms, stage_index=stage_index,
                        tournament_seed=tournament_seed,
                    )
                else:
                    accumulator.record_call(
                        success=True, error_type=None,
                        duration_ms=duration_ms, stage_index=stage_index,
                        tournament_seed=tournament_seed,
                    )
                    return [group_docs[i - 1] for i in cleaned]

        if attempt < max_attempts:
            await asyncio.sleep(min(2 ** (attempt - 1), 4))

    # Exhausted retries: deterministic fallback. Loud in log.txt via
    # the recorded failures, never silent.
    accumulator.record_fallback(
        stage_index=stage_index, tournament_seed=tournament_seed,
        reason=last_error or "unknown",
    )
    _log.warning(
        "select_top_m fell back to input order at stage %d (seed %d): %s",
        stage_index, tournament_seed, last_error,
    )
    return list(group_docs[:m])


# --------------------------------------------------------------------
# Tournaments.
# --------------------------------------------------------------------

def _chunk(seq: list[Doc], g: int, n: int) -> list[list[Doc]]:
    """Split `seq` into `g` groups of `n` each.

    `len(seq)` must equal `g * n` — invariant of the GROUPS table.
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
    seed: int,
    max_attempts: int,
    semaphore: asyncio.Semaphore,
    accumulator: _RunAccumulator,
) -> dict[UUID, int]:
    """Walk the 5-stage cascade once. Returns per-doc points (0..stages)."""
    rng = random.Random(seed)
    points: dict[UUID, int] = {d.product_id: 0 for d in docs}
    survivors = list(docs)

    for stage_index, (g, n, m) in enumerate(GROUPS):
        rng.shuffle(survivors)
        groups = _chunk(survivors, g, n)
        picks = await asyncio.gather(*[
            select_top_m(
                query=query, profile=profile, group_docs=group, m=m,
                max_attempts=max_attempts, semaphore=semaphore,
                accumulator=accumulator, tournament_seed=seed,
                stage_index=stage_index,
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
    R: int,
    max_attempts: int,
    semaphore: asyncio.Semaphore,
    accumulator: _RunAccumulator,
) -> dict[UUID, int]:
    """Run R tournaments in parallel and sum points across them."""
    rounds = await asyncio.gather(*[
        one_tournament(
            query=query, profile=profile, docs=docs, seed=r,
            max_attempts=max_attempts, semaphore=semaphore,
            accumulator=accumulator,
        )
        for r in range(R)
    ])
    summed: dict[UUID, int] = {d.product_id: 0 for d in docs}
    for per_round in rounds:
        for pid, pts in per_round.items():
            summed[pid] += pts
    return summed
