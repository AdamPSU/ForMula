"""Public `score_many()` orchestration for the tournament reranker.

Contract: the call site (`ai/rerank/graph.py::_judge`) hands us the
DB pool, the user's HairProfile, the user's free-text request, and the
list of Cohere-scored candidates. We:

  1. Resolve the bucket schedule via `make_schedule(len(cohere_scored))`,
     truncate to the bucket size (snap-down to the largest bucket ≤
     candidate count). The rerank graph caps Cohere's `top_k` upstream
     at 100 — the ceiling of the bucket table.
  2. Fetch each candidate's `rerank_doc` from `products` in a single
     pooled query, then immediately release the connection — the LLM
     stage holds zero DB resources.
  3. Run R parallel TourRank tournaments (selection cascades) under
     one global semaphore.
  4. Sum stage-points across tournaments.
  5. Sort descending, breaking ties on Cohere `relevance_score`.
  6. Return `list[ProductJudgment]` + `TournamentMetrics`.

Design notes:
  - Temperature is held at 0 inside each LLM call. Diversity comes from
    per-tournament shuffles with distinct RNG seeds (Shi et al. AACL 2024).
  - Per-call retry budget is bounded; on full exhaustion the
    `select_top_m` helper falls back to deterministic input order and
    surfaces the failure in `log.txt`. Silent fallbacks would mask
    real upstream issues.
  - The output `overall_score` is `tournament_points / max_possible`,
    which lands in [0, 1] and replaces the v2 binary judge's geometric
    mean. The frontend keeps rendering it as a percentage.
"""

from __future__ import annotations

import asyncio
import time
from uuid import UUID, uuid4

import asyncpg

from ai.judge.log import (
    TournamentMetrics,
    _RunAccumulator,
    write_metrics,
)
from ai.judge.models import ProductJudgment
from ai.judge.prompt import strip_description
from ai.judge.tournament import (
    MODEL_DEFAULT,
    MODEL_REASONING,
    Doc,
    calls_per_tournament,
    make_schedule,
    run_tournaments,
)


# How many trailing stages run on the reasoning model in think mode.
# Reasoning calls sit on the per-tournament critical path (stages are
# strictly sequential within a tournament), so wall-clock scales ~linearly
# with this knob. Each stage demoted off reasoning saves roughly one
# reasoning-call latency from the chain.
#
# K=2 keeps reasoning on the high-leverage cuts (10→5 and 5→2 — where
# the visible leaderboard actually crystallizes) and demotes the 20→10
# "pick top half" cut to the fast model. K=1 would leave reasoning only
# as a final tiebreaker; K=3 was the original setting (full endgame).
THINK_REASONING_TAIL = 2


def _stage_models(
    schedule: tuple[tuple[int, int, int], ...], *, thinking: bool,
) -> tuple[str, ...]:
    """Per-stage model selection.

    Default mode: every stage on MODEL_DEFAULT.
    Think mode: reasoning variant on the last `THINK_REASONING_TAIL`
    stages; head stages stay fast so the per-tournament critical path
    stays bounded. If the schedule is shorter than the tail (tiny
    buckets), every stage gets reasoning — those buckets have so few
    calls that the wall-clock cost is negligible.
    """
    if not thinking:
        return tuple(MODEL_DEFAULT for _ in schedule)
    n_stages = len(schedule)
    tail_start = max(0, n_stages - THINK_REASONING_TAIL)
    return tuple(
        MODEL_REASONING if i >= tail_start else MODEL_DEFAULT
        for i in range(n_stages)
    )
from ai.rerank.cohere.models import ScoredProduct
from profiles.models import HairProfile

_DEFAULT_R = 5
# Sized to xAI 1800 RPM and matched to the httpx pool in client.py.
# The heaviest think-mode bucket (160, 13 calls/tournament × R=5 = 65
# calls) fits in one wave with plenty of headroom.
_DEFAULT_CONCURRENCY = 256
_DEFAULT_MAX_ATTEMPTS_PER_CALL = 3


async def _fetch_rerank_docs(
    pool: asyncpg.Pool, ids: list[UUID],
) -> dict[UUID, str]:
    """One-shot fetch of `rerank_doc` for the given IDs.

    Strips each doc's `Description:` line at fetch time so the per-call
    hot path doesn't redo the work tens of times for the same doc.
    Conn is released before the LLM stage starts so the per-product
    critical section holds no DB resources.
    """
    if not ids:
        return {}
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, rerank_doc FROM products "
            "WHERE id = ANY($1::uuid[]) AND rerank_doc IS NOT NULL",
            ids,
        )
    return {row["id"]: strip_description(row["rerank_doc"]) for row in rows}


def _profile_summary(profile: HairProfile) -> str:
    """Compact one-line profile signature for log lines."""
    parts = [
        f"curl={profile.curl_pattern}",
        f"scalp={profile.scalp_condition}",
        f"density={profile.density}",
        f"thickness={profile.strand_thickness}",
        f"porosity={profile.product_absorption}",
    ]
    if profile.concerns:
        parts.append(f"concerns={','.join(profile.concerns)}")
    parts.append(f"goals={','.join(profile.goals)}")
    if profile.story:
        # Length only — story content is user-written and may carry
        # PII; logging just the length lets log scans tell which runs
        # had a story attached without dumping it.
        parts.append(f"story_len={len(profile.story)}")
    return " ".join(parts)


