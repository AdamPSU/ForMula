"""Ingredient tagging — extract, list, lookup, and tag unique INCI
strings from the `products` table. Four subcommands wired into
`__main__.py`:

  list-untagged      → unique normalized INCI not yet in `ingredients`
  lookup-ingredient  → Firecrawl /scrape on incidecoder.com for one INCI
  tag-batch          → JSONL upsert into `ingredients` (per-row autocommit)
  tag-status         → counts + top untagged by frequency

Workflow lives in `scraper/references/INGREDIENT-TAGGING.md`.
"""

import json
import os
import re
from collections import Counter
from urllib.parse import quote_plus

from firecrawl import AsyncFirecrawl
from pydantic import ValidationError

from ..db import connection
from ..validation import check_db_drift
from ..validation.models import IngredientTagOutput


# ─── Normalization ────────────────────────────────────────────────────
#
# Bare-minimum, non-semantic. Within a single product's INCI list a
# manufacturer never uses two names for the same molecule, so we don't
# attempt cross-listing canonicalization. Per design.

_SPLIT_RE = re.compile(r"[,;\n]+")
_WS_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\.\,\;\:\*]+|[\s\.\,\;\:\*]+$")


def _normalize(token: str) -> str | None:
    """UPPER + trim + collapse whitespace + strip asterisks/edge punctuation.
    Parens content preserved. Returns None for tokens that aren't real
    ingredients (too short, no letters at all)."""
    s = _EDGE_PUNCT_RE.sub("", token)
    s = _WS_RE.sub(" ", s).strip().upper()
    if len(s) < 2:
        return None
    if not any(c.isalpha() for c in s):
        return None
    return s


def _split_ingredient_text(text: str) -> list[str]:
    """Split on `,`, `;`, newlines. Drops empties via _normalize."""
    out: list[str] = []
    for raw in _SPLIT_RE.split(text):
        n = _normalize(raw)
        if n is not None:
            out.append(n)
    return out


# ─── Firecrawl lookup ─────────────────────────────────────────────────
#
# incidecoder.com hosts one structured page per INCI ingredient. The
# slug pattern is deterministic enough for a direct /scrape attempt;
# on miss we fall back to the site's search page so the agent can
# pick the right slug from the results.

_SLUG_NONALNUM_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """INCI name → incidecoder URL slug. Lowercases, drops parens
    content, collapses non-alphanumerics to single hyphens."""
    s = re.sub(r"\([^)]*\)", "", name).lower()
    s = _SLUG_NONALNUM_RE.sub("-", s).strip("-")
    return s


def _firecrawl() -> AsyncFirecrawl:
    return AsyncFirecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])


async def lookup_ingredient(name: str) -> dict:
    """Fetch the incidecoder.com reference page for one INCI ingredient
    via Firecrawl /scrape (5 credits). On miss, fall back to the site's
    search results page (also 5 credits).

    The agent reads the returned markdown and decides function tags from
    its content. Replaces WebSearch in the tagging workflow.
    """
    fc = _firecrawl()
    slug = _slugify(name)
    page_url = f"https://incidecoder.com/ingredients/{slug}"
    try:
        doc = await fc.scrape(page_url, formats=["markdown"])
        markdown = getattr(doc, "markdown", None) or ""
        # incidecoder serves a generic 404 page rather than HTTP 404 for
        # unknown slugs — detect by content rather than status code.
        if markdown and "this page does not exist" not in markdown.lower():
            return {
                "name": name,
                "slug": slug,
                "url": page_url,
                "source": "page",
                "credits_used": 5,
                "markdown": markdown,
            }
    except Exception as e:  # noqa: BLE001 — firecrawl raises varied errors
        page_error = f"{type(e).__name__}: {e}"
    else:
        page_error = "page exists but appears to be a 404"

    # Fallback: search results page. Agent can read result list and call
    # lookup-ingredient again with a corrected name.
    search_url = f"https://incidecoder.com/search?query={quote_plus(name)}"
    try:
        doc = await fc.scrape(search_url, formats=["markdown"])
        markdown = getattr(doc, "markdown", None) or ""
    except Exception as e:  # noqa: BLE001
        return {
            "name": name,
            "slug": slug,
            "url": search_url,
            "source": "search",
            "credits_used": 10,  # both attempts billed
            "page_error": page_error,
            "search_error": f"{type(e).__name__}: {e}",
            "markdown": "",
        }

    return {
        "name": name,
        "slug": slug,
        "url": search_url,
        "source": "search",
        "credits_used": 10,
        "page_error": page_error,
        "markdown": markdown,
    }


