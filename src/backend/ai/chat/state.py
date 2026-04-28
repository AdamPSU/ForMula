"""State + context for the chat graph.

`ChatState` is the persisted-by-checkpointer shape. `messages` is the
only field with a reducer (append-only); everything else is last-write-
wins.

Messages are stored in raw OpenAI Chat Completions format
(`{role, content}`), not LangChain `BaseMessage` objects. The whole
stack — judge, sql_filter writer, chat — calls the OpenAI SDK directly
via `ai/_xai.py`, and pulling LangChain in just for `add_messages`
would add weight without value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

import asyncpg

Phase = Literal[
    "init",
    "awaiting_confirm",
    "rerank_pending",
    "relay",
    "conversing",
    "ended",
]


class ChatMessage(TypedDict, total=False):
    """One OpenAI-style chat message. Plain prose only — the agent has
    no tools, so there are no tool_calls or tool-role messages."""

    role: Literal["system", "user", "assistant"]
    content: str


def _add_messages(
    left: list[ChatMessage] | None,
    right: list[ChatMessage] | ChatMessage | None,
) -> list[ChatMessage]:
    """Append-only reducer. Concurrent updates from sibling nodes merge
    in deterministic order (LangGraph orders updates by node name)."""
    if left is None:
        left = []
    if right is None:
        return left
    if isinstance(right, list):
        return left + right
    return left + [right]


class ChatState(TypedDict, total=False):
    # Inputs
    user_text: str
    user_id: str
    personalize: bool

    # Filter outputs. `profile` is the dumped HairProfile dict — same
    # msgpack-hygiene reasoning as `cohere_scored` / `judgments`.
    # Re-hydrated to a HairProfile when handed to `rerank_graph`.
    sql: str | None
    params: list[Any] | None
    products: list[dict]
    surfaced_count: int
    profile: dict[str, Any] | None

    # Rerank outputs (only populated on the post-confirm path).
    # Stored as plain JSON-compatible dicts (Pydantic `.model_dump(mode="json")`)
    # so the chat checkpointer's msgpack serializer sees only native types —
    # no asyncpg UUIDs, no Pydantic class metadata. Shapes mirror
    # `ScoredProduct` and `ProductJudgment`.
    cohere_scored: list[dict[str, Any]]
    judgments: list[dict[str, Any]]
    reranked: bool
    judged: bool

    # Per-product YAML facets for the top-K judged products. Pulled
    # once at rerank time so the chat agent can reason about *why* a
    # given product ranked where it did without an extra DB hop per
    # turn. Keyed by stringified UUID (msgpack-clean — see comment in
    # `_run_rerank`). Products without a doc are absent.
    top_docs: dict[str, str]

    # Chat surface
    messages: Annotated[list[ChatMessage], _add_messages]

    # Bookkeeping
    phase: Phase
    final_error: str | None


@dataclass
class ChatContext:
    """Non-serializable runtime injection: the asyncpg pool."""

    pool: asyncpg.Pool
