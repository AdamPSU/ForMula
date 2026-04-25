"""POST /filter — narrow the product catalog from free-text shopping intent.

Single endpoint, JWT-gated. Orchestrates: LLM call → schema validation →
SQL composition → DB fetch → response. Logs the full pipeline (raw
response, parsed intent, SQL, params, row count, any error) to a
discardable `log.txt` co-located with this module — exactly one entry
per request, success or failure.

The reranker (next milestone) will call `apply_filter` directly rather
than going through this HTTP route.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from ai.rerank.sql_filter.llm import call_llm, parse_intent
from ai.rerank.sql_filter.log import log_call
from ai.rerank.sql_filter.models import FilterIntent, FilterRequest, FilterResponse
from ai.rerank.sql_filter.sql import build_filter_sql
from auth.jwt import get_current_user_id

router = APIRouter(tags=["filter"])


@router.post("/filter")
async def filter_products(
    payload: FilterRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001 — gate only
) -> FilterResponse:
    user_text = payload.text
    raw: str | None = None
    intent: FilterIntent | None = None
    sql: str | None = None
    params: list[Any] | None = None
    rows: list | None = None
    err: str | None = None

    try:
        raw = await call_llm(user_text)
        try:
            intent = parse_intent(raw)
        except ValidationError as exc:
            err = f"ValidationError: {exc}"
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "could not interpret request",
            ) from exc

        sql, params = build_filter_sql(intent)
        pool = request.app.state.pool
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except HTTPException:
        raise
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "filter pipeline failed"
        ) from exc
    finally:
        log_call(
            user_text=user_text,
            raw_response=raw,
            parsed_intent_json=intent.model_dump_json() if intent else None,
            sql=sql,
            params=params,
            row_count=len(rows) if rows is not None else None,
            error=err,
        )

    products = [dict(r) for r in rows or []]
    return FilterResponse(
        intent=intent,  # type: ignore[arg-type]  # success path: intent is set
        products=products,
        count=len(products),
    )
