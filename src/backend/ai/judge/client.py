"""Lazy module-singleton AsyncOpenAI client for xAI Grok.

Mirrors the `@cache`-decorated factory pattern from
`ai/rerank/sql_filter/llm.py`. Same env var, same model family, same
base URL; the judge just uses different prompts and a different output
schema.

We override the default httpx connection pool. The reasoning model
takes ~25–30s per call, so a 300-call burst (top-100 × N=3) wants to
fan out wide — but httpx defaults to `max_connections=100`, which
would silently cap parallelism regardless of the asyncio.Semaphore
size in service.py. xAI's documented rate limit is 1800 RPM = 30 RPS,
and a single in-flight burst of 256 is well under that ceiling, so
matching the connection pool to the semaphore is safe.
"""

from __future__ import annotations

import os
from functools import cache

import httpx
from openai import AsyncOpenAI

MODEL = "grok-4-1-fast-non-reasoning"
MAX_CONCURRENT_CONNECTIONS = 256


@cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
        http_client=httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=MAX_CONCURRENT_CONNECTIONS,
                max_keepalive_connections=MAX_CONCURRENT_CONNECTIONS,
            ),
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        ),
    )
