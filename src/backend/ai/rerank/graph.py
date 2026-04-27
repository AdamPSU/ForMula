"""Top-level rerank pipeline graph.

Orchestrates the full /recommend flow:

    START → filter → load_profile → cohere_rerank → judge → END
                ↓ no products    ↓ no profile     ↓ no scored   ↓
                └────────────── END (skip downstream stages) ──┘

`filter` invokes the existing sql_filter graph as a subroutine (its
state schema differs from this one; calling `ainvoke` is cleaner than
mapping schemas). Cohere and judge are plain async functions called
from nodes — neither has a multi-step LLM loop that would benefit
from being its own graph.

State accumulates progressively. Soft skips (no products, no profile)
route to END with stage flags set; hard failures set `final_error`
with a stage-prefixed message (`AST:` / `EXEC:` propagated from
sql_filter, plus `COHERE:` / `JUDGE:`). The route handler maps the
prefix to an HTTP status.

Pool is injected via Runtime[RecommendContext] — pools aren't
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

    # profile lookup
    profile: HairProfile | None

    # cohere stage
    cohere_scored: list[ScoredProduct]
    reranked: bool

    # judge stage
    judgments: list[ProductJudgment]
    judged: bool

    # stage-prefixed message on hard failure
    final_error: str | None


@dataclass
class RecommendContext:
    pool: asyncpg.Pool


async def _filter(
    state: RecommendState, runtime: Runtime[RecommendContext]
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
    update: dict[str, Any] = {
        "sql": sub.get("sql"),
        "params": sub.get("params") or [],
        "products": products,
        "surfaced_count": len(products),
    }
    if not products:
        return Command(update={**update, "reranked": False}, goto=END)
    return Command(update=update, goto="load_profile")


async def _load_profile(
    state: RecommendState, runtime: Runtime[RecommendContext]
) -> Command[Literal["cohere_rerank", "__end__"]]:
    if not state.get("personalize", True):
        return Command(update={"profile": None, "reranked": False}, goto=END)

    async with runtime.context.pool.acquire() as conn:
        profile = await get_latest_hair_profile(conn, state["user_id"])

    if profile is None:
        return Command(update={"profile": None, "reranked": False}, goto=END)
    return Command(update={"profile": profile}, goto="cohere_rerank")


async def _cohere_rerank(
    state: RecommendState, runtime: Runtime[RecommendContext]
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
        return Command(
            update={"cohere_scored": [], "reranked": True}, goto=END
        )
    return Command(
        update={"cohere_scored": scored, "reranked": True}, goto="judge"
    )


async def _judge(
    state: RecommendState, runtime: Runtime[RecommendContext]
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

    return Command(
        update={"judgments": judgments, "judged": bool(judgments)},
        goto=END,
    )


graph = (
    StateGraph(RecommendState, context_schema=RecommendContext)
    .add_node("filter", _filter)
    .add_node("load_profile", _load_profile)
    .add_node("cohere_rerank", _cohere_rerank)
    .add_node("judge", _judge)
    .add_edge(START, "filter")
    .compile()
)
