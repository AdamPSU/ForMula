"""Pydantic schemas for the writer LLM and the /filter API.

The writer emits `WriterOutput`: a parameterized SQL string + a list of
parameters. Safety is enforced by `sql.ast_validate` against this output,
not by a clause-level allowlist (that was v1/v2). The schema here only
constrains the wire shape.
"""

from typing import Any

from pydantic import BaseModel, Field


class WriterOutput(BaseModel):
    """Raw output from the writer LLM."""

    sql: str = Field(min_length=1)
    params: list[Any] = Field(default_factory=list)


class FilterRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class FilterResponse(BaseModel):
    products: list[dict]
    count: int
    sql: str
    params: list[Any]
