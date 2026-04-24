"""Pre-extraction URL classifier.

Drops tool / accessory / merch / sample / gift-card URLs before they reach
`stage-products`, so we never spend 5 Firecrawl credits on a product we
couldn't recommend. One Grok call per brand, priced in cents.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from openai import AsyncOpenAI
from pydantic import BaseModel, Field


_MODEL = "grok-4-1-fast-reasoning"


_FILTER_PROMPT = (
    "You are filtering product URLs from a hair brand's catalog. Decide, "
    "for each URL, whether it points to a product worth scraping for "
    "cosmetic ingredient data (keep) or one we should drop (skip).\n"
    "\n"
    "KEEP — SINGLE products that carry their own INCI ingredient list:\n"
    "- Shampoos, conditioners, leave-in conditioners, hair masks\n"
    "- Styling products: creams, mousses, gels, sprays, pomades, edge "
    "control, curl products\n"
    "- Treatments: bond repair, protein, scalp serum / scalp treatment\n"
    "- Oils: hair oils, pre-wash oils\n"
    "- Hair perfumes / hair mists\n"
    "\n"
    "SKIP — no INCI we can make recommendations against:\n"
    "- Bundles, sets, trios, duos, collections, rituals, kits, gift "
    "boxes, on-the-go duos, 'build your ritual'-style multi-product "
    "pages. These pages don't carry their own ingredient list — their "
    "constituent products appear separately in the catalog via their own "
    "single-product pages, so scraping the bundle page is pure credit "
    "waste (5 credits per `missing` row).\n"
    "- Physical tools: brushes (paddle, round, detangling, boar-bristle, "
    "kabuki, scalp-brush), combs, hair clips, scrunchies, microfiber "
    "towels\n"
    "- Heated tools: hair dryers, flat irons, curling irons, diffusers, "
    "hot-air brushes\n"
    "- Tool accessories: brush cleaners, tool cases, storage\n"
    "- Fabric accessories: silk bonnets, silk scarves, silk pillowcases\n"
    "- Merchandise: crewnecks, tote bags, mugs, coasters, wraps, cups, "
    "home goods\n"
    "- Samples / packettes / sachets (no shelf-stable catalog value)\n"
    "- Gift cards\n"
    "\n"
    "The URL slug is the primary signal (e.g. 'the-hair-dryer' → skip, "
    "'the-hydrating-shampoo' → keep). When the slug is genuinely "
    "ambiguous, lean toward KEEP — a borderline keep costs 5 Firecrawl "
    "credits; a borderline skip costs us a product we could recommend.\n"
    "\n"
    "For each skipped URL, attach a short reason (1–5 words) identifying "
    "the category — e.g. 'brush', 'heated tool', 'gift card', "
    "'accessory', 'merch', 'sample'. Return JSON matching the schema."
)


class _SkippedUrl(BaseModel):
    """One URL dropped from staging, with a short reason for audit."""

    url: str = Field(description="The skipped URL, verbatim from the input list.")
    reason: str = Field(
        description=(
            "Short category-style reason (1-5 words) identifying why this "
            "URL isn't a recommendable product — e.g. 'brush', 'heated "
            "tool', 'silk accessory', 'gift card', 'merch', 'sample'."
        ),
    )


class _FilterResult(BaseModel):
    """Partition of the input URL list into keep / skip sets."""

    keep: list[str] = Field(
        description=(
            "URLs that look like recommendable hair products (shampoo, "
            "conditioner, styling, treatment, oil, mask, hair perfume, "
            "bundle). These proceed to staging + extraction."
        ),
    )
    skip: list[_SkippedUrl] = Field(
        description=(
            "URLs dropped before staging — tools, accessories, merch, "
            "samples, gift cards. Each entry carries a short reason."
        ),
    )


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
    )


def _read_urls(urls_file: str) -> list[str]:
    path = Path(urls_file)
    raw = [line.strip() for line in path.read_text().splitlines()]
    urls = [u for u in raw if u and urlparse(u).scheme in ("http", "https")]
    # dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def filter_links(urls_file: str) -> dict:
    urls = _read_urls(urls_file)
    if not urls:
        return {"kept": 0, "skipped": 0, "keep": [], "skip": []}

    client = _client()
    schema = _FilterResult.model_json_schema()
    resp = await client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _FILTER_PROMPT},
            {
                "role": "user",
                "content": "Classify these URLs:\n" + "\n".join(urls),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "FilterResult",
                "schema": schema,
                "strict": True,
            },
        },
    )

    content = resp.choices[0].message.content or "{}"
    parsed = _FilterResult.model_validate_json(content)

    # Constrain the model's partition to the exact input set. Model-invented
    # or rewritten URLs (trailing slashes, slug normalization, hallucinations)
    # must not reach staging — each one wastes 5 Firecrawl credits.
    input_set = set(urls)
    skipped_urls = {s.url for s in parsed.skip if s.url in input_set}
    kept_urls = {u for u in parsed.keep if u in input_set}
    overlap = kept_urls & skipped_urls
    if overlap:
        raise ValueError(
            f"filter model returned {len(overlap)} URL(s) in both keep and skip: "
            f"{sorted(overlap)[:3]}"
        )

    # Any URL the model dropped falls back to keep (conservative: a missed
    # skip costs credits; a missed keep loses a product we could recommend).
    unaccounted = [u for u in urls if u not in kept_urls and u not in skipped_urls]
    keep = [u for u in urls if u in kept_urls] + unaccounted
    skip = [s.model_dump() for s in parsed.skip if s.url in input_set]

    return {
        "kept": len(keep),
        "skipped": len(skip),
        "keep": keep,
        "skip": skip,
    }