# ─── Subcommands ──────────────────────────────────────────────────────


async def list_untagged(out_file: str, limit: int | None) -> dict:
    """Walk products.ingredient_text, normalize, dedupe, exclude names
    already in `ingredients`. Write one per line to `out_file`. Return
    counts + frequency-ranked sample.

    `limit` truncates the output file but does not change `count` —
    useful for spot-checking normalization without writing 5K lines.
    """
    async with connection() as conn:
        product_rows = await conn.fetch(
            """select ingredient_text from products
               where scrape_status = 'success'
                 and ingredient_text is not null"""
        )
        tagged_rows = await conn.fetch("select inci_name from ingredients")

    tagged: set[str] = {r["inci_name"] for r in tagged_rows}
    freq: Counter[str] = Counter()
    for r in product_rows:
        # set() per product so an ingredient repeated in one INCI string
        # (rare but happens) doesn't double-count toward frequency.
        seen = set(_split_ingredient_text(r["ingredient_text"]))
        for name in seen:
            freq[name] += 1

    untagged_by_freq = [
        (name, count) for name, count in freq.most_common() if name not in tagged
    ]
    out_names = [name for name, _ in untagged_by_freq]
    written = out_names[:limit] if limit is not None else out_names

    with open(out_file, "w") as f:
        for name in written:
            f.write(name + "\n")

    return {
        "count": len(out_names),
        "written": len(written),
        "out_file": out_file,
        "sample": out_names[:10],
        "top_by_frequency": [
            {"inci_name": n, "products": c} for n, c in untagged_by_freq[:20]
        ],
    }


async def tag_batch(file: str) -> dict:
    """Read JSONL from `file`, validate each line via IngredientTagOutput,
    upsert into `ingredients`. Per-row autocommit — a malformed row never
    rolls back the rest of the batch.

    Drift-checks the `ingredients_function_tags` constraint up front so a
    forgotten migration fails loudly instead of corrupting tags.
    """
    async with connection() as conn:
        await check_db_drift(conn, target="ingredients")

    inserted = 0
    updated = 0
    errors: list[dict] = []

    with open(file) as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]

    async with connection() as conn:
        for i, raw in enumerate(lines, start=1):
            try:
                payload = IngredientTagOutput.model_validate_json(raw)
            except ValidationError as e:
                errors.append({"line": i, "error": f"validation: {e.errors()[0]['msg']}"})
                continue
            try:
                row = await conn.fetchrow(
                    """insert into ingredients
                         (inci_name, function_tags, common_name, has_safety_concern)
                       values ($1, $2, $3, $4)
                       on conflict (inci_name) do update set
                         function_tags      = excluded.function_tags,
                         common_name        = excluded.common_name,
                         has_safety_concern = excluded.has_safety_concern
                       returning (xmax = 0) as inserted""",
                    payload.inci_name,
                    list(payload.function_tags),
                    payload.common_name,
                    payload.has_safety_concern,
                )
                if row["inserted"]:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({"line": i, "error": f"{type(e).__name__}: {e}"})

    return {
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
    }


async def tag_status() -> dict:
    """Counts (total unique in products vs tagged), `other` rate, and
    the top 10 untagged by product frequency."""
    async with connection() as conn:
        product_rows = await conn.fetch(
            """select ingredient_text from products
               where scrape_status = 'success'
                 and ingredient_text is not null"""
        )
        tagged_rows = await conn.fetch(
            "select inci_name, function_tags from ingredients"
        )

    tagged_names: set[str] = {r["inci_name"] for r in tagged_rows}

    freq: Counter[str] = Counter()
    for r in product_rows:
        for name in set(_split_ingredient_text(r["ingredient_text"])):
            freq[name] += 1

    total_unique = len(freq)
    tagged_count = sum(1 for name in freq if name in tagged_names)
    untagged_count = total_unique - tagged_count

    other_count = sum(
        1 for r in tagged_rows if "other" in (r["function_tags"] or [])
    )
    other_rate = (other_count / len(tagged_rows)) if tagged_rows else 0.0

    top_untagged = [
        {"inci_name": name, "products": count}
        for name, count in freq.most_common()
        if name not in tagged_names
    ][:10]

    return {
        "total_unique_in_products": total_unique,
        "tagged": tagged_count,
        "untagged": untagged_count,
        "other_rate": round(other_rate, 4),
        "top_untagged_by_frequency": top_untagged,
    }
