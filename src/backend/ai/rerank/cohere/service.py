"""Public `rerank()` orchestration.

Pipeline:
    1. Fetch rerank_doc for each candidate id (rows w/o doc are dropped).
    2. Build the Cohere query string from free-text + HairProfile.
    3. Call Cohere Rerank 4 Fast under tenacity retry.
    4. Map response indices back to product ids; emit ScoredProduct[].

The asyncpg connection is passed in — caller owns the pool. No caching.
"""

from __future__ import annotations

import time
from uuid import UUID

import asyncpg
from cohere.errors import (
    GatewayTimeoutError,
    InternalServerError,
    ServiceUnavailableError,
    TooManyRequestsError,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai._timing import log_timing
from ai.rerank.cohere.client import get_client
from ai.rerank.cohere.log import log_call
from ai.rerank.cohere.models import ScoredProduct
from ai.rerank.cohere.query import build_query
from ai.rerank.cohere.repository import fetch_rerank_docs
from profiles.models import HairProfile

_MODEL = "rerank-v4.0-fast"
# Default 4096 truncates the tail of long INCI lists. v4 chunk size is
# 32,764; bump to 16K to give the Ingredients line breathing room.
_MAX_TOKENS_PER_DOC = 16384

_RETRIABLE = (
    TooManyRequestsError,
    InternalServerError,
    ServiceUnavailableError,
    GatewayTimeoutError,
)


async def rerank(
    conn: asyncpg.Connection,
    profile: HairProfile,
    query: str,
    candidate_ids: list[UUID],
    top_k: int = 150,
) -> list[ScoredProduct]:
    if not candidate_ids:
        return []

    docs_by_id = await fetch_rerank_docs(conn, candidate_ids)
    ordered_ids: list[UUID] = [cid for cid in candidate_ids if cid in docs_by_id]
    documents: list[str] = [docs_by_id[cid] for cid in ordered_ids]

    if not documents:
        log_call(
            query=query,
            candidate_count=len(candidate_ids),
            docs_sent=0,
            top_results=[],
            elapsed_ms=0.0,
            error="no candidates had a rerank_doc",
        )
        return []

    cohere_query = build_query(profile, query)
    client = get_client()
    started = time.perf_counter()

    # Per-attempt timing — when the wrapping `node=cohere_rerank` line
    # blows up to 100s+, this is what tells us whether we paid for
    # one slow API call or multiple silent retries on 429/5xx.
    attempt_durations_ms: list[float] = []
    attempt_outcomes: list[str] = []

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            retry=retry_if_exception_type(_RETRIABLE),
            reraise=True,
        ):
            attempt_started = time.perf_counter()
            try:
                with attempt:
                    response = await client.v2.rerank(
                        model=_MODEL,
                        query=cohere_query,
                        documents=documents,
                        top_n=min(top_k, len(documents)),
                        max_tokens_per_doc=_MAX_TOKENS_PER_DOC,
                    )
            except _RETRIABLE as exc:
                attempt_durations_ms.append(
                    round((time.perf_counter() - attempt_started) * 1000, 1)
                )
                attempt_outcomes.append(f"retriable:{type(exc).__name__}")
                raise
            except Exception as exc:
                attempt_durations_ms.append(
                    round((time.perf_counter() - attempt_started) * 1000, 1)
                )
                attempt_outcomes.append(f"fatal:{type(exc).__name__}")
                raise
            else:
                attempt_durations_ms.append(
                    round((time.perf_counter() - attempt_started) * 1000, 1)
                )
                attempt_outcomes.append("ok")
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        log_timing(
            "cohere_api",
            elapsed_ms=round(elapsed_ms, 1),
            attempts=len(attempt_durations_ms),
            attempt_durations_ms=attempt_durations_ms,
            outcomes=attempt_outcomes,
            error=f"{type(exc).__name__}: {exc}",
        )
        log_call(
            query=cohere_query,
            candidate_count=len(candidate_ids),
            docs_sent=len(documents),
            top_results=[],
            elapsed_ms=elapsed_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    log_timing(
        "cohere_api",
        elapsed_ms=round(elapsed_ms, 1),
        attempts=len(attempt_durations_ms),
        attempt_durations_ms=attempt_durations_ms,
        outcomes=attempt_outcomes,
        docs_sent=len(documents),
    )
    scored = [
        ScoredProduct(
            product_id=ordered_ids[result.index],
            relevance_score=result.relevance_score,
            rank=rank,
        )
        for rank, result in enumerate(response.results)
    ]
    log_call(
        query=cohere_query,
        candidate_count=len(candidate_ids),
        docs_sent=len(documents),
        top_results=[(s.product_id, s.relevance_score) for s in scored[:10]],
        elapsed_ms=elapsed_ms,
    )
    return scored
