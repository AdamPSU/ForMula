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

import time
from dataclasses import dataclass
from typing import Any, Literal, TypedDict
from uuid import UUID

import asyncpg
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from ai._timing import log_timing
from ai.judge import ProductJudgment, score_many
from ai.rerank.cohere import ScoredProduct, rerank
from ai.rerank.sql_filter.graph import FilterContext
from ai.rerank.sql_filter.graph import graph as sql_filter_graph
from ai.rerank.sql_filter.log import log_from_state
from profiles.models import HairProfile
from profiles.repository import get_latest_hair_profile

# Cohere's `top_k` and the judge's `judge_top_n` are intentionally the
# same number: every Cohere-surfaced row is judged, no slack tier. Bump
# both together if you ever want a wider tournament.
_TOP_K = 100
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
    sql_started = time.perf_counter()
    try:
        sub = await sql_filter_graph.ainvoke(
            {"user_text": state["user_text"], "attempt": 0},
            context=FilterContext(pool=runtime.context.pool),
        )
    except Exception as exc:
        msg = f"EXEC: {type(exc).__name__}: {exc}"
        log_from_state({"user_text": state["user_text"], "final_error": msg})
        log_timing(
            "filter",
            elapsed_ms=round((time.perf_counter() - sql_started) * 1000, 1),
            final_error=msg,
        )
        return Command(update={"final_error": msg}, goto=END)
    sql_filter_ms = (time.perf_counter() - sql_started) * 1000

    log_from_state(sub)

    if sub.get("final_error"):
        log_timing(
            "filter",
            elapsed_ms=round(sql_filter_ms, 1),
            sql_filter_ms=round(sql_filter_ms, 1),
            final_error=sub["final_error"],
        )
        return Command(update={"final_error": sub["final_error"]}, goto=END)

    rows = sub.get("rows") or []
    products = [dict(r) for r in rows]
    brand_started = time.perf_counter()
    await _hydrate_brand_names(runtime.context.pool, products)
    brand_ms = (time.perf_counter() - brand_started) * 1000
    log_timing(
        "filter",
        elapsed_ms=round(sql_filter_ms + brand_ms, 1),
        sql_filter_ms=round(sql_filter_ms, 1),
        brand_hydration_ms=round(brand_ms, 1),
        attempts=sub.get("attempt"),
        products_count=len(products),
    )
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
    started = time.perf_counter()
    if not state.get("personalize", True):
        log_timing("load_profile", elapsed_ms=0.0, skipped="personalize=false")
        return Command(update={"profile": None}, goto=END)
    async with runtime.context.pool.acquire() as conn:
        profile = await get_latest_hair_profile(conn, state["user_id"])
    log_timing(
        "load_profile",
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        has_profile=profile is not None,
    )
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
    started = time.perf_counter()
    # The chat path stringifies UUIDs upstream so the msgpack checkpointer
    # can serialize products (`ai/chat/graph.py::_msgpack_safe_products`),
    # whereas /recommend hands us native UUIDs straight from asyncpg.
    # `fetch_rerank_docs` uses `WHERE id = ANY($1::uuid[])` and returns
    # UUID-keyed rows, so a str id never matches and every chat call
    # silently returned zero docs. Coerce here so this graph is callable
    # from either path.
    candidate_ids: list[UUID] = [
        p["id"] if isinstance(p["id"], UUID) else UUID(p["id"])
        for p in state["products"]
    ]
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
        log_timing(
            "cohere_rerank",
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            candidates=len(candidate_ids),
            final_error=f"{type(exc).__name__}: {exc}",
        )
        return Command(
            update={"final_error": f"COHERE: {type(exc).__name__}: {exc}"},
            goto=END,
        )

    elapsed_ms = (time.perf_counter() - started) * 1000
    log_timing(
        "cohere_rerank",
        elapsed_ms=round(elapsed_ms, 1),
        candidates=len(candidate_ids),
        scored_count=len(scored),
    )

    if not scored:
        return Command(update={"cohere_scored": []}, goto=END)
    return Command(update={"cohere_scored": scored}, goto="judge")


async def _judge(
    state: RerankState, runtime: Runtime[RecommendContext]
) -> Command[Literal["__end__"]]:
    started = time.perf_counter()
    try:
        judgments, _ = await score_many(
            runtime.context.pool,
            state["profile"],
            state["user_text"],
            state["cohere_scored"],
            judge_top_n=_JUDGE_TOP_N,
        )
    except Exception as exc:
        log_timing(
            "judge",
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            candidates=len(state["cohere_scored"]),
            final_error=f"{type(exc).__name__}: {exc}",
        )
        return Command(
            update={"final_error": f"JUDGE: {type(exc).__name__}: {exc}"},
            goto=END,
        )
    log_timing(
        "judge",
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        candidates=len(state["cohere_scored"]),
        judgments_count=len(judgments),
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
