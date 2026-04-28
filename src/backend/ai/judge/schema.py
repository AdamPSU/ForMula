"""Structured-output schema for the selection LLM call.

The LLM walks a two-step procedure in one structured-output response:
`notes` -> `selected`. The field order is load-bearing: in
autoregressive generation the model commits to each field before the
next, so emitting `notes` first forces reasoning before the ranking is
locked in. Only `selected` is consumed downstream; `notes` exists to
move the model's distribution before it commits.

Naming: `notes` over `initial_reasoning` — the latter cues reasoning
models to keep work in their hidden CoT and emit an empty visible field.

Single static schema — same shape works for every (n, m) selection
call. Length validation on `selected` happens in Python
(`tournament.py::_validate_selection`).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

_NoteStr = Annotated[str, StringConstraints(min_length=1)]


class Selection(BaseModel):
    """One selection-prompt response."""

    model_config = ConfigDict(extra="forbid")

    notes: _NoteStr = Field(
        description=(
            "Work through the candidates against the hair laws and the "
            "user's profile. Surface the ingredient signals that fit or "
            "disqualify each contender, in the form 'Doc K: <ingredient "
            "signal that fits or doesn't fit this user> / <concern or "
            "contraindication if any>'. Cover the strong contenders and "
            "any clear disqualifiers; you don't need to write a line for "
            "every doc. This is your reasoning before commitment — do "
            "not rank yet."
        ),
    )
    selected: list[int] = Field(
        description=(
            "Your top-m in descending fit order. Exactly m unique ints "
            "in [1, n]."
        ),
    )
