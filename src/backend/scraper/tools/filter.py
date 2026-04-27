"""Pre-extraction URL classifier.

Drops tool / accessory / merch / sample / gift-card URLs before they reach
`stage-products`, so we never spend 5 Firecrawl credits on a product we
couldn't recommend. One Grok call per ~100-URL chunk, priced in cents.
"""

import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from openai import AsyncOpenAI
from pydantic import BaseModel, Field


_MODEL = "grok-4-1-fast-reasoning"
_FILTER_CHUNK_SIZE = 100  # URLs per Grok call; large catalogs blow output token budget at >150
_FILTER_CONCURRENCY = 8   # parallel Grok calls (max chunks in flight)


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
    """Normalize via pipeline._normalize_url so fragment / variant
    duplicates collapse before they reach Grok (saves classifier tokens)
    and before staging (saves 5 credits per dup at extraction)."""
    from .pipeline import _normalize_url

    path = Path(urls_file)
    raw = [line.strip() for line in path.read_text().splitlines()]
    seen: set[str] = set()
    out: list[str] = []
    for line in raw:
        if not line:
            continue
        normalized = _normalize_url(line)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _write_keep_atomic(keep_file: str, keep: list[str]) -> None:
    path = Path(keep_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(keep) + ("\n" if keep else ""))
    os.replace(tmp, path)


def _write_skip_atomic(skip_file: str, skip: list[dict]) -> None:
    path = Path(skip_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(skip, indent=2))
    os.replace(tmp, path)


async def _classify_chunk(
    client: AsyncOpenAI,
    chunk: list[str],
    sem: asyncio.Semaphore,
) -> tuple[set[str], list[dict]]:
    """One Grok call over a ≤_FILTER_CHUNK_SIZE URL chunk. Returns the
    set of URLs the model classified as KEEP plus a list of `{url,
    reason}` SKIP records, both constrained to the input set."""
    schema = _FilterResult.model_json_schema()
    async with sem:
        resp = await client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _FILTER_PROMPT},
                {
                    "role": "user",
                    "content": "Classify these URLs:\n" + "\n".join(chunk),
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
    chunk_set = set(chunk)
    kept = {u for u in parsed.keep if u in chunk_set}
    skips = [s.model_dump() for s in parsed.skip if s.url in chunk_set]
    return kept, skips


async def filter_links(urls_file: str, keep_file: str, skip_file: str) -> dict:
    urls = _read_urls(urls_file)
    if not urls:
        _write_keep_atomic(keep_file, [])
        _write_skip_atomic(skip_file, [])
        return {
            "kept": 0,
            "skipped": 0,
            "keep_file": keep_file,
            "skip_file": skip_file,
            "skip_buckets": {},
            "sample_skips": [],
        }

    # Chunk the URL list. At >~150 URLs Grok's structured-output
    # response truncates mid-stream and the JSON parse blows up. Chunks
    # run in parallel under a small semaphore so big catalogs (Inkey
    # 200+, Sukin 75) finish in roughly one chunk's worth of wallclock.
    client = _client()
    sem = asyncio.Semaphore(_FILTER_CONCURRENCY)
    chunks = [urls[i : i + _FILTER_CHUNK_SIZE] for i in range(0, len(urls), _FILTER_CHUNK_SIZE)]
    chunk_results = await asyncio.gather(
        *[_classify_chunk(client, c, sem) for c in chunks]
    )

    kept_urls: set[str] = set()
    skip: list[dict] = []
    for kept_set, skip_list in chunk_results:
        kept_urls.update(kept_set)
        skip.extend(skip_list)

    # Cross-chunk sanity: a URL appearing in both keep and skip means
    # one chunk's classifier made an error. Treat as a hard fail since
    # each duplicate costs us 5 credits at extraction.
    skipped_urls = {s["url"] for s in skip}
    overlap = kept_urls & skipped_urls
    if overlap:
        raise ValueError(
            f"filter model returned {len(overlap)} URL(s) in both keep and skip "
            f"across chunks: {sorted(overlap)[:3]}"
        )

    # Conservative fallback: any URL the model dropped (didn't put in
    # either list) falls back to keep. A missed skip costs 5 credits;
    # a missed keep loses a product we could recommend.
    unaccounted = [u for u in urls if u not in kept_urls and u not in skipped_urls]
    keep = [u for u in urls if u in kept_urls] + unaccounted

    _write_keep_atomic(keep_file, keep)
    _write_skip_atomic(skip_file, skip)

    bucket_counts = Counter(s["reason"].strip().lower() for s in skip)
    skip_buckets = dict(bucket_counts.most_common())

    seen_buckets: set[str] = set()
    sample_skips: list[dict] = []
    for s in skip:
        bucket = s["reason"].strip().lower()
        if bucket not in seen_buckets:
            seen_buckets.add(bucket)
            sample_skips.append(s)
            if len(sample_skips) >= 5:
                break

    return {
        "kept": len(keep),
        "skipped": len(skip),
        "keep_file": keep_file,
        "skip_file": skip_file,
        "chunks": len(chunks),
        "skip_buckets": skip_buckets,
        "sample_skips": sample_skips,
    }