async def score_many(
    pool: asyncpg.Pool,
    profile: HairProfile,
    query: str,
    cohere_scored: list[ScoredProduct],
    *,
    thinking: bool = False,
    R: int = _DEFAULT_R,
    concurrency: int = _DEFAULT_CONCURRENCY,
    max_attempts_per_call: int = _DEFAULT_MAX_ATTEMPTS_PER_CALL,
) -> tuple[list[ProductJudgment], TournamentMetrics]:
    """Rerank Cohere-scored candidates via a TourRank-style tournament.

    Schedule is selected from the bucket table by the actual length of
    `cohere_scored`; the rerank graph clamps `cohere_scored` to 100
    (the bucket ceiling) before handing it here.

    `thinking=True` widens the candidate cap upstream (set in
    `rerank/graph.py`) AND swaps the LLM to the reasoning Grok variant
    on endgame stages only — head stages stay on the fast variant so
    wall-clock doesn't 10x. See `_stage_models` for the policy.

    Returns `(judgments_sorted_desc, metrics)`. Products without a
    `rerank_doc` in the DB are silently dropped — they cannot be judged
    and the count appears in `metrics.n_products_in vs len(judgments)`.
    """
    # Snap-down to nearest valid bucket. If we have fewer than 2
    # candidates there's nothing to rank, so drop straight through.
    if len(cohere_scored) < 2:
        empty_metrics = _RunAccumulator(
            profile_summary=_profile_summary(profile),
            n_products_in=len(cohere_scored),
            R=R,
            calls_per_tournament=0,
        ).finalize(
            wall_clock_ms=0.0,
            score_by_id={}, points_by_id={}, ranked_top_10=[],
        )
        write_metrics(empty_metrics)
        return [], empty_metrics

    schedule = make_schedule(len(cohere_scored))
    bucket_size = schedule[0][0] * schedule[0][1]
    top = cohere_scored[:bucket_size]

    accumulator = _RunAccumulator(
        profile_summary=_profile_summary(profile),
        n_products_in=len(top),
        R=R,
        calls_per_tournament=calls_per_tournament(schedule),
    )
    started = time.perf_counter()

    candidate_ids = [s.product_id for s in top]
    docs_by_id = await _fetch_rerank_docs(pool, candidate_ids)

    docs: list[Doc] = [
        Doc(product_id=s.product_id, rerank_doc=docs_by_id[s.product_id])
        for s in top
        if s.product_id in docs_by_id
    ]
    # rerank_doc dropouts can knock us off the bucket size — re-resolve
    # the schedule against what we actually have. Loud in log.txt
    # because n_products_in (set above) won't match the new bucket.
    if len(docs) < 2:
        metrics = accumulator.finalize(
            wall_clock_ms=(time.perf_counter() - started) * 1000,
            score_by_id={}, points_by_id={}, ranked_top_10=[],
        )
        write_metrics(metrics)
        return [], metrics
    if len(docs) != bucket_size:
        schedule = make_schedule(len(docs))
        bucket_size = schedule[0][0] * schedule[0][1]
        docs = docs[:bucket_size]
        accumulator.calls_per_tournament = calls_per_tournament(schedule)

    semaphore = asyncio.Semaphore(concurrency)
    models = _stage_models(schedule, thinking=thinking)
    # One conv_id per /filter call. xAI uses `x-grok-conv-id` as a
    # sticky-routing key so every call in this run lands on the same
    # server, where the system-prompt prefix stays cached. Without it,
    # the parallel fan-out scatters across servers and most calls miss.
    conv_id = f"judge-{uuid4()}"
    points = await run_tournaments(
        query=query, profile=profile, docs=docs,
        schedule=schedule, R=R, models=models,
        max_attempts=max_attempts_per_call,
        semaphore=semaphore, accumulator=accumulator,
        conv_id=conv_id,
    )

    max_possible = len(schedule) * R
    score_by_id: dict[UUID, float] = {
        pid: pts / max_possible for pid, pts in points.items()
    }

    cohere_score_by_id = {s.product_id: s.relevance_score for s in top}
    ordered_ids = sorted(
        (d.product_id for d in docs),
        key=lambda pid: (
            -points[pid],
            -cohere_score_by_id.get(pid, 0.0),
        ),
    )

    judgments = [
        ProductJudgment(
            product_id=pid,
            overall_score=score_by_id[pid],
            tournament_points=points[pid],
            final_rank=rank,
        )
        for rank, pid in enumerate(ordered_ids, start=1)
    ]

    metrics = accumulator.finalize(
        wall_clock_ms=(time.perf_counter() - started) * 1000,
        score_by_id=score_by_id,
        points_by_id=points,
        ranked_top_10=ordered_ids[:10],
    )
    write_metrics(metrics)
    return judgments, metrics
