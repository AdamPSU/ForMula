"""Public `score_many()` orchestration for the tournament reranker.

Contract: the call site (`ai/rerank/graph.py::_judge`) hands us the
DB pool, the user's HairProfile, the user's free-text request, and the
list of Cohere-scored candidates. We:

  1. Slice to top-N (default 100).
  2. Fetch each candidate's `rerank_doc` from `products` in a single
     pooled query, then immediately release the connection — the LLM
     stage holds zero DB resources.
  3. Run R parallel TourRank tournaments (5-stage selection cascades)
     under one global semaphore.
  4. Sum stage-points across tournaments.
  5. Sort descending, breaking ties on Cohere `relevance_score`.
  6. Return `list[ProductJudgment]` + `TournamentMetrics`.

Design notes:
  - Temperature is held at 0 inside each LLM call. Diversity comes from
    per-tournament shuffles with distinct RNG seeds, not sampling noise
    (Shi et al. AACL 2024).
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
from uuid import UUID

import asyncpg

from ai.judge.log import (
    TournamentMetrics,
    _RunAccumulator,
    write_metrics,
)
from ai.judge.models import ProductJudgment
from ai.judge.tournament import (
    CALLS_PER_TOURNAMENT,
    Doc,
    STAGES_PER_TOURNAMENT,
    run_tournaments,
)
from ai.rerank.cohere.models import ScoredProduct
from profiles.models import HairProfile

_DEFAULT_JUDGE_TOP_N = 100
_DEFAULT_R = 10
# Sized to xAI 1800 RPM and matched to the httpx pool in client.py.
# 130 calls/query at R=10 fits in one wave; this gives headroom.
_DEFAULT_CONCURRENCY = 256
_DEFAULT_MAX_ATTEMPTS_PER_CALL = 3


async def _fetch_rerank_docs(
    pool: asyncpg.Pool, ids: list[UUID],
) -> dict[UUID, str]:
    """One-shot fetch of `rerank_doc` for the given IDs.

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
    return {row["id"]: row["rerank_doc"] for row in rows}


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
    return " ".join(parts)


async def score_many(
    pool: asyncpg.Pool,
    profile: HairProfile,
    query: str,
    cohere_scored: list[ScoredProduct],
    *,
    judge_top_n: int = _DEFAULT_JUDGE_TOP_N,
    R: int = _DEFAULT_R,
    concurrency: int = _DEFAULT_CONCURRENCY,
    max_attempts_per_call: int = _DEFAULT_MAX_ATTEMPTS_PER_CALL,
) -> tuple[list[ProductJudgment], TournamentMetrics]:
    """Rerank the Cohere top-N via a TourRank-style tournament.

    Returns `(judgments_sorted_desc, metrics)`. Products without a
    `rerank_doc` in the DB are silently dropped — they cannot be judged
    and the count appears in `metrics.n_products_in vs len(judgments)`.
    """
    top = cohere_scored[:judge_top_n]
    accumulator = _RunAccumulator(
        profile_summary=_profile_summary(profile),
        n_products_in=len(top),
        R=R,
    )
    started = time.perf_counter()

    if not top:
        metrics = accumulator.finalize(
            wall_clock_ms=(time.perf_counter() - started) * 1000,
            score_by_id={}, points_by_id={}, ranked_top_10=[],
        )
        write_metrics(metrics)
        return [], metrics

    candidate_ids = [s.product_id for s in top]
    docs_by_id = await _fetch_rerank_docs(pool, candidate_ids)

    docs: list[Doc] = [
        Doc(product_id=s.product_id, rerank_doc=docs_by_id[s.product_id])
        for s in top
        if s.product_id in docs_by_id
    ]
    if not docs:
        metrics = accumulator.finalize(
            wall_clock_ms=(time.perf_counter() - started) * 1000,
            score_by_id={}, points_by_id={}, ranked_top_10=[],
        )
        write_metrics(metrics)
        return [], metrics

    semaphore = asyncio.Semaphore(concurrency)
    points = await run_tournaments(
        query=query, profile=profile, docs=docs, R=R,
        max_attempts=max_attempts_per_call,
        semaphore=semaphore, accumulator=accumulator,
    )

    max_possible = STAGES_PER_TOURNAMENT * R
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
    # Keep the constants importable by callers / tests.
    _ = CALLS_PER_TOURNAMENT
    return judgments, metrics
