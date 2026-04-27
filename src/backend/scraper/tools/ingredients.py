"""Ingredient tagging — extract, normalize, and classify unique INCI
strings from the `products` table.

Tagging fires automatically at the end of `run-and-finish` per brand
(orchestrated from `tools/enrichment.py`); there is no agent-driven
tag-batch loop. The agent never sees the INCI strings.

Per-call flow inside `tag_unknowns_for_brand`:
  1. Discover new INCI from this brand's success rows.
  2. Batch ~100 / Grok call → structured tags + `needs_lookup` flags.
  3. For `needs_lookup=true` rows, Firecrawl-lookup incidecoder + a
     second Grok pass with the markdown for each uncertain INCI.
  4. Upsert into `ingredients` with per-row autocommit.
"""

import asyncio
import json
import os
import re
from collections import Counter
from urllib.parse import quote_plus

from firecrawl import AsyncFirecrawl
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from ..db import connection
from ..validation import check_db_drift
from ..validation.models import FunctionTag, IngredientTagOutput


# ─── Normalization ────────────────────────────────────────────────────
#
# Bare-minimum, non-semantic. Within a single product's INCI list a
# manufacturer never uses two names for the same molecule, so we don't
# attempt cross-listing canonicalization. Per design.

# Split on commas, semicolons, newlines AND on `.\s*\*` (period followed
# by an asterisk is the standard footnote separator: e.g. `SODIUM
# HYDROXIDE. *OUR SCENT BLEND...`). Without this the next ingredient
# fuses into the previous one and lands in `ingredients` as a long
# garbage row tagged `other`. We don't split on a bare period because
# many INCI tokens legitimately end with one (`ALCOHOL DENAT.`).
_SPLIT_RE = re.compile(r"[,;\n]+|\.\s*(?=\*)")
_WS_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\.\,\;\:\*]+|[\s\.\,\;\:\*]+$")


# Color additives are real INCI but contribute nothing to a hair-fit
# reranker — colorant choice doesn't affect curl/scalp/density fit. We
# drop them at normalize time so they never enter the `ingredients`
# table or the rerank doc's `Ingredients:` line. Pattern set is
# intentional, not a grab-bag: each prefix is a regulated colorant
# nomenclature (Color Index numbers, EU/US dye family names).
_COLORANT_PATTERNS = (
    re.compile(r"^CI\s*\d+(?:[/\s].*)?$"),                  # CI 17200, CI17200/RED 33
    re.compile(r"^(BASIC|ACID|HC|DISPERSE|REACTIVE|DIRECT)\s+(BLUE|RED|YELLOW|BROWN|VIOLET|GREEN|ORANGE|BLACK)\s*\d+$"),
    re.compile(r"^(?:FD&C|D&C)\s+\w+(?:\s+\d+)?$"),         # FD&C Red 40, D&C Yellow 5
    re.compile(r"^(BLUE|RED|YELLOW|BROWN|VIOLET|GREEN|ORANGE|BLACK)\s+\d+$"),  # post-CI-stripped names like 'RED 33'
)


def _is_colorant(token: str) -> bool:
    return any(p.match(token) for p in _COLORANT_PATTERNS)


def _normalize(token: str) -> str | None:
    """UPPER + trim + collapse whitespace + strip asterisks/edge punctuation.
    Parens content preserved. Returns None for tokens that aren't real
    ingredients (too short, no letters at all) or for color additives
    (regulated dye nomenclature with no fit signal — see _COLORANT_PATTERNS)."""
    s = _EDGE_PUNCT_RE.sub("", token)
    s = _WS_RE.sub(" ", s).strip().upper()
    if len(s) < 2:
        return None
    if not any(c.isalpha() for c in s):
        return None
    if _is_colorant(s):
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


# ─── Batch tagging (Grok) ─────────────────────────────────────────────
#
# Replaces the prior agent-in-the-loop pattern (agent reads 50 lines,
# decides per-line, builds JSONL, calls tag-batch). One Grok call per
# ~100 INCI returns the whole batch in structured output. The agent
# never sees the INCI strings.

_TAG_MODEL = "grok-4-1-fast-reasoning"
_TAG_BATCH_SIZE = 100
_TAG_CONCURRENCY = 8  # parallel Grok calls (per batch); each batch ≤100 INCI


