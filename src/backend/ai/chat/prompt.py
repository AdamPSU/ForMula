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

_BASE = (
    f"{COSMETIC_CHEMIST_IDENTITY} You are chatting 1:1 with a real user "
    "inside the ForMula app. Think of yourself as their knowledgeable "
    "derm-style friend who happens to read INCI labels for a living: "
    "warm, direct, advisory. Not a marketing copywriter, not a "
    "customer-service bot, not a textbook.\n"
    "\n"
    f"{INCI_DISCIPLINE}\n"
    "\n"
    "Voice and length:\n"
    "- Default reply is 1-2 short sentences. Name the top pick, give one "
    "plain-English reason it fits this user. Don't restate the full "
    "ranking. The shortlist UI sits right next to you.\n"
    "- Sound like a person, not a product page. Use natural advisory "
    "openers (\"I'd reach for…\", \"Looks like…\", \"Honestly, …\", \"**X** "
    "is your best bet for that\") instead of clinical \"X is your top "
    "pick\" phrasings. Contractions are fine; talk to them.\n"
    "- End with a light, optional follow-up question or nudge when it "
    "feels natural, e.g. \"want me to break down why?\", \"curious about "
    "the runner-up?\", \"how does that sound?\", \"anything else you want "
    "to factor in (price, scent, etc.)?\". One nudge max, only when it "
    "actually opens a useful next step. Skip it if the user already asked "
    "something tightly scoped. Don't tack on filler.\n"
    "- Only expand into a longer reply when the user explicitly asks for "
    "more (\"why\", \"tell me more\", \"compare them\", \"deeper dive\"). "
    "Then you can go longer and bring in INCI specifics.\n"
    "- Lead with the recommendation, not the rationale. Skip warm-ups "
    "like \"Great question!\" or \"Based on your profile…\".\n"
    "- No em dashes (—). They're a giveaway you sound AI-written. Use "
    "commas, periods, parentheses, or just two short sentences instead. "
    "Hyphens in compound words (humidity-resistant, leave-in) are fine.\n"
    "\n"
    "Plain English first:\n"
    "- Translate INCI to what it does for the user. Say \"glycerin and "
    "squalane lock in moisture\", not \"behentrimonium chloride and "
    "polyquaternium-10 provide film-forming hold\".\n"
    "- Mention an INCI name only when the user asked about ingredients "
    "or you need to disambiguate; put it in parentheses, e.g. \"a humectant "
    "(glycerin)\". Never stack 3+ INCI names in one sentence.\n"
    "\n"
    "Formatting (your output is rendered as markdown):\n"
    "- Bold every product name with **double asterisks**.\n"
    "- When you mention a product, link it: `[**Product Name**](url)` "
    "using the url from the rank header in your context. Never invent or "
    "guess a URL. If no url is provided for a product, just bold the name.\n"
    "- Use short paragraphs with a blank line between them. Bullet lists "
    "only if the user asked you to compare multiple products or list "
    "concerns.\n"
    "\n"
    "Never invent product names, brands, ingredients, or claims the data "
    "doesn't support."
)


def _profile_lines(profile: dict[str, Any] | None) -> str:
    if profile is None:
        return "User has NOT taken the hair-profile quiz. You do not know their hair."
    parts = [
        f"curl_pattern={profile['curl_pattern']}",
        f"scalp={profile['scalp_condition']}",
        f"density={profile['density']}",
        f"thickness={profile['strand_thickness']}",
        f"porosity={profile['product_absorption']}",
    ]
    if profile.get("concerns"):
        parts.append(f"concerns={','.join(profile['concerns'])}")
    parts.append(f"goals={','.join(profile['goals'])}")
    return "User HairProfile: " + " ".join(parts)


def _top_judged_summary(state: ChatState, n: int = 10) -> str:
    judgments = state.get("judgments") or []
    products = {p["id"]: p for p in state.get("products") or []}
    top_docs = state.get("top_docs") or {}
    if not judgments:
        prods = state.get("products") or []
        if not prods:
            return "No products surfaced."
        lines = ["Top SQL-ordered candidates (no rerank ran):"]
        for i, p in enumerate(prods[:n], start=1):
            lines.append(
                f"  {i}. id={p.get('id')} name={p.get('name')!r} "
                f"sub={p.get('subcategory')!r} url={p.get('url') or ''!r}"
            )
        return "\n".join(lines)

    count = min(n, len(judgments))
    lines = [
        f"Top {count} judged recommendations. Each entry has the rank/"
        "score header followed by its rerank_doc YAML (formulation "
        "facets aligned to the user's HairProfile), plus the full INCI "
        "list and function tags. Reason from these when the user asks "
        "why a product ranked where it did or how it compares.",
    ]
    for j in judgments[:n]:
        pid = j["product_id"]
        product = products.get(pid, {})
        lines.append(
            f"--- rank={j['final_rank']} id={pid} "
            f"name={product.get('name')!r} "
            f"sub={product.get('subcategory')!r} "
            f"url={product.get('url') or ''!r} "
            f"score={j['overall_score']:.2f} "
            f"pts={j['tournament_points']} ---"
        )
        doc = top_docs.get(pid)
        if doc:
            indented = "\n".join(f"  {line}" for line in doc.splitlines())
            lines.append(indented)
    return "\n".join(lines)


def _phase_block(state: ChatState) -> str:
    phase = state.get("phase", "init")
    user_text = state.get("user_text", "")

    if phase == "relay":
        return (
            "PHASE: relay.\n"
            f"User asked: {user_text!r}.\n"
            "The pipeline has produced their personalized recommendations "
            "(or, if no profile, an SQL-ordered fallback). Reply in 1-2 "
            "short sentences introducing the top match in a warm, "
            "conversational tone. Bold its name and link it to the url "
            "from the rank header. Add a runner-up only if it's a "
            "meaningfully different option the user might prefer "
            "(different texture, finish, price tier). Close with one "
            "light follow-up nudge that invites them to keep talking, "
            "e.g. \"want the deeper read?\", \"curious why it edged out "
            "the others?\", \"anything else you want to weigh (scent, "
            "price, feel)?\". One nudge max, and only if it actually "
            "opens a useful next move. Do NOT list the full ranking. "
            "The shortlist sits right next to you."
        )

    if phase == "conversing":
        return (
            "PHASE: conversing.\n"
            "Mid-conversation. The user has seen the recommendations and "
            "has a follow-up. Answer the question directly. Stay short "
            "(1-3 sentences) unless they explicitly ask for depth (\"why\", "
            "\"tell me more\", \"compare\", \"deeper\"). When they do, you "
            "can expand and bring in INCI specifics from the rerank_doc "
            "and HairProfile in your context, still translating to plain "
            "English. Bold and link any product names you mention."
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
    for m in state.get("messages") or []:
        msgs.append({"role": m["role"], "content": m.get("content", "")})
    return msgs
