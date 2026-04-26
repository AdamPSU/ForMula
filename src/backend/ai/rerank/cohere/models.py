"""Public types for the cohere reranker."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ScoredProduct(BaseModel):
    """One reranked candidate: product id, Cohere relevance score, rank position."""

    product_id: UUID
    relevance_score: float
    rank: int
