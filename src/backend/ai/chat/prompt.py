"""Build the system prompt for one chat turn.

The prompt has three layers, composed per turn:

  1. Persona — `COSMETIC_CHEMIST_IDENTITY` + `INCI_DISCIPLINE` from
     `ai/_persona.py`. Same voice as the tournament judge.
  2. Operating instructions — short, conversation-shaped: be concise,
     prefer specifics over hedges, never speculate about brands, lead
     with the most decision-relevant signal.
  3. Phase-specific guidance + grounding facts — what the agent is
     currently being asked to do and which fields of state matter.

The function returns a list of OpenAI chat messages. The persistent
`messages` channel from `ChatState` is appended after the system
message; the LLM call concatenates `[system] + state["messages"]`.
"""

from __future__ import annotations

from typing import Any

from ai._persona import COSMETIC_CHEMIST_IDENTITY, INCI_DISCIPLINE
from ai.chat.state import ChatState
from profiles.models import HairProfile

_BASE = (
    f"{COSMETIC_CHEMIST_IDENTITY} You are talking to a real user inside the "
    "ForMula app, helping them choose haircare products. You are NOT a "
    "marketing copywriter and NOT a customer-service bot — you are an "
    "expert giving direct, ingredient-grounded advice.\n"
    "\n"
    f"{INCI_DISCIPLINE}\n"
    "\n"
    "Style:\n"
    "- Be concise. Aim for 2-4 sentences per turn unless the user asked "
    "for depth.\n"
    "- Lead with the decision-relevant signal first (\"this won't suit "
    "you because of X\") rather than warming up.\n"
    "- Refer to ingredients by their INCI name when it matters; gloss the "
    "function in plain English alongside.\n"
    "- Never invent product names, brands, or claims the data doesn't "
    "support."
)


def _profile_lines(profile: HairProfile | None) -> str:
    if profile is None:
        return "User has NOT taken the hair-profile quiz. You do not know their hair."
    parts = [
        f"curl_pattern={profile.curl_pattern}",
        f"scalp={profile.scalp_condition}",
        f"density={profile.density}",
        f"thickness={profile.strand_thickness}",
        f"porosity={profile.product_absorption}",
    ]
    if profile.concerns:
        parts.append(f"concerns={','.join(profile.concerns)}")
    parts.append(f"goals={','.join(profile.goals)}")
    return "User HairProfile: " + " ".join(parts)


def _top_judged_summary(state: ChatState, n: int = 10) -> str:
    judgments = state.get("judgments") or []
    products = {p["id"]: p for p in state.get("products") or []}
    if not judgments:
        prods = state.get("products") or []
        if not prods:
            return "No products surfaced."
        lines = ["Top SQL-ordered candidates (no rerank ran):"]
        for i, p in enumerate(prods[:n], start=1):
            lines.append(
                f"  {i}. id={p.get('id')} name={p.get('name')!r} "
                f"sub={p.get('subcategory')!r}"
            )
        return "\n".join(lines)

    lines = [f"Top {min(n, len(judgments))} judged recommendations:"]
    for j in judgments[:n]:
        product = products.get(j.product_id, {})
        lines.append(
            f"  rank={j.final_rank} id={j.product_id} "
            f"name={product.get('name')!r} "
            f"sub={product.get('subcategory')!r} "
            f"score={j.overall_score:.2f} "
            f"pts={j.tournament_points}"
        )
    return "\n".join(lines)


def _phase_block(state: ChatState) -> str:
    phase = state.get("phase", "init")
    user_text = state.get("user_text", "")

    if phase == "relay":
        return (
            "PHASE: relay.\n"
            f"User asked: {user_text!r}.\n"
            "The pipeline has produced their personalized recommendations "
            "(or, if no profile, an SQL-ordered fallback). Write a single "
            "tight paragraph that names the top 1-2 picks and the "
            "ingredient reason each fits the user's hair. Do NOT list the "
            "full ranking — they can see it in the shortlist next to you. "
            "Do NOT emit a tool call here unless the user explicitly "
            "asks for one."
        )

    if phase == "conversing":
        return (
            "PHASE: conversing.\n"
            "Mid-conversation. The user has seen the recommendations and "
            "has a follow-up. Answer it directly. If they ask why a "
            "specific product was ranked where it was, call "
            "`explain_product` with the product_id, plus your sentence-"
            "long axes_summary and 2-3 top_signals. Otherwise, reply in "
            "plain text."
        )

    return f"PHASE: {phase}."


def build_messages(state: ChatState) -> list[dict[str, Any]]:
    """Return the OpenAI messages list for one chat turn."""
    system_parts = [
        _BASE,
        _phase_block(state),
        _profile_lines(state.get("profile")),
        _top_judged_summary(state),
    ]
    system = "\n\n".join(system_parts)
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]

    # Persistent conversation history. Strip None-content tool-call
    # assistant messages of None-content if any sneaked in (defensive).
    for m in state.get("messages") or []:
        msg: dict[str, Any] = {"role": m["role"]}
        if m.get("content") is not None:
            msg["content"] = m["content"]
        if m.get("tool_calls"):
            msg["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"):
            msg["tool_call_id"] = m["tool_call_id"]
        if m.get("name"):
            msg["name"] = m["name"]
        msgs.append(msg)

    return msgs
