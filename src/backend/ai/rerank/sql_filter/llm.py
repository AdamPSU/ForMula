"""Filter LLM call: free-text shopping intent → validated FilterIntent.

Single xAI Grok call via the OpenAI-compatible AsyncOpenAI client, with
`response_format=json_schema` enforcing the FilterIntent shape. Mirrors
`scraper/tools/filter.py` mechanics. No retries, no tool loop.

Split into `call_llm` (returns raw string) and `parse_intent` so the
caller can capture the raw response for logging even when validation
fails.
"""

from __future__ import annotations

import os
from pathlib import Path

from openai import AsyncOpenAI

from ai.rerank.sql_filter.models import FilterIntent

_MODEL = "grok-4-1-fast-reasoning"
_SYSTEM_PROMPT = (Path(__file__).resolve().parent / "prompts" / "system.txt").read_text()


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
    )


async def call_llm(user_text: str) -> str:
    """Issue the LLM call, return the raw JSON content string."""
    client = _client()
    schema = FilterIntent.model_json_schema()
    resp = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "FilterIntent",
                "schema": schema,
                "strict": True,
            },
        },
    )
    return resp.choices[0].message.content or "{}"


def parse_intent(raw: str) -> FilterIntent:
    """Validate the raw LLM response. Raises pydantic.ValidationError."""
    return FilterIntent.model_validate_json(raw)