_TAG_PROMPT = (
    "You are a cosmetic-chemistry tagger. For each INCI ingredient name "
    "in the input list, emit one entry assigning function tags from the "
    "closed enum below. Output one entry per input — preserve the "
    "`inci_name` verbatim from the input.\n"
    "\n"
    "Tag from knowledge by default. The vast majority of common INCI "
    "have unambiguous structural cues:\n"
    "- `*-eth*-sulfate`, `*-sulfonate`, `*-laureate`, `disodium *-`, "
    "fatty-acid soaps → `anionic_surfactant`\n"
    "- `*-trimonium *`, `behentrimonium *`, `cetrimonium *`, "
    "`polyquaternium-N` → `cationic_surfactant` (and ALSO `polyquat` "
    "for the polyquaternium series)\n"
    "- `decyl glucoside`, `coco glucoside`, `lauryl glucoside`, "
    "`PEG-* esters`, polysorbate → `nonionic_surfactant`\n"
    "- `cocamidopropyl betaine`, `*-amphoacetate`, `*-sultaine` → "
    "`amphoteric_surfactant`\n"
    "- `dimethicone`, `*-cone`, `*-siloxane` (non-volatile) → "
    "`silicone_non_water_soluble`\n"
    "- `cyclopentasiloxane`, `cyclohexasiloxane`, `cyclomethicone` → "
    "`silicone_volatile`\n"
    "- `PEG-*-dimethicone`, `dimethicone copolyol` → "
    "`silicone_water_soluble`\n"
    "- `hydrolyzed *-protein` → `protein_hydrolyzed`\n"
    "- intact protein peptides (e.g. `keratin`, `silk amino acids` "
    "without `hydrolyzed`) → `protein_intact`\n"
    "- recognizable Latin binomial `* oil` (jojoba, argania spinosa, "
    "olea europaea, cocos nucifera, etc.) → `plant_oil` AND `emollient` "
    "(add `occlusive` for heavy oils)\n"
    "- `* butter` (shea, mango, cocoa) → `butter` AND `emollient` AND "
    "`occlusive`\n"
    "- recognizable Latin binomial in `* extract`, `* leaf extract`, "
    "`* flower extract`, `* seed extract`, `* root extract`, `* fruit "
    "extract`, `* bark extract` form (Moringa pterygosperma, Spiraea "
    "ulmaria, Chlorella pyrenoidosa, Ascophyllum nodosum, Phyllostachys "
    "nigra, Camellia sinensis, Rosmarinus officinalis, Aloe barbadensis, "
    "etc.) → `humectant` (default for cosmetic plant extracts, which "
    "are typically water-glycerin macerations). Use `antioxidant` "
    "additionally for known antioxidant-rich extracts (green tea, "
    "rosemary, grape seed). Do NOT set `needs_lookup` for these — "
    "plant-extract macerations are functional adjuncts with broad "
    "humectant behavior whether or not you know the specific species.\n"
    "- `glycerin`, `*-glycol` (non-drying), `urea`, `panthenol`, "
    "`sodium PCA` → `humectant` (panthenol also gets `film_former`)\n"
    "- `water`, `aqua` → `solvent`\n"
    "- `cetyl alcohol`, `cetearyl alcohol`, `behenyl alcohol`, "
    "`stearyl alcohol` → `fatty_alcohol`\n"
    "- `alcohol denat`, `SD alcohol *`, `isopropyl alcohol` → "
    "`drying_alcohol`\n"
    "- `phenoxyethanol`, parabens, `methylisothiazolinone`, "
    "`benzyl alcohol`, `sodium benzoate` (preservative dose), "
    "`potassium sorbate`, `chlorphenesin` → `preservative`\n"
    "- `disodium EDTA`, `tetrasodium EDTA`, `phytic acid`, "
    "`etidronic acid` → `chelator`\n"
    "- `citric acid`, `lactic acid`, `sodium hydroxide`, `sodium "
    "citrate` (when unmistakeably pH-buffering) → `ph_adjuster`\n"
    "- `fragrance`, `parfum`, declared fragrance allergens (limonene, "
    "linalool, citronellol, geraniol, hexyl cinnamal, citral) → "
    "`fragrance`\n"
    "- recognizable essential-oil binomials (lavandula, mentha, "
    "rosmarinus) → `essential_oil` (and add `fragrance`)\n"
    "- `tocopherol`, `tocopheryl acetate`, ascorbic acid → "
    "`antioxidant`\n"
    "- `salicylic acid`, AHAs at exfoliating concentrations → "
    "`exfoliant`\n"
    "- `ceramide *`, `phytosphingosine` → `ceramide`\n"
    "- `zinc pyrithione`, `piroctone olamine`, `climbazole`, "
    "`ketoconazole`, `selenium sulfide`, `salicylic acid` (scalp "
    "dose) → `antidandruff`\n"
    "- known heat-active film-formers (PVP, polyquaternium-55) → "
    "`film_former` (and `heat_protectant` if positioned as such)\n"
    "- UV filters (avobenzone, octocrylene, octinoxate, zinc oxide, "
    "titanium dioxide) → `uv_filter`\n"
    "- minoxidil, finasteride, caffeine, redensyl, capixyl, "
    "procapil → `hair_growth_active`\n"
    "- bond builders (bis-aminopropyl diglycol dimaleate / Olaplex "
    "AP-OL; maleic acid in bond context) → `bond_builder`\n"
    "\n"
    "Surfactant ionic class is non-negotiable — anionic + cationic "
    "form an insoluble complex. If you cannot identify the ionic class "
    "with high confidence, set `needs_lookup=true`.\n"
    "\n"
    "Set `needs_lookup=true` ONLY when you genuinely cannot identify "
    "the function: proprietary blend names, novel actives with no "
    "structural cues, ambiguous chemistry. When `needs_lookup=true`, "
    "set `function_tags=[\"other\"]` and `common_name` to the input "
    "name as a placeholder — the orchestrator will fetch the "
    "incidecoder reference and call you again with the markdown.\n"
    "\n"
    "Tag junk strings (footnote fragments like `*CERTIFIED ORGANIC. "
    "OM021`, fused tokens like `LIMONENELINALOOL`, color markers like "
    "`+/-`, materials like `BOAR BRISTLE`) as `function_tags=[\"other\"]` "
    "with `needs_lookup=false`. Don't waste lookup budget on noise.\n"
    "\n"
    "Set `has_safety_concern=true` ONLY for documented endocrine "
    "disruption, formaldehyde donors, MIT/MCI above EU limits, or "
    "banned dyes. Don't flag generic 'may irritate' — that's true of "
    "most surfactants.\n"
    "\n"
    "If a per-INCI `lookup_markdown` is present in the input, use it "
    "as the source of truth — the markdown is the incidecoder.com "
    "reference page, which lists CosIng official functions, CAS, and "
    "any SCCS safety opinions. Translate CosIng vocabulary to our "
    "enum (e.g. 'antistatic + hair conditioning' → "
    "`cationic_surfactant`).\n"
    "\n"
    "Output JSON matching the IngredientTagBatch schema."
)


