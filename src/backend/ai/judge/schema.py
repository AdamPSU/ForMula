"""Structured-output schema for the selection LLM call.

The LLM is asked: 'select the m most relevant of these n shuffled
documents.' We enforce a closed JSON shape via the OpenAI response_format
JSON-schema mechanism, then validate length and index range in the
caller (see `tournament.py::select_top_m`).

Single static schema — no dynamic construction is needed since the same
shape works for every (n, m) selection call.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Selection(BaseModel):
    """One selection-prompt response.

    `selected` is the list of 1-indexed document labels chosen, in
    descending order of fit. The caller validates:
      - len(selected) == m
      - every value ∈ [1, n_in_group]
      - no duplicates
    """

    model_config = ConfigDict(extra="forbid")

    selected: list[int] = Field(
        description=(
            "1-indexed document labels chosen, in descending order of fit. "
            "Must contain exactly m entries, each in the range [1, n]."
        ),
    )
