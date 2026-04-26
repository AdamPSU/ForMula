"""POST /filter — free-text → SQL candidates → Cohere rerank → ordered list.

Single endpoint, JWT-gated. Two stages:

1. `sql_filter` LangGraph (writer LLM → AST validate → execute) narrows
   ~5,000 → ~150–2,000 candidates.
2. If the user has a HairProfile, `cohere.rerank` reorders the
   candidates by ingredient fit. Without a profile, candidates are
   returned in their original SQL order with `reranked=False`.

Cohere failure surfaces as 502 (loud, not silent) so users never get
mis-ranked results without knowing. Reranked rows carry
`relevance_score` and `rank` fields; unreranked rows do not.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ai.rerank.cohere import rerank
from ai.rerank.sql_filter.graph import FilterContext, graph
from ai.rerank.sql_filter.log import log_from_state
from ai.rerank.sql_filter.models import FilterRequest, FilterResponse
from auth.jwt import get_current_user_id
from profiles.repository import get_latest_hair_profile

router = APIRouter(tags=["filter"])

_TOP_K = 150


@router.post("/filter")
async def filter_products(
    payload: FilterRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
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
    products: list[dict] = [dict(r) for r in rows]

    if not products:
        return FilterResponse(
            products=[], count=0, sql=state["sql"],
            params=state["params"] or [], reranked=False,
        )

    async with pool.acquire() as conn:
        profile = await get_latest_hair_profile(conn, user_id)
        if profile is None:
            return FilterResponse(
                products=products, count=len(products),
                sql=state["sql"], params=state["params"] or [],
                reranked=False,
            )

        candidate_ids: list[UUID] = [p["id"] for p in products]
        try:
            scored = await rerank(
                conn, profile, payload.text, candidate_ids, top_k=_TOP_K
            )
        except Exception as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "rerank failed"
            ) from exc

    by_id = {p["id"]: p for p in products}
    ordered: list[dict] = []
    for s in scored:
        product = by_id.get(s.product_id)
        if product is None:
            continue
        ordered.append(
            {**product, "relevance_score": s.relevance_score, "rank": s.rank}
        )

    return FilterResponse(
        products=ordered,
        count=len(ordered),
        sql=state["sql"],
        params=state["params"] or [],
        reranked=True,
    )
