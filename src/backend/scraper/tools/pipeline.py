"""Firecrawl pipeline: discovery (/map) and extraction (/scrape + json format)."""

import asyncio
import json as _json
import os
from typing import Any

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


def _parse_json_field(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            return _json.loads(raw)
        except _json.JSONDecodeError:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _validate_ingredients(text: str | None) -> bool:
    if not text:
        return False
    tokens = [t for t in text.split(",") if t.strip()]
    return len(tokens) >= 5


async def run_discovery(
    job_id: str, brand_id: str, seed_url: str, limit: int = 500
) -> dict:
    fc = _client()
    result = await fc.map(seed_url, limit=limit)

    urls: list[str] = []
    for link in getattr(result, "links", []) or []:
        url = getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else None)
        if url:
            urls.append(url)

    if urls:
        async with connection() as conn:
            await conn.executemany(
                """insert into products (brand_id, scrape_job_id, url, scrape_status)
                   values ($1::uuid, $2::uuid, $3, 'pending')
                   on conflict (url) do nothing""",
                [(brand_id, job_id, u) for u in urls],
            )
            await conn.execute(
                "update scrape_jobs set pages_found = $2 where id = $1::uuid",
                job_id,
                len(urls),
            )

    return {"urls_found": len(urls)}


async def _extract_one(
    fc: AsyncFirecrawl,
    url: str,
    schema: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[str, ProductExtraction | None, str | None]:
    """Returns (status, parsed_or_none, error_or_none)."""
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
                data = _parse_json_field(getattr(doc, "json", None))
                try:
                    parsed = ProductExtraction(**data)
                except ValidationError as ve:
                    return ("failed", None, f"validation: {ve}")

                if _validate_ingredients(parsed.ingredient_text):
                    return ("success", parsed, None)
                # page reachable but no valid INCI string
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
