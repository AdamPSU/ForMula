"""Chat agent — outer graph that wraps `/recommend`.

Topology:

    START → run_filter → route_after_filter ─no profile─→ emit_relay → wait → ...
                              │                                ▲
                              │ has profile                    │
                              ▼                                │
                        run_rerank ───────────────────────────┘
                              │
                              ▼
                              END
                              (final_error)

The chat surface only opens *after* the relay lands — the home page
shows a static "takes <30s" notice while the graph runs through
filter (and rerank, when a profile exists). The wait node is the
single pause point for follow-up Q&A on /results.

Streaming: each emit node uses `langgraph.config.get_stream_writer`
to push token deltas + tool-call events to the SSE consumer in
`api.py`.

State persists in `MemorySaver` keyed by `thread_id` (in-memory only;
refresh loses the thread).
"""

from __future__ import annotations

import time
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from ai._timing import log_timing
from ai._xai import get_xai_client
from ai.chat.log import log_turn
from ai.chat.prompt import build_messages
from ai.chat.state import ChatContext, ChatMessage, ChatState
from ai.rerank.cohere.repository import fetch_rerank_docs
from ai.rerank.graph import (
    RecommendContext,
    filter_graph,
    rerank_graph,
)
from profiles.models import HairProfile

# Number of top-ranked products whose `rerank_doc` is hydrated into the
# chat agent's system prompt — and the slice the frontend shortlist
# renders. Keep these aligned: the agent should only be asked to reason
# about products the user can actually see.
_TOP_K_FOR_CHAT = 10

_MODEL = "grok-4-1-fast-non-reasoning"

# Below this count we pause the pipeline and ask the user whether they
# want to refine the prompt or proceed with whatever surfaced. The chat
# surface lives on /results — the gate here is rendered as a static
# warning card on the home page.
_LOW_COUNT_THRESHOLD = 30


# ---------------------------------------------------------------------------
# Helper: one streaming LLM call. Pushes deltas to the SSE writer.
# ---------------------------------------------------------------------------


async def _llm_call(state: ChatState) -> tuple[str, dict[str, float]]:
    """Run one streaming chat completion.

    Returns the full assistant text plus a timing breakdown:
    `prompt_build_ms` (in-process), `ttft_ms` (time to first content
    token from the model — the user-perceived "did it start"), and
    `stream_total_ms` (request through last token). The relay/conversing
    LLM is by far the biggest user-facing latency, so we want the
    breakdown printed at the call site.
    """
    writer = get_stream_writer()
    prompt_started = time.perf_counter()
    messages = build_messages(state)
    prompt_build_ms = (time.perf_counter() - prompt_started) * 1000

    request_started = time.perf_counter()
    stream = await get_xai_client().chat.completions.create(
        model=_MODEL,
        messages=messages,
        stream=True,
    )

    content_parts: list[str] = []
    ttft_ms: float | None = None
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if delta.content:
            if ttft_ms is None:
                ttft_ms = (time.perf_counter() - request_started) * 1000
            content_parts.append(delta.content)
            writer({"type": "messages_delta", "content": delta.content})

    full_content = "".join(content_parts)
    if full_content:
        writer({"type": "message_complete"})
    stream_total_ms = (time.perf_counter() - request_started) * 1000
    return full_content, {
        "prompt_build_ms": prompt_build_ms,
        "ttft_ms": ttft_ms or 0.0,
        "stream_total_ms": stream_total_ms,
    }


def _assistant_message(content: str) -> ChatMessage:
    return {"role": "assistant", "content": content}


# ---------------------------------------------------------------------------
# Pipeline-driving nodes (no LLM, no interrupt).
# ---------------------------------------------------------------------------


_UUID_FIELDS = ("id", "brand_id")


def _msgpack_safe_products(products: list[dict]) -> list[dict]:
    """Stringify asyncpg-native UUID values so the chat checkpointer's
    msgpack serializer doesn't warn (and won't drop neighboring fields
    once strict mode lands). asyncpg returns its own UUID subclass for
    uuid columns; LangGraph's msgpack serde flags it as unregistered."""
    out: list[dict] = []
    for p in products:
        copy = dict(p)
        for f in _UUID_FIELDS:
            v = copy.get(f)
            if v is not None:
                copy[f] = str(v)
        out.append(copy)
    return out


