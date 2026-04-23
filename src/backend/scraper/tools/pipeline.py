"""Firecrawl pipeline: discovery (/map + index enumeration) and extraction."""

import asyncio
import os
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from firecrawl import AsyncFirecrawl
from firecrawl.v2.utils.error_handler import RateLimitError
from pydantic import ValidationError

from ..db import connection, get_pool
from ..models import SUBCATEGORY_TO_CATEGORY, ProductExtraction


EXTRACT_PROMPT = (
    "Extract structured data about ONE specific product from its product detail "
    "page. Verbatim-extraction only: never paraphrase, translate, reorder, "
    "invent, or concatenate values.\n"
    "\n"
    "Scope strictly to this product. Product pages routinely embed 'shop similar' "
    "carousels, 'you may also like' rails, bundle-constituent listings, and "
    "sibling-product cards — ignore all of them. Only pull values that "
    "unambiguously describe the product this page is about. If attribution is "
    "ambiguous, return null.\n"
    "\n"
    "Recognize non-product pages. Editorial (/blog, /about), policy, ritual "
    "guide, and collection/category pages are not single-product pages — return "
    "null for every field.\n"
    "\n"
    "Null is always a valid answer. Never invent a value to fill a field, and "
    "never pick the closest-ish enum value when nothing truly fits. A wrong "
    "value is worse than a null value."
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
# Extraction
# ---------------------------------------------------------------------------

_RETRY_ATTEMPTS = 4
_RETRY_BASE_S = 10  # 10, 20, 40, 60 — survives Firecrawl's 60s rate-limit window
_SCRAPE_COST_CREDITS = 5  # JSON-format /scrape is 5 credits per URL
_FREE_RPM = 10
_FREE_CONCURRENCY = 2


class _RateLimiter:
    """Sliding-window async rate limiter: max N acquires per window_s seconds."""

    def __init__(self, max_requests: int, window_s: float = 60.0):
        self._max = max_requests
        self._window_s = window_s
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            async with self._lock:
                now = loop.time()
                while self._timestamps and now - self._timestamps[0] >= self._window_s:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                wait_s = self._window_s - (now - self._timestamps[0])
            await asyncio.sleep(wait_s)


# Module-level so all in-process scrape calls share the same minute window.
_scrape_limiter = _RateLimiter(max_requests=_FREE_RPM, window_s=60.0)


def _retry_after_seconds(err: Exception) -> float | None:
    resp = getattr(err, "response", None)
    headers = getattr(resp, "headers", None)
    header = headers.get("Retry-After") if headers else None
    if not header:
        return None
    try:
        return float(header)
    except (TypeError, ValueError):
        return None


async def _extract_one(
    fc: AsyncFirecrawl,
    url: str,
    schema: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[str, ProductExtraction | None, str | None]:
    async with semaphore:
        last_error: str | None = None
        for attempt in range(_RETRY_ATTEMPTS):
            await _scrape_limiter.acquire()
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
            except RateLimitError as e:
                last_error = f"{type(e).__name__}: {e}"
                if attempt < _RETRY_ATTEMPTS - 1:
                    hinted = _retry_after_seconds(e)
                    delay = hinted if hinted is not None else min(
                        60, _RETRY_BASE_S * (2**attempt)
                    )
                    await asyncio.sleep(delay)
            except Exception as e:  # noqa: BLE001 — firecrawl raises varied errors
                last_error = f"{type(e).__name__}: {e}"
                if attempt < _RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(min(60, _RETRY_BASE_S * (2**attempt)))
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

    # Preflight: live credit check so we never start a batch we can't finish.
    expected_cost = len(rows) * _SCRAPE_COST_CREDITS
    usage = await fc.get_credit_usage()
    if usage.remaining_credits < expected_cost:
        raise RuntimeError(
            f"insufficient Firecrawl credits: need {expected_cost} for "
            f"{len(rows)} URLs, have {usage.remaining_credits}"
        )

    schema = ProductExtraction.model_json_schema()
    # Concurrency and RPM are enforced independently: Semaphore for parallel
    # workers, _scrape_limiter for the 10/min Free-tier quota.
    sem = asyncio.Semaphore(_FREE_CONCURRENCY)

    tasks = [_extract_one(fc, r["url"], schema, sem) for r in rows]
    results = await asyncio.gather(*tasks)

    stats = {"processed": len(rows), "success": 0, "missing": 0, "failed": 0}

    async with pool.acquire() as conn:
        async with conn.transaction():
            for row, (status, parsed, err) in zip(rows, results):
                stats[status] += 1
                if parsed is not None:
                    category = (
                        SUBCATEGORY_TO_CATEGORY[parsed.subcategory]
                        if parsed.subcategory is not None
                        else None
                    )
                    await conn.execute(
                        """update products set
                             name            = coalesce($2, name),
                             subcategory     = coalesce($3, subcategory),
                             category        = coalesce($4, category),
                             description     = coalesce($5, description),
                             price           = coalesce($6, price),
                             ingredient_text = coalesce($7, ingredient_text),
                             scrape_status   = $8,
                             scrape_error    = null
                           where id = $1""",
                        row["id"],
                        parsed.name,
                        parsed.subcategory,
                        category,
                        parsed.description,
                        parsed.price,
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
