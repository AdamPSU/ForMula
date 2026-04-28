"""State + context for the chat graph.

`ChatState` is the persisted-by-checkpointer shape. `messages` is the
only field with a reducer (append-only); everything else is last-write-
wins.

Messages are stored in raw OpenAI Chat Completions format
(`{role, content, tool_calls?, tool_call_id?, name?}`), not LangChain
`BaseMessage` objects. The whole stack — judge, sql_filter writer,
chat — calls the OpenAI SDK directly via `ai/_xai.py`, and pulling
LangChain in just for `add_messages` would add weight without value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

import asyncpg

from ai.judge import ProductJudgment
from ai.rerank.cohere import ScoredProduct
from profiles.models import HairProfile

Phase = Literal[
    "init",
    "awaiting_confirm",
    "rerank_pending",
    "relay",
    "conversing",
    "ended",
]


class ChatMessage(TypedDict, total=False):
    """One OpenAI-style chat message.

    Tool calls live on assistant messages; tool results come back as
    `{role: 'tool', tool_call_id, content}`. We rarely use the tool-
    result form here because all three tools resolve from in-memory
    state (no async DB / external fetch), so the assistant message
    carrying the tool_call IS the rendered card on the frontend — no
    follow-up tool message round-trip is needed.
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    tool_calls: list[dict[str, Any]]
    tool_call_id: str
    name: str


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

    # Filter outputs
    sql: str | None
    params: list[Any] | None
    products: list[dict]
    surfaced_count: int
    profile: HairProfile | None

    # Rerank outputs (only populated on the post-confirm path)
    cohere_scored: list[ScoredProduct]
    judgments: list[ProductJudgment]
    reranked: bool
    judged: bool

    # Chat surface
    messages: Annotated[list[ChatMessage], _add_messages]

    # Bookkeeping
    phase: Phase
    final_error: str | None


@dataclass
class ChatContext:
    """Non-serializable runtime injection: the asyncpg pool."""

    pool: asyncpg.Pool
