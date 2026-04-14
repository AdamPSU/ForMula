"""Tavily research helpers for the hair-product pipeline."""

from __future__ import annotations

from pathlib import Path

from tavily import AsyncTavilyClient

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_RESEARCH_QUERY_TEMPLATE = (_PROMPTS_DIR / "research_query.txt").read_text()

PRODUCT_SCHEMA: dict = {
    "properties": {
        "candidates": {
            "type": "array",
            "description": "List of hair-care product candidates matching the user's profile",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact product name"},
                    "brand": {"type": "string", "description": "Manufacturer or brand"},
                    "url": {
                        "type": "string",
                        "description": "Direct URL to the page where ingredients were verified",
                    },
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Full INCI list in order, exactly as printed",
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "shampoo", "conditioner", "leave-in", "mask",
                            "oil", "gel", "mousse", "cream", "serum", "other",
                        ],
                        "description": "Product category; must be one of the listed enum values",
                    },
                    "price": {
                        "type": "string",
                        "description": "Price with currency, e.g. '$24.00'",
                    },
                    "key_actives": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-5 hero ingredients the product markets",
                    },
                    "allergens": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Common allergens present (e.g. fragrance, essential oils, nuts, gluten)",
                    },
                },
                "required": ["name", "brand", "url", "ingredients", "category"],
            },
        }
    },
    "required": ["candidates"],
}


_client: AsyncTavilyClient | None = None


def get_tavily_client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient()
    return _client


_PROFILE_SKIP_FIELDS = {"free_text"}
_SENTINEL_VALUES = {"unknown", "", None}


def build_research_query(profile, prompt: str, count: int = 3) -> str:
    if profile is None:
        raise ValueError("build_research_query requires a parsed HairProfile")

    parts: list[str] = []
    for key, value in profile.model_dump().items():
        if key in _PROFILE_SKIP_FIELDS:
            continue
        if isinstance(value, list):
            if not value:
                continue
            parts.append(f"{key}: {', '.join(value)}")
        elif value not in _SENTINEL_VALUES:
            parts.append(f"{key}: {value}")

    summary = "; ".join(parts)
    return _RESEARCH_QUERY_TEMPLATE.format(summary=summary, prompt=prompt, count=count)
