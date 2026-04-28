"""Top-level rerank pipeline graphs.

Three compiled graphs are exported here:

  - `filter_graph`  — sql_filter + load_profile. The "find candidates"
    half of the pipeline. Used by the chat agent to surface results
    BEFORE deciding whether a warning gate fires.
  - `rerank_graph`  — cohere + judge. The "rank candidates" half.
    Called by the chat agent AFTER the user clears the gate.
  - `graph`         — the public `/recommend` pipeline. Composes the
    two halves; preserves the wire shape `ai/rerank/api.py` already
    expects (`reranked` + `judged` flags, top-level error prefixes).

State accumulates progressively. Soft skips (no products, no profile,
empty cohere result) end the pipeline cleanly with stage flags set;
hard failures set `final_error` with a stage-prefixed message
(`AST:` / `EXEC:` propagated from sql_filter, plus `COHERE:` / `JUDGE:`).
The route handler maps the prefix to an HTTP status.

Pool is injected via `Runtime[RecommendContext]` — pools aren't
serializable and shouldn't flow through state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

import asyncpg
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from ai.judge import ProductJudgment, score_many
from ai.rerank.cohere import ScoredProduct, rerank
from ai.rerank.sql_filter.graph import FilterContext
from ai.rerank.sql_filter.graph import graph as sql_filter_graph
from ai.rerank.sql_filter.log import log_from_state
from profiles.models import HairProfile
from profiles.repository import get_latest_hair_profile

_TOP_K = 150
_JUDGE_TOP_N = 100


@dataclass
class RecommendContext:
    pool: asyncpg.Pool


# ---------------------------------------------------------------------------
# filter_graph: sql_filter + profile lookup
# ---------------------------------------------------------------------------


class FilterState(TypedDict, total=False):
    # inputs
    user_text: str
    user_id: str
    personalize: bool

    # outputs
    sql: str | None
    params: list[Any] | None
    products: list[dict]
    surfaced_count: int
    profile: HairProfile | None
    final_error: str | None


async def _hydrate_brand_names(
    pool: asyncpg.Pool, products: list[dict]
) -> None:
    """Mutate `products` in place, adding `brand_name` from a single
    `brands` lookup. Surfaces in the API response so the frontend can
    render the brand under each product without a second round-trip."""
    brand_ids = {p["brand_id"] for p in products if p.get("brand_id")}
    name_by_id: dict[Any, str] = {}
    if brand_ids:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name FROM brands WHERE id = ANY($1::uuid[])",
                list(brand_ids),
            )
        name_by_id = {r["id"]: r["name"] for r in rows}
    for p in products:
        p["brand_name"] = name_by_id.get(p.get("brand_id"))


async def _filter(
    state: FilterState, runtime: Runtime[RecommendContext]
) -> Command[Literal["load_profile", "__end__"]]:
    try:
        sub = await sql_filter_graph.ainvoke(
            {"user_text": state["user_text"], "attempt": 0},
            context=FilterContext(pool=runtime.context.pool),
        )
    except Exception as exc:
        msg = f"EXEC: {type(exc).__name__}: {exc}"
        log_from_state({"user_text": state["user_text"], "final_error": msg})
        return Command(update={"final_error": msg}, goto=END)

    log_from_state(sub)

    if sub.get("final_error"):
        return Command(update={"final_error": sub["final_error"]}, goto=END)

    rows = sub.get("rows") or []
    products = [dict(r) for r in rows]
    await _hydrate_brand_names(runtime.context.pool, products)
    return Command(
        update={
            "sql": sub.get("sql"),
            "params": sub.get("params") or [],
            "products": products,
            "surfaced_count": len(products),
        },
        goto="load_profile",
    )


async def _load_profile(
    state: FilterState, runtime: Runtime[RecommendContext]
) -> Command[Literal["__end__"]]:
    if not state.get("personalize", True):
        return Command(update={"profile": None}, goto=END)
    async with runtime.context.pool.acquire() as conn:
        profile = await get_latest_hair_profile(conn, state["user_id"])
    return Command(update={"profile": profile}, goto=END)


filter_graph = (
    StateGraph(FilterState, context_schema=RecommendContext)
    .add_node("filter", _filter)
    .add_node("load_profile", _load_profile)
    .add_edge(START, "filter")
    .compile()
)


# ---------------------------------------------------------------------------
# rerank_graph: cohere rerank + tournament judge
# ---------------------------------------------------------------------------


class RerankState(TypedDict, total=False):
    # inputs
    user_text: str
    profile: HairProfile
    products: list[dict]

    # outputs
    cohere_scored: list[ScoredProduct]
    judgments: list[ProductJudgment]
    final_error: str | None


async def _cohere_rerank(
    state: RerankState, runtime: Runtime[RecommendContext]
) -> Command[Literal["judge", "__end__"]]:
    candidate_ids = [p["id"] for p in state["products"]]
    try:
        async with runtime.context.pool.acquire() as conn:
            scored = await rerank(
                conn,
                state["profile"],
                state["user_text"],
                candidate_ids,
                top_k=_TOP_K,
            )
    except Exception as exc:
        return Command(
            update={"final_error": f"COHERE: {type(exc).__name__}: {exc}"},
            goto=END,
        )

    if not scored:
        return Command(update={"cohere_scored": []}, goto=END)
    return Command(update={"cohere_scored": scored}, goto="judge")


async def _judge(
    state: RerankState, runtime: Runtime[RecommendContext]
) -> Command[Literal["__end__"]]:
    try:
        judgments, _ = await score_many(
            runtime.context.pool,
            state["profile"],
            state["user_text"],
            state["cohere_scored"],
            judge_top_n=_JUDGE_TOP_N,
        )
    except Exception as exc:
        return Command(
            update={"final_error": f"JUDGE: {type(exc).__name__}: {exc}"},
            goto=END,
        )
    return Command(update={"judgments": judgments}, goto=END)


rerank_graph = (
    StateGraph(RerankState, context_schema=RecommendContext)
    .add_node("cohere_rerank", _cohere_rerank)
    .add_node("judge", _judge)
    .add_edge(START, "cohere_rerank")
    .compile()
)


# ---------------------------------------------------------------------------
# graph: composed /recommend pipeline (wire-compatible with prior shape)
# ---------------------------------------------------------------------------


class RecommendState(TypedDict, total=False):
    # inputs
    user_text: str
    user_id: str
    personalize: bool

    # filter outputs
    sql: str | None
    params: list[Any] | None
    products: list[dict]
    surfaced_count: int
    profile: HairProfile | None

    # rerank outputs
    cohere_scored: list[ScoredProduct]
    judgments: list[ProductJudgment]

    # response flags
    reranked: bool
    judged: bool

    # stage-prefixed message on hard failure
    final_error: str | None


async def _run_filter(
    state: RecommendState, runtime: Runtime[RecommendContext]
) -> Command[Literal["run_rerank", "__end__"]]:
    sub = await filter_graph.ainvoke(
        {
            "user_text": state["user_text"],
            "user_id": state["user_id"],
            "personalize": state.get("personalize", True),
        },
        context=runtime.context,
    )

    update: dict[str, Any] = {
        "sql": sub.get("sql"),
        "params": sub.get("params") or [],
        "products": sub.get("products") or [],
        "surfaced_count": sub.get("surfaced_count", 0),
        "profile": sub.get("profile"),
    }

    if sub.get("final_error"):
        return Command(
            update={**update, "final_error": sub["final_error"]}, goto=END
        )

    products = update["products"]
    profile = sub.get("profile")
    if not products or profile is None:
        # No products surfaced, or unpersonalized / no profile on file —
        # return SQL ordering, skip rerank.
        return Command(update={**update, "reranked": False}, goto=END)
    return Command(update=update, goto="run_rerank")


async def _run_rerank(
    state: RecommendState, runtime: Runtime[RecommendContext]
) -> Command[Literal["__end__"]]:
    sub = await rerank_graph.ainvoke(
        {
            "user_text": state["user_text"],
            "profile": state["profile"],
            "products": state["products"],
        },
        context=runtime.context,
    )
    if sub.get("final_error"):
        return Command(update={"final_error": sub["final_error"]}, goto=END)

    cohere_scored = sub.get("cohere_scored") or []
    judgments = sub.get("judgments") or []
    return Command(
        update={
            "cohere_scored": cohere_scored,
            "judgments": judgments,
            "reranked": True,
            "judged": bool(judgments),
        },
        goto=END,
    )


graph = (
    StateGraph(RecommendState, context_schema=RecommendContext)
    .add_node("run_filter", _run_filter)
    .add_node("run_rerank", _run_rerank)
    .add_edge(START, "run_filter")
    .compile()
)
