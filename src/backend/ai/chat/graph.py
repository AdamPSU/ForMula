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

import json
import uuid
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from ai._xai import get_xai_client
from ai.chat.log import log_turn
from ai.chat.prompt import build_messages
from ai.chat.state import ChatContext, ChatMessage, ChatState
from ai.chat.tools import tools_for_phase
from ai.rerank.graph import (
    RecommendContext,
    filter_graph,
    rerank_graph,
)

_MODEL = "grok-4-1-fast-non-reasoning"

# Below this count we pause the pipeline and ask the user whether they
# want to refine the prompt or proceed with whatever surfaced. The chat
# surface lives on /results — the gate here is rendered as a static
# warning card on the home page.
_LOW_COUNT_THRESHOLD = 30


# ---------------------------------------------------------------------------
# Helper: one streaming LLM call. Pushes deltas to the SSE writer.
# ---------------------------------------------------------------------------


async def _llm_call(
    state: ChatState,
    *,
    tools: list[dict],
) -> tuple[str, list[dict[str, Any]]]:
    """Run one streaming chat completion. Returns (content, tool_calls)."""
    writer = get_stream_writer()
    messages = build_messages(state)

    kwargs: dict[str, Any] = {
        "model": _MODEL,
        "messages": messages,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    stream = await get_xai_client().chat.completions.create(**kwargs)

    content_parts: list[str] = []
    tool_calls_acc: dict[int, dict[str, Any]] = {}

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if delta.content:
            content_parts.append(delta.content)
            writer({"type": "messages_delta", "content": delta.content})
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                slot = tool_calls_acc.setdefault(
                    idx,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        slot["function"]["arguments"] += tc.function.arguments

    full_content = "".join(content_parts)
    tool_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]

    # Emit one tool_call event per completed call, with parsed args.
    for tc in tool_calls:
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {"_raw": tc["function"]["arguments"]}
        writer({
            "type": "tool_call",
            "id": tc["id"] or str(uuid.uuid4()),
            "name": tc["function"]["name"],
            "arguments": args,
        })

    if full_content:
        writer({"type": "message_complete"})

    return full_content, tool_calls


def _assistant_message(content: str, tool_calls: list[dict]) -> ChatMessage:
    msg: ChatMessage = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


# ---------------------------------------------------------------------------
# Pipeline-driving nodes (no LLM, no interrupt).
# ---------------------------------------------------------------------------


async def _run_filter(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["route_after_filter", "__end__"]]:
    sub = await filter_graph.ainvoke(
        {
            "user_text": state["user_text"],
            "user_id": state["user_id"],
            "personalize": state.get("personalize", True),
        },
        context=RecommendContext(pool=runtime.context.pool),
    )

    update: dict[str, Any] = {
        "sql": sub.get("sql"),
        "params": sub.get("params") or [],
        "products": sub.get("products") or [],
        "surfaced_count": sub.get("surfaced_count", 0),
        "profile": sub.get("profile"),
        # Seed the conversation with the user's original query so the
        # /results chat opens with their prompt as the first bubble.
        "messages": [{"role": "user", "content": state["user_text"]}],
    }

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
    sub = await rerank_graph.ainvoke(
        {
            "user_text": state["user_text"],
            "profile": state["profile"],
            "products": state["products"],
        },
        context=RecommendContext(pool=runtime.context.pool),
    )
    if sub.get("final_error"):
        return Command(
            update={"final_error": sub["final_error"]}, goto=END
        )
    cohere_scored = sub.get("cohere_scored") or []
    judgments = sub.get("judgments") or []
    return Command(
        update={
            "cohere_scored": cohere_scored,
            "judgments": judgments,
            "reranked": True,
            "judged": bool(judgments),
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
    tools = tools_for_phase("relay")
    content, tool_calls = await _llm_call(state, tools=tools)
    log_turn(
        phase="relay",
        user_text=state.get("user_text"),
        pending_warning=None,
        surfaced_count=state.get("surfaced_count"),
        sent_messages=None,
        assistant_content=content,
        tool_calls=tool_calls,
    )
    return Command(
        update={"messages": [_assistant_message(content, tool_calls)]},
        goto="wait",
    )


async def _emit_chat_response(
    state: ChatState, runtime: Runtime[ChatContext]
) -> Command[Literal["wait"]]:
    tools = tools_for_phase("conversing")
    content, tool_calls = await _llm_call(state, tools=tools)
    log_turn(
        phase="conversing",
        user_text=None,
        pending_warning=None,
        surfaced_count=state.get("surfaced_count"),
        sent_messages=None,
        assistant_content=content,
        tool_calls=tool_calls,
    )
    return Command(
        update={"messages": [_assistant_message(content, tool_calls)]},
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
        tool_calls=None,
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