class _BatchEntry(BaseModel):
    """One Grok-tagged ingredient inside a batch response."""

    inci_name: str = Field(
        ...,
        description="Echo the input inci_name verbatim (uppercase, unchanged).",
    )
    function_tags: list[FunctionTag] = Field(
        ...,
        description="One or more values from the closed FunctionTag enum.",
    )
    common_name: str = Field(
        ..., description="Human-friendly name, e.g. 'Glycerin'."
    )
    has_safety_concern: bool = Field(
        ..., description="True only for documented restricted-use concerns."
    )
    needs_lookup: bool = Field(
        ...,
        description=(
            "True ONLY when you cannot confidently classify from the "
            "INCI name alone (no structural cues, novel/proprietary)."
        ),
    )


class _BatchResult(BaseModel):
    tags: list[_BatchEntry]


def _xai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
    )


async def _grok_tag_batch(
    client: AsyncOpenAI,
    items: list[dict],  # [{inci_name: str, lookup_markdown: str | None}, ...]
) -> list[_BatchEntry]:
    """Single Grok call → one entry per input. Hallucinated names are
    dropped; missing-from-output inputs get a fallback `other` row."""
    schema = _BatchResult.model_json_schema()
    user = "Tag these ingredients:\n\n" + json.dumps(items, ensure_ascii=False)
    resp = await client.chat.completions.create(
        model=_TAG_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": _TAG_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "IngredientTagBatch",
                "schema": schema,
                "strict": True,
            },
        },
    )
    raw = resp.choices[0].message.content or "{}"
    parsed = _BatchResult.model_validate_json(raw)

    input_names = {it["inci_name"] for it in items}
    by_name: dict[str, _BatchEntry] = {}
    for entry in parsed.tags:
        if entry.inci_name in input_names and entry.inci_name not in by_name:
            by_name[entry.inci_name] = entry
    # Backfill anything Grok dropped with a conservative `other` row so
    # the upsert pass is exhaustive.
    out: list[_BatchEntry] = []
    for it in items:
        name = it["inci_name"]
        if name in by_name:
            out.append(by_name[name])
        else:
            out.append(_BatchEntry(
                inci_name=name,
                function_tags=["other"],
                common_name=name.title(),
                has_safety_concern=False,
                needs_lookup=False,
            ))
    return out


