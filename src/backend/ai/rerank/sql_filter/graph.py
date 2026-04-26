"""LangGraph workflow for the writer + AST sql_filter pipeline.

Three nodes with a Command-driven rewrite loop:

    START → write → validate → execute → END
              ↑        ↓ fail      ↓ exec error
              └──── rewrite (≤MAX_ATTEMPTS) ────┘

State carries the last attempt's sql/params/error so the writer can read
them on a rewrite. `final_error` is set only when retries are exhausted;
the API maps its prefix (`AST:` vs `EXEC:`) to a 422 vs 502 response.

The asyncpg pool is injected via Runtime[FilterContext] — pools are not
serializable and shouldn't flow through state.

`RetryPolicy(max_attempts=3)` on `write` handles transient *network*
failures from xAI; that's distinct from the LLM-driven rewrite loop,
which handles content failures (AST rejection, Postgres rejection).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

import asyncpg
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, RetryPolicy

from ai.rerank.sql_filter.llm import call_writer
from ai.rerank.sql_filter.sql import SqlValidationError, ast_validate

MAX_ATTEMPTS = 3


class FilterState(TypedDict, total=False):
    user_text: str
    attempt: int
    sql: str | None
    params: list[Any] | None
    rows: list | None
    error: str | None        # transient between write/validate/execute
    final_error: str | None  # set only when MAX_ATTEMPTS exhausted


@dataclass
class FilterContext:
    pool: asyncpg.Pool


async def _write(state: FilterState) -> dict:
    out = await call_writer(
        state["user_text"],
        prior_sql=state.get("sql"),
        prior_error=state.get("error"),
    )
    return {
        "sql": out.sql,
        "params": out.params,
        "attempt": state.get("attempt", 0) + 1,
        "error": None,
    }


def _validate(
    state: FilterState,
) -> Command[Literal["execute", "write", "__end__"]]:
    try:
        ast_validate(state["sql"] or "")
    except SqlValidationError as e:
        msg = f"AST: {e}"
        if state.get("attempt", 0) >= MAX_ATTEMPTS:
            return Command(update={"final_error": msg}, goto=END)
        return Command(update={"error": msg}, goto="write")
    return Command(goto="execute")


async def _execute(
    state: FilterState, runtime: Runtime[FilterContext]
) -> Command[Literal["__end__", "write"]]:
    sql = state["sql"] or ""
    params = state.get("params") or []
    try:
        async with runtime.context.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except Exception as e:
        msg = f"EXEC: {type(e).__name__}: {e}"
        if state.get("attempt", 0) >= MAX_ATTEMPTS:
            return Command(update={"final_error": msg}, goto=END)
        return Command(update={"error": msg}, goto="write")
    return Command(update={"rows": rows}, goto=END)


graph = (
    StateGraph(FilterState, context_schema=FilterContext)
    .add_node(
        "write",
        _write,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0),
    )
    .add_node("validate", _validate)
    .add_node("execute", _execute)
    .add_edge(START, "write")
    .add_edge("write", "validate")
    .compile()
)
