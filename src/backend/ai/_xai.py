"""Shared AsyncOpenAI client for xAI Grok.

One process-wide singleton, reused by every module that talks to xAI
(today: the SQL writer in `ai/rerank/sql_filter/llm.py` and the
tournament judge in `ai/judge/tournament.py`). `@cache` on the factory
means the underlying httpx pool is shared across callers.

Pool sizing: the judge fans 256 LLM calls in parallel (sized to xAI's
1800 RPM ceiling and matched to its asyncio.Semaphore in
`judge/service.py`). httpx defaults to `max_connections=100`, which
would silently cap parallelism below the semaphore. We raise the pool
to 256 so the throttle is the semaphore, not the connection pool. The
writer is a single in-flight call per request and is happy under the
same ceiling.

Read timeout is generous (120s) because the reasoning model takes
~25–30s per call.
"""

from __future__ import annotations

import os
from functools import cache

import httpx
from openai import AsyncOpenAI

_BASE_URL = "https://api.x.ai/v1"
_MAX_CONNECTIONS = 256


@cache
def get_xai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url=_BASE_URL,
        http_client=httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=_MAX_CONNECTIONS,
                max_keepalive_connections=_MAX_CONNECTIONS,
            ),
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        ),
    )