async def _upsert_entry(conn, entry: _BatchEntry) -> str:
    """Single-row upsert. Returns 'inserted' | 'updated'. Never raises —
    a bad row is logged and skipped (per-row autocommit discipline)."""
    row = await conn.fetchrow(
        """insert into ingredients
             (inci_name, function_tags, common_name, has_safety_concern)
           values ($1, $2, $3, $4)
           on conflict (inci_name) do update set
             function_tags      = excluded.function_tags,
             common_name        = excluded.common_name,
             has_safety_concern = excluded.has_safety_concern
           returning (xmax = 0) as inserted""",
        entry.inci_name,
        list(entry.function_tags),
        entry.common_name,
        entry.has_safety_concern,
    )
    return "inserted" if row["inserted"] else "updated"


async def tag_unknowns_for_brand(brand_id: str) -> dict:
    """Discover new INCI from this brand's just-extracted products and
    tag them via batch Grok (+ Firecrawl lookup fallback for genuinely
    uncertain rows). Idempotent — INCI already in `ingredients` are
    skipped.

    Returns `{discovered, tagged_from_knowledge, looked_up,
    inserted, updated, errors}`.
    """
    async with connection() as conn:
        await check_db_drift(conn, target="ingredients")
        product_rows = await conn.fetch(
            """select ingredient_text from products
               where brand_id        = $1::uuid
                 and scrape_status   = 'success'
                 and ingredient_text is not null""",
            brand_id,
        )
        tagged_rows = await conn.fetch("select inci_name from ingredients")

    already_tagged: set[str] = {r["inci_name"] for r in tagged_rows}
    freq: Counter[str] = Counter()
    for r in product_rows:
        for name in set(_split_ingredient_text(r["ingredient_text"])):
            freq[name] += 1
    unknowns = [name for name, _ in freq.most_common() if name not in already_tagged]

    if not unknowns:
        return {
            "discovered": 0,
            "tagged_from_knowledge": 0,
            "looked_up": 0,
            "inserted": 0,
            "updated": 0,
            "errors": [],
        }

    client = _xai_client()
    sem = asyncio.Semaphore(_TAG_CONCURRENCY)

    async def run_batch(batch_items: list[dict]) -> list[_BatchEntry]:
        async with sem:
            return await _grok_tag_batch(client, batch_items)

    # Pass 1: classify all unknowns from the name alone.
    initial_items = [{"inci_name": n, "lookup_markdown": None} for n in unknowns]
    chunks = [
        initial_items[i : i + _TAG_BATCH_SIZE]
        for i in range(0, len(initial_items), _TAG_BATCH_SIZE)
    ]
    pass1_lists = await asyncio.gather(*[run_batch(c) for c in chunks])
    pass1: list[_BatchEntry] = [e for sub in pass1_lists for e in sub]

    confident = [e for e in pass1 if not e.needs_lookup]
    uncertain_names = [e.inci_name for e in pass1 if e.needs_lookup]

    # Pass 2: Firecrawl-lookup each uncertain INCI, then re-classify
    # with the markdown as additional context. One Firecrawl call per
    # uncertain INCI is unavoidable; expected count is small.
    looked_up_entries: list[_BatchEntry] = []
    if uncertain_names:
        lookups = await asyncio.gather(
            *[lookup_ingredient(name) for name in uncertain_names]
        )
        lookup_items = [
            {"inci_name": name, "lookup_markdown": (lk.get("markdown") or "")[:6000]}
            for name, lk in zip(uncertain_names, lookups)
        ]
        # Smaller batches for the lookup pass since each item carries
        # ~6KB of markdown context.
        lookup_batch_size = 20
        lookup_chunks = [
            lookup_items[i : i + lookup_batch_size]
            for i in range(0, len(lookup_items), lookup_batch_size)
        ]
        pass2_lists = await asyncio.gather(*[run_batch(c) for c in lookup_chunks])
        looked_up_entries = [e for sub in pass2_lists for e in sub]

    inserted = 0
    updated = 0
    errors: list[dict] = []
    all_entries = confident + looked_up_entries

    async with connection() as conn:
        for entry in all_entries:
            try:
                result = await _upsert_entry(conn, entry)
                if result == "inserted":
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:  # noqa: BLE001
                errors.append({
                    "inci_name": entry.inci_name,
                    "error": f"{type(e).__name__}: {e}",
                })

    return {
        "discovered": len(unknowns),
        "tagged_from_knowledge": len(confident),
        "looked_up": len(looked_up_entries),
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
    }


# ─── Legacy CLI helpers (kept callable internally) ────────────────────


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
