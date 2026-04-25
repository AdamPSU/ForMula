"""POST /filter — narrow the product catalog from free-text shopping intent.

Single endpoint, JWT-gated. Thin wrapper over the LangGraph workflow in
`graph.py`. Builds initial state, awaits `graph.ainvoke(...)`, writes
one log entry, returns the response (or 422/502 based on
`final_error` prefix).

The reranker (next milestone) will invoke the graph (or its successor)
directly rather than going through this HTTP route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ai.rerank.sql_filter.graph import FilterContext, graph
from ai.rerank.sql_filter.log import log_from_state
from ai.rerank.sql_filter.models import FilterRequest, FilterResponse
from auth.jwt import get_current_user_id

router = APIRouter(tags=["filter"])


@router.post("/filter")
async def filter_products(
    payload: FilterRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),  # noqa: ARG001 — gate only
) -> FilterResponse:
    pool = request.app.state.pool
    try:
        state = await graph.ainvoke(
            {"user_text": payload.text, "attempt": 0},
            context=FilterContext(pool=pool),
        )
    except Exception as exc:
        log_from_state(
            {
                "user_text": payload.text,
                "final_error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "filter pipeline failed"
        ) from exc

    log_from_state(state)

    if state.get("final_error"):
        kind = state["final_error"].split(":", 1)[0]
        if kind == "AST":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "could not interpret request",
            )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "filter pipeline failed"
        )

    rows = state["rows"] or []
    return FilterResponse(
        products=[dict(r) for r in rows],
        count=len(rows),
        sql=state["sql"],
        params=state["params"] or [],
    )
