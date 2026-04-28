"""POST /chat/stream — SSE-streamed chat agent.

Two request shapes:

  - **Initial turn** — body has `user_text` (required) and optional
    `thread_id` (server mints one if absent) + `personalize`. Drives
    the graph from START through filter (+ rerank when a profile
    exists) → relay.
  - **Resume turn** — body has `thread_id` (required) and `resume`
    (payload from the wait node). Continues a paused thread. Resume
    payload: `{"action": "user_message", "text": "..."}`

The response is SSE (`text/event-stream`). Event vocabulary:

    type=thread             {thread_id}
    type=messages_delta     {content}
    type=message_complete   {}
    type=phase              {phase}
    type=interrupt          {phase}
    type=final_error        {error}
    type=done               {}

The frontend `lib/api/chat.ts` knows this vocabulary 1:1.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field

from ai.chat.graph import graph
from ai.chat.state import ChatContext
from auth.jwt import get_current_user_id

router = APIRouter(tags=["chat"])


class ChatStreamRequest(BaseModel):
    user_text: Optional[str] = Field(default=None, max_length=2000)
    thread_id: Optional[str] = None
    personalize: bool = True
    thinking: bool = False
    resume: Optional[dict[str, Any]] = None


def _sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, default=str)}\n\n".encode("utf-8")


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    thread_id = payload.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    ctx = ChatContext(pool=request.app.state.pool)

    if payload.resume is not None:
        graph_input: Any = Command(resume=payload.resume)
    else:
        if not payload.user_text:
            graph_input = None
        else:
            graph_input = {
                "user_text": payload.user_text,
                "user_id": user_id,
                "personalize": payload.personalize,
                "thinking": payload.thinking,
                "phase": "init",
                # Seed the conversation with the user's prompt so it renders
                # as the first bubble. The agent's responses append after.
                "messages": [{"role": "user", "content": payload.user_text}],
            }

    async def gen():
        yield _sse({"type": "thread", "thread_id": thread_id})

        if graph_input is None:
            yield _sse({"type": "final_error", "error": "user_text required for initial turn"})
            yield _sse({"type": "done"})
            return

        last_phase: str | None = None

        try:
            async for mode, data in graph.astream(
                graph_input,
                config=config,
                context=ctx,
                stream_mode=["custom", "updates"],
            ):
                if mode == "custom":
                    # writer(...) payloads from emit_* nodes — pass through.
                    yield _sse(data)
                    continue

                # mode == "updates": {node_name: state_update}
                if not isinstance(data, dict):
                    continue
                for node_name, update in data.items():
                    if node_name == "__interrupt__":
                        # update is a tuple of Interrupt objects.
                        for intr in update:
                            yield _sse({
                                "type": "interrupt",
                                **(intr.value if isinstance(intr.value, dict) else {"value": intr.value}),
                            })
                        continue
                    if not isinstance(update, dict):
                        continue
                    new_phase = update.get("phase")
                    if new_phase and new_phase != last_phase:
                        last_phase = new_phase
                        evt: dict[str, Any] = {"type": "phase", "phase": new_phase}
                        # Forward surfaced_count whenever the node sets
                        # it on the same update — used by the home page's
                        # low-count warning to render the actual number.
                        if "surfaced_count" in update:
                            evt["surfaced_count"] = update["surfaced_count"]
                        yield _sse(evt)
                    if update.get("final_error"):
                        yield _sse({
                            "type": "final_error",
                            "error": update["final_error"],
                        })
        except Exception as exc:
            yield _sse({
                "type": "final_error",
                "error": f"{type(exc).__name__}: {exc}",
            })

        yield _sse({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/state/{thread_id}")
async def chat_state(
    thread_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Return the current persisted state of a thread.

    Used by the page-2 chat panel on initial mount: it picks up the
    thread that was started on page 1 and renders the messages already
    accumulated. JWT-gated; no cross-user access (we don't yet store
    user_id with the checkpoint, so a guessed thread_id WILL leak —
    threads are uuid4 so guessing is impractical, but if this becomes
    a public concern, store user_id alongside in state and check it
    here).
    """
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    values = snapshot.values or {}
    products = values.get("products") or []
    judgments = values.get("judgments") or []
    cohere_scored = values.get("cohere_scored") or []

    # Products carry stringified UUIDs (see `_msgpack_safe_products`),
    # and judgments / cohere_scored are plain dicts dumped from Pydantic
    # with `mode="json"` — so every product_id lookup here is a string.
    by_id = {p["id"]: p for p in products}
    cohere_by_id = {s["product_id"]: s for s in cohere_scored}

    # Single source of truth for shortlist ordering: the judge
    # tournament. If judgments aren't populated (no profile, gate
    # skipped, or judge produced nothing) we return raw SQL order —
    # never Cohere order. Showing Cohere here would silently
    # contradict the LLM's recommendations, which read from
    # `judgments` exclusively.
    if values.get("judged"):
        ordered = []
        for j in judgments:
            pid = j["product_id"]
            product = by_id.get(pid)
            if product is None:
                continue
            cohere = cohere_by_id.get(pid)
            ordered.append({
                **product,
                "relevance_score": cohere["relevance_score"] if cohere else None,
                "rank": cohere["rank"] if cohere else None,
                "overall_score": j["overall_score"],
                "tournament_points": j["tournament_points"],
                "final_rank": j["final_rank"],
            })
        result_products = ordered
    else:
        result_products = products

    return {
        "thread_id": thread_id,
        "phase": values.get("phase"),
        "messages": values.get("messages") or [],
        "products": result_products,
        "surfaced_count": values.get("surfaced_count", 0),
        "reranked": bool(values.get("reranked")),
        "judged": bool(values.get("judged")),
        "final_error": values.get("final_error"),
    }
