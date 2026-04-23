"""Firecrawl pipeline: discovery (/map + index enumeration) and extraction."""

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

from firecrawl import AsyncFirecrawl
from pydantic import ValidationError

from ..db import connection, get_pool
from ..models import ProductExtraction


EXTRACT_PROMPT = (
    "Extract product information from this page. Only return fields that are "
    "visible verbatim on the page. Many pages are not product pages (e.g. "
    "/about, /blog, /collections); in that case return null for every field. "
    "Never paraphrase, translate, or invent values — especially not the INCI "
    "ingredient list. Return the ingredient list exactly as printed on the label."
)


def _client() -> AsyncFirecrawl:
    return AsyncFirecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])


def _validate_ingredients(text: str | None) -> bool:
    if not text:
        return False
    tokens = [t for t in text.split(",") if t.strip()]
    return len(tokens) >= 5


def _same_host(a: str, b: str) -> bool:
    ha = urlparse(a).hostname or ""
    hb = urlparse(b).hostname or ""
    return ha.lower() == hb.lower()


def _url_of(link) -> str | None:
    return getattr(link, "url", None)


# ---------------------------------------------------------------------------
# Discovery — step 1: list domain URLs ranked by semantic relevance
# ---------------------------------------------------------------------------

async def list_site_urls(
    seed_url: str,
    search: str = "hair products",
    limit: int = 100,
) -> dict:
    fc = _client()
    result = await fc.map(seed_url, search=search, limit=limit)
    urls = [u for link in (getattr(result, "links", None) or []) if (u := _url_of(link))]
    return {"urls": urls}


# ---------------------------------------------------------------------------
# Discovery — step 2: list same-domain links on one page (the products index)
# ---------------------------------------------------------------------------

async def list_page_links(url: str) -> dict:
    fc = _client()
    doc = await fc.scrape(url, formats=["links"])
    raw = getattr(doc, "links", None) or []
    links = [
        l for link in raw
        if (l := (link if isinstance(link, str) else _url_of(link)))
        and _same_host(l, url)
        and l.rstrip("/") != url.rstrip("/")
    ]
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return {"links": out}


# ---------------------------------------------------------------------------
# Discovery — step 3: insert verified URLs as pending rows
# ---------------------------------------------------------------------------

async def stage_products(job_id: str, brand_id: str, urls_file: str) -> dict:
    path = Path(urls_file)
    raw = [line.strip() for line in path.read_text().splitlines()]
    urls = [
        u for u in raw
        if u and urlparse(u).scheme in ("http", "https")
    ]
    # dedupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    if not deduped:
        return {"staged": 0, "skipped": 0}

    async with connection() as conn:
        before = await conn.fetchval(
            "select count(*) from products where scrape_job_id = $1::uuid",
            job_id,
        )
        await conn.executemany(
            """insert into products (brand_id, scrape_job_id, url, scrape_status)
               values ($1::uuid, $2::uuid, $3, 'pending')
               on conflict (url) do nothing""",
            [(brand_id, job_id, u) for u in deduped],
        )
        after = await conn.fetchval(
            "select count(*) from products where scrape_job_id = $1::uuid",
            job_id,
        )
        staged = (after or 0) - (before or 0)
        skipped = len(deduped) - staged
        await conn.execute(
            """update scrape_jobs
               set pages_found = coalesce(pages_found, 0) + $2
               where id = $1::uuid""",
            job_id,
            staged,
        )

    return {"staged": staged, "skipped": skipped}


# ---------------------------------------------------------------------------
# Extraction — unchanged
# ---------------------------------------------------------------------------

async def _extract_one(
    fc: AsyncFirecrawl,
    url: str,
    schema: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[str, ProductExtraction | None, str | None]:
    async with semaphore:
        last_error: str | None = None
        for attempt in range(3):
            try:
                doc = await fc.scrape(
                    url,
                    formats=[
                        {
                            "type": "json",
                            "prompt": EXTRACT_PROMPT,
                            "schema": schema,
                        }
                    ],
                )
                data = getattr(doc, "json", None) or {}
                try:
                    parsed = ProductExtraction(**data)
                except ValidationError as ve:
                    return ("failed", None, f"validation: {ve}")

                if _validate_ingredients(parsed.ingredient_text):
                    return ("success", parsed, None)
                parsed.ingredient_text = None
                return ("missing", parsed, None)
            except Exception as e:  # noqa: BLE001 — firecrawl raises varied errors
                last_error = f"{type(e).__name__}: {e}"
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        return ("failed", None, last_error)


async def run_extraction(job_id: str, batch_size: int = 50) -> dict:
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """select id, url from products
               where scrape_job_id = $1::uuid and scrape_status = 'pending'
               order by url limit $2""",
            job_id,
            batch_size,
        )

    if not rows:
        return {"processed": 0, "success": 0, "missing": 0, "failed": 0}

    fc = _client()
    schema = ProductExtraction.model_json_schema()
    sem = asyncio.Semaphore(8)

    tasks = [_extract_one(fc, r["url"], schema, sem) for r in rows]
    results = await asyncio.gather(*tasks)

    stats = {"processed": len(rows), "success": 0, "missing": 0, "failed": 0}

    async with pool.acquire() as conn:
        async with conn.transaction():
            for row, (status, parsed, err) in zip(rows, results):
                stats[status] += 1
                if parsed is not None:
                    await conn.execute(
                        """update products set
                             name            = coalesce($2, name),
                             product_type    = coalesce($3, product_type),
                             description     = coalesce($4, description),
                             ingredient_text = coalesce($5, ingredient_text),
                             scrape_status   = $6,
                             scrape_error    = null
                           where id = $1""",
                        row["id"],
                        parsed.name,
                        parsed.product_type,
                        parsed.description,
                        parsed.ingredient_text,
                        status,
                    )
                else:
                    await conn.execute(
                        """update products set
                             scrape_status = 'failed',
                             scrape_error  = $2
                           where id = $1""",
                        row["id"],
                        err,
                    )
            await conn.execute(
                """update scrape_jobs
                   set pages_scraped = coalesce(pages_scraped, 0) + $2
                   where id = $1::uuid""",
                job_id,
                len(rows),
            )

    return stats
