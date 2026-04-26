"""Pydantic shapes for the tournament reranker.

The new architecture is a TourRank-style multi-round selection cascade
(Chen et al., WWW 2025; arXiv:2406.11678) — not a per-product judge.
The result shape is therefore much slimmer than the v2 binary judge:
overall fit collapses to one float (`overall_score` ∈ [0, 1]) plus the
raw integer `tournament_points` that produced it, plus the final rank.

The `summary` field is reserved — it stays empty until / unless we add
a separate one-shot summarization pass over the top-K. The frontend
already handles a missing/empty summary; we ship without one for now.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ProductJudgment(BaseModel):
    """Per-product result of the tournament rerank stage."""

    product_id: UUID
    overall_score: float       # tournament_points / max_possible, ∈ [0, 1]
    tournament_points: int     # raw, ∈ {0..stages_per_tournament * R}
    final_rank: int            # 1-indexed within this /filter call
    summary: str = ""          # reserved; empty until a summarization pass lands