async def _run_filter(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["route_after_filter", "__end__"]]:
    started = time.perf_counter()
    sub = await filter_graph.ainvoke(
        {
            "user_text": state["user_text"],
            "user_id": state["user_id"],
            "personalize": state.get("personalize", True),
        },
        context=RecommendContext(pool=runtime.context.pool),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    profile = sub.get("profile")
    update: dict[str, Any] = {
        "sql": sub.get("sql"),
        "params": sub.get("params") or [],
        "products": _msgpack_safe_products(sub.get("products") or []),
        "surfaced_count": sub.get("surfaced_count", 0),
        # Dump HairProfile to a plain dict — same msgpack hygiene as
        # `cohere_scored` / `judgments`. Re-hydrated when handed to
        # `rerank_graph` in `_run_rerank`.
        "profile": profile.model_dump() if profile else None,
    }
    log_timing(
        "run_filter",
        elapsed_ms=round(elapsed_ms, 1),
        products_count=len(update["products"]),
        has_profile=profile is not None,
        final_error=bool(sub.get("final_error")),
    )

    if sub.get("final_error"):
        # AST refusals + DB errors both surface as terminal final_error;
        # the home page renders them inline and lets the user retype.
        return Command(update={**update, "final_error": sub["final_error"]}, goto=END)

    return Command(update=update, goto="route_after_filter")


def _next_after_gate(state: ChatState) -> Command:
    """Routing once the low-count gate has been cleared (or skipped).
    No profile → emit_relay (no rerank). Has profile → run_rerank."""
    if state.get("profile") is None:
        return Command(update={"phase": "relay"}, goto="emit_relay")
    return Command(update={"phase": "rerank_pending"}, goto="run_rerank")


async def _route_after_filter(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["run_rerank", "emit_relay", "wait"]]:
    """Gate the pipeline if too few products surfaced; otherwise route
    straight to rerank / relay. The gate sits between filter and
    rerank so we don't burn the rerank call on a near-empty shortlist
    without the user's consent."""
    products = state.get("products") or []
    if len(products) < _LOW_COUNT_THRESHOLD:
        return Command(
            update={
                "phase": "awaiting_confirm",
                "surfaced_count": len(products),
            },
            goto="wait",
        )
    return _next_after_gate(state)


async def _run_rerank(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["emit_relay", "__end__"]]:
    node_started = time.perf_counter()
    profile_dict = state.get("profile")
    profile = HairProfile(**profile_dict) if profile_dict else None
    rerank_started = time.perf_counter()
    sub = await rerank_graph.ainvoke(
        {
            "user_text": state["user_text"],
            "profile": profile,
            "products": state["products"],
        },
        context=RecommendContext(pool=runtime.context.pool),
    )
    rerank_ms = (time.perf_counter() - rerank_started) * 1000
    if sub.get("final_error"):
        log_timing(
            "run_rerank",
            elapsed_ms=round((time.perf_counter() - node_started) * 1000, 1),
            rerank_graph_ms=round(rerank_ms, 1),
            final_error=sub.get("final_error"),
        )
        return Command(
            update={"final_error": sub["final_error"]}, goto=END
        )
    # Dump Pydantic models to plain JSON-compatible dicts before they
    # cross the chat checkpointer boundary. `mode="json"` stringifies
    # UUID fields, so the msgpack serializer sees only native types.
    raw_cohere = sub.get("cohere_scored") or []
    raw_judgments = sub.get("judgments") or []
    cohere_scored = [s.model_dump(mode="json") for s in raw_cohere]
    judgments = [j.model_dump(mode="json") for j in raw_judgments]

    # Hydrate rerank_doc for the top-K judged products so the agent has
    # ingredient-level signal to reason about in chat (no per-turn DB
    # hop). Skipped when nothing was judged; the prompt then falls back
    # to the SQL-ordered listing.
    #
    # Keys are stringified UUIDs deliberately. `fetch_rerank_docs`
    # returns asyncpg's UUID subclass, which LangGraph's msgpack
    # checkpoint serializer cannot round-trip — and a single
    # non-serializable field silently torpedoes neighboring booleans
    # like `judged` / `reranked` in the same `Command.update`. Strings
    # are msgpack-trivial, so the whole update lands cleanly.
    top_docs: dict[str, str] = {}
    top_docs_ms = 0.0
    if raw_judgments:
        top_docs_started = time.perf_counter()
        # `fetch_rerank_docs` expects real UUIDs — pull them off the
        # pre-dump Pydantic objects rather than parsing the stringified
        # values back out.
        top_ids = [j.product_id for j in raw_judgments[:_TOP_K_FOR_CHAT]]
        async with runtime.context.pool.acquire() as conn:
            raw_docs = await fetch_rerank_docs(conn, top_ids)
        top_docs = {str(k): v for k, v in raw_docs.items()}
        top_docs_ms = (time.perf_counter() - top_docs_started) * 1000

    log_timing(
        "run_rerank",
        elapsed_ms=round((time.perf_counter() - node_started) * 1000, 1),
        rerank_graph_ms=round(rerank_ms, 1),
        top_docs_fetch_ms=round(top_docs_ms, 1),
        cohere_count=len(cohere_scored),
        judgments_count=len(judgments),
        judged=bool(raw_judgments),
    )

    return Command(
        update={
            "cohere_scored": cohere_scored,
            "judgments": judgments,
            "top_docs": top_docs,
            "reranked": True,
            "judged": bool(raw_judgments),
            "phase": "relay",
        },
        goto="emit_relay",
    )


# ---------------------------------------------------------------------------
# Emit nodes — one LLM call each. Stream deltas via the writer.
# ---------------------------------------------------------------------------


async def _emit_relay(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["wait"]]:
    content, timing = await _llm_call(state)
    log_timing(
        "emit_relay",
        ttft_ms=round(timing["ttft_ms"], 1),
        stream_total_ms=round(timing["stream_total_ms"], 1),
        prompt_build_ms=round(timing["prompt_build_ms"], 1),
        content_chars=len(content),
    )
    log_turn(
        phase="relay",
        user_text=state.get("user_text"),
        pending_warning=None,
        surfaced_count=state.get("surfaced_count"),
        sent_messages=None,
        assistant_content=content,
    )
    return Command(
        update={"messages": [_assistant_message(content)]},
        goto="wait",
    )


async def _emit_chat_response(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["wait"]]:
    content, timing = await _llm_call(state)
    log_timing(
        "emit_chat_response",
        ttft_ms=round(timing["ttft_ms"], 1),
        stream_total_ms=round(timing["stream_total_ms"], 1),
        prompt_build_ms=round(timing["prompt_build_ms"], 1),
        content_chars=len(content),
    )
    log_turn(
        phase="conversing",
        user_text=None,
        pending_warning=None,
        surfaced_count=state.get("surfaced_count"),
        sent_messages=None,
        assistant_content=content,
    )
    return Command(
        update={"messages": [_assistant_message(content)]},
        goto="wait",
    )


# ---------------------------------------------------------------------------
# wait — the single pause point. interrupt() saves state; resume value
# tells us how to advance.
# ---------------------------------------------------------------------------


async def _wait(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[
    Literal["emit_chat_response", "run_rerank", "emit_relay", "__end__"]
]:
    payload = interrupt({
        "type": "interrupt",
        "phase": state.get("phase"),
    })
    payload = payload or {}
    phase = state.get("phase")
    action = payload.get("action")

    log_turn(
        phase=f"wait/{phase}",
        user_text=None,
        pending_warning=None,
        surfaced_count=state.get("surfaced_count"),
        sent_messages=None,
        assistant_content=None,
        resume_value=payload,
    )

    if phase == "awaiting_confirm" and action == "confirm":
        return _next_after_gate(state)

    if phase in ("relay", "conversing"):
        text = (payload.get("text") or "").strip()
        user_msg: ChatMessage = {"role": "user", "content": text or "(empty)"}
        return Command(
            update={"messages": [user_msg], "phase": "conversing"},
            goto="emit_chat_response",
        )

    # Unexpected phase / action — close out.
    return Command(update={"phase": "ended"}, goto=END)


# ---------------------------------------------------------------------------
# Compile.
# ---------------------------------------------------------------------------


graph = (
    StateGraph(ChatState, context_schema=ChatContext)
    .add_node("run_filter", _run_filter)
    .add_node("route_after_filter", _route_after_filter)
    .add_node("run_rerank", _run_rerank)
    .add_node("emit_relay", _emit_relay)
    .add_node("emit_chat_response", _emit_chat_response)
    .add_node("wait", _wait)
    .add_edge(START, "run_filter")
    .compile(checkpointer=MemorySaver())
)
