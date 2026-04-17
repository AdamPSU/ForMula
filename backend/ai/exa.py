"""Exa research helpers for the hair-product pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from exa_py import AsyncExa

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
RESEARCH_SYSTEM_PROMPT = (_PROMPTS_DIR / "research_system_prompt.txt").read_text().strip()

SEARCH_HIGHLIGHTS_QUERY = "ingredients list INCI"

SEARCH_EXCLUDE_DOMAINS = [
    "reddit.com",
    "incidecoder.com",
    "skinsort.com",
    "byrdie.com",
    "allure.com",
    "cosmopolitan.com",
    "glamour.com",
    "instyle.com",
    "shop.tiktok.com",
    "amazon.com",
    "target.com/s",
    "sephora.com/buy",
    "sephora.com/shop",
    "ulta.com/discover",
    "ulta.com/shop",
    "livingproof.com/product-ingredients",
    "olaplex.com",
    "wella.com",
    "palmers.com",
    "curlsmith.com",
    "orshaircare.com",
    "itsa10haircare.com",
    "formunova.com",
]

PER_PAGE_PRODUCT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The product's exact name as shown on the PDP, excluding the brand.",
        },
        "brand": {
            "type": "string",
            "description": "The brand or manufacturer name.",
        },
        "url": {
            "type": "string",
            "description": "The canonical PDP URL for this product.",
        },
        "ingredients": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The COMPLETE INCI ingredient list, with every ingredient as a separate "
                "string, in the exact order shown on the PDP. This must include all "
                "carriers, solvents, preservatives, fragrance components, surfactants, "
                "conditioning agents, and colorants — every item on the label. Do NOT "
                "put only marketed 'key ingredients' or 'hero actives' here; those go "
                "in the separate key_actives field."
            ),
        },
        "key_actives": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The marketed 'hero' or 'key' active ingredients the brand highlights "
                "on the PDP (typically 1-6 items — e.g. 'biotin', 'hyaluronic acid', "
                "'tea tree oil'). These are the ingredients featured in marketing copy, "
                "NOT the full INCI list. Return an empty array if the PDP does not "
                "highlight specific actives."
            ),
        },
        "category": {
            "type": "string",
            "description": (
                "The product category. Must be one of: shampoo, conditioner, "
                "leave-in, mask, oil, gel, mousse, cream, serum, other."
            ),
        },
        "price": {
            "type": "string",
            "description": "The listed price including currency symbol (e.g. '$24.00').",
        },
    },
    "required": ["name", "brand", "url", "ingredients", "category", "price"],
}

PER_PAGE_SUMMARY_QUERY = (
    "First, verify this PDP is for a HAIR-CARE product (shampoo, conditioner, "
    "co-wash, hair mask, leave-in, hair oil, hair serum, scalp treatment, bond "
    "repair, or hair styling product like gel/mousse/cream). If the PDP is for "
    "skincare, face serum, body lotion, general moisturizer, makeup, or fragrance, "
    "return an object with empty ingredients and empty key_actives arrays "
    "(name/brand may still be filled). Otherwise extract the product's name, "
    "brand, and price, and separate the ingredient data into TWO distinct fields: "
    "(1) `ingredients` = the COMPLETE INCI list as printed on the label (every "
    "single item in order — typically 15-40+ entries), and (2) `key_actives` = "
    "only the 3-6 hero ingredients the brand markets. Do not conflate the two. "
    "If only key actives are shown and no full INCI, return an empty ingredients "
    "array."
)


_client: AsyncExa | None = None


def get_exa_client() -> AsyncExa:
    global _client
    if _client is None:
        _client = AsyncExa(api_key=os.environ["EXA_API_KEY"])
    return _client


_PROFILE_SKIP_FIELDS = {"free_text"}


def profile_to_summary(profile) -> str:
    parts: list[str] = []
    for key, value in profile.model_dump().items():
        if key in _PROFILE_SKIP_FIELDS:
            continue
        if isinstance(value, list):
            if value:
                parts.append(f"{key}: {', '.join(value)}")
        else:
            parts.append(f"{key}: {value}")
    return "; ".join(parts)
