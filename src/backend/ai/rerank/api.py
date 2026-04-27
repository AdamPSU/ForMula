"""POST /recommend — free-text → SQL candidates → Cohere rerank → judge.

Thin invoker for the rerank pipeline graph. The graph (`ai.rerank.graph`)
owns all branching: empty filter, no profile, Cohere returning nothing,
judge yielding nothing, hard failures. This route only:

  1. Calls `graph.ainvoke` with the request payload.
  2. Maps `final_error` prefix to an HTTP status (`AST:` → 422, anything
     else → 502).
  3. Shapes the final state into `RecommendResponse`.

Stage `log.txt` files are written by the stages themselves; this route
adds no extra logging.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ai.rerank.graph import RecommendContext, RecommendState, graph
from ai.rerank.models import RecommendRequest, RecommendResponse
from auth.jwt import get_current_user_id

router = APIRouter(tags=["recommend"])


@router.post("/recommend")
async def recommend_products(
    payload: RecommendRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> RecommendResponse:
    state = await graph.ainvoke(
        {
            "user_text": payload.text,
            "user_id": user_id,
            "personalize": payload.personalize,
        },
        context=RecommendContext(pool=request.app.state.pool),
    )

    if state.get("final_error"):
        kind = state["final_error"].split(":", 1)[0]
        if kind == "AST":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "could not interpret request",
            )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "recommendation pipeline failed"
        )

    return _build_response(state)


def _build_response(state: RecommendState) -> RecommendResponse:
    products = state.get("products", [])
    surfaced = state.get("surfaced_count", len(products))
    sql = state.get("sql") or ""
    params = state.get("params") or []

    if state.get("judged"):
        by_id = {p["id"]: p for p in products}
        cohere_by_id = {s.product_id: s for s in state.get("cohere_scored", [])}
        ordered: list[dict] = []
        for j in state["judgments"]:
            product = by_id.get(j.product_id)
            if product is None:
                continue
            cohere = cohere_by_id.get(j.product_id)
            ordered.append({
                **product,
                "relevance_score": cohere.relevance_score if cohere else None,
                "rank": cohere.rank if cohere else None,
                "overall_score": j.overall_score,
                "tournament_points": j.tournament_points,
                "final_rank": j.final_rank,
            })
        return RecommendResponse(
            products=ordered,
            count=len(ordered),
            surfaced_count=surfaced,
            sql=sql,
            params=params,
            reranked=True,
            judged=True,
        )

    if state.get("reranked"):
        scored = state.get("cohere_scored", [])
        by_id = {p["id"]: p for p in products}
        ordered = []
        for s in scored:
            product = by_id.get(s.product_id)
            if product is None:
                continue
            ordered.append({
                **product,
                "relevance_score": s.relevance_score,
                "rank": s.rank,
            })
        return RecommendResponse(
            products=ordered,
            count=len(ordered),
            surfaced_count=surfaced,
            sql=sql,
            params=params,
            reranked=True,
            judged=False,
        )

    return RecommendResponse(
        products=products,
        count=len(products),
        surfaced_count=surfaced,
        sql=sql,
        params=params,
        reranked=False,
        judged=False,
    )
