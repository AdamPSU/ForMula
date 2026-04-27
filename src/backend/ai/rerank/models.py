"""Wire schemas for the /recommend endpoint.

The pipeline graph (`ai.rerank.graph`) consumes `RecommendRequest` and
emits `RecommendResponse` via the route in `ai.rerank.api`. Internal
stage shapes (writer JSON, ScoredProduct, ProductJudgment) live with
their respective stages.
"""

from typing import Any

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    personalize: bool = True


class RecommendResponse(BaseModel):
    products: list[dict]
    count: int
    surfaced_count: int
    sql: str
    params: list[Any]
    reranked: bool
    judged: bool = False
