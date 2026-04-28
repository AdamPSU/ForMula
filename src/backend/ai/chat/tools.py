"""OpenAI tool schemas for the chat agent.

Two tools, surfaced to the LLM as standard function-calls. Each maps
1:1 to a frontend card component. The agent never fulfills these
itself — `explain_product` and `start_quiz` are inert renderable
side-effects whose 'result' is just the act of being shown.
"""

from __future__ import annotations

EXPLAIN_PRODUCT = {
    "type": "function",
    "function": {
        "name": "explain_product",
        "description": (
            "Render an inline product-explainer card next to your reply. "
            "Use when the user asks why a specific product was ranked where "
            "it was, or asks for a deeper read on a single recommendation. "
            "Pull product_id from the user-visible recommendation list. "
            "Your accompanying assistant message should be the explanation; "
            "this tool only renders the card."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "UUID of the product being explained.",
                },
                "axes_summary": {
                    "type": "string",
                    "description": (
                        "One-sentence summary of the strongest axis "
                        "(moisture / scalp safety / structural fit)."
                    ),
                },
                "top_signals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "2-3 INCI ingredients or formulation facets that drove "
                        "the ranking."
                    ),
                },
            },
            "required": ["product_id"],
        },
    },
}

START_QUIZ = {
    "type": "function",
    "function": {
        "name": "start_quiz",
        "description": (
            "Render a 'take the quiz' card that deep-links the user to "
            "/quiz. Use ONLY when the user does not have a HairProfile on "
            "file and the conversation makes it clear they want one."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


def tools_for_phase(phase: str) -> list[dict]:
    """Return the tool list to expose to the LLM for a given phase."""
    if phase in ("relay", "conversing"):
        return [EXPLAIN_PRODUCT, START_QUIZ]
    return []
