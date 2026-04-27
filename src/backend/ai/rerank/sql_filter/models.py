"""Writer-LLM wire schema.

`WriterOutput` constrains what the writer LLM is allowed to emit
(parameterized SQL + parameter list). Safety is enforced post-hoc by
`sql.ast_validate`, not by clause-level allowlisting in this schema.
The pipeline-level request/response models live in `ai.rerank.models`.
"""

from typing import Any

from pydantic import BaseModel, Field


class WriterOutput(BaseModel):
    """Raw output from the writer LLM."""

    sql: str = Field(min_length=1)
    params: list[Any] = Field(default_factory=list)
