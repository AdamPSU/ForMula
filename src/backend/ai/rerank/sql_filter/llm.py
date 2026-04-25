"""Writer LLM call: free-text request → parameterized SQL + params.

Single xAI Grok call via the OpenAI-compatible AsyncOpenAI client, with
`response_format=json_schema` enforcing the `WriterOutput` shape. The
caller (graph.py) is responsible for AST-validating the SQL after this
returns.

If `prior_sql` and `prior_error` are passed, this is a rewrite attempt:
the prior SQL and error are prepended to the user message so the writer
can correct its previous output.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import get_args

from openai import AsyncOpenAI

from ai.rerank.sql_filter.models import WriterOutput
from scraper.validation.models import (
    HairProductCategory,
    HairProductCurrency,
    HairProductSubcategory,
)

_MODEL = "grok-4-1-fast-reasoning"

_PROMPT_TEMPLATE = (
    Path(__file__).resolve().parent / "prompts" / "system.txt"
).read_text()

_SYSTEM_PROMPT = _PROMPT_TEMPLATE.format(
    subcategories=", ".join(get_args(HairProductSubcategory)),
    categories=", ".join(get_args(HairProductCategory)),
    currencies=", ".join(get_args(HairProductCurrency)),
)

_SCHEMA = WriterOutput.model_json_schema()


# Lazy so importing this module without XAI_API_KEY (tests, tooling) doesn't blow up.
@cache
def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
    )


async def call_writer(
    user_text: str,
    prior_sql: str | None,
    prior_error: str | None,
) -> WriterOutput:
    """One LLM call. On rewrite (prior_sql + prior_error both set), the
    user message includes the prior attempt and the verbatim error so
    the writer can fix the specific issue."""
    if prior_sql is not None and prior_error is not None:
        user_msg = (
            f"Your previous attempt was:\n\n{prior_sql}\n\n"
            f"It failed with: {prior_error}\n\n"
            f"Rewrite to fix the specific issue. The user originally "
            f"asked: {user_text}"
        )
    else:
        user_msg = user_text

    resp = await _client().chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "WriterOutput",
                "schema": _SCHEMA,
                "strict": True,
            },
        },
    )
    return WriterOutput.model_validate_json(
        resp.choices[0].message.content or "{}"
    )
