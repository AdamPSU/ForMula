"""Per-brand discovery orchestrator for `discover-and-stage`.

Bundles the previously-separate happy-path ticks (list-page-links,
filter-links, update-brand --seed-url, create-scrape-job,
stage-products) into one CLI call, and walks ?page=1..N pagination
internally so the agent doesn't manage pagination by hand.

After this returns successfully the brand's `seed_url` is written
(extraction has already proven the URL serves real product links), so
re-investigating the same brand later — even if the eventual scrape
fails — won't redo the discovery work.
"""

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ..db import connection
from . import catalog, filter as filter_tool, pipeline


_TMP_DIR = Path("/tmp/scraper")


def _paginate_url(url: str, page: int) -> str:
    """Replace `page` query param with the given value, preserving the
    rest of the URL (including `?limit=250` etc. that the agent set)."""
    parts = urlparse(url)
    qs = dict(parse_qsl(parts.query, keep_blank_values=True))
    qs["page"] = str(page)
    return urlunparse(parts._replace(query=urlencode(qs)))


async def discover_and_stage(
    brand_id: str,
    index_url: str,
    max_pages: int = 5,
) -> dict:
    """List products from `index_url` (paginating ?page=2..max_pages
    until the count plateaus), Grok-filter the URL list, set the brand's
    `seed_url` to the verified index, create a scrape job, and stage the
    keep set. Returns one consolidated result the agent can hand to
    `run-and-finish`.

    `index_url` can already include query params (e.g. `?limit=250`);
    the paginator only sets/replaces the `page` key.
    """
    async with connection() as conn:
        brand = await conn.fetchrow(
            "select slug from brands where id = $1::uuid",
            brand_id,
        )
    if brand is None:
        raise RuntimeError(f"unknown brand_id: {brand_id}")
    slug = brand["slug"]

    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    links_file = str(_TMP_DIR / f"{slug}-links.txt")
    keep_file = str(_TMP_DIR / f"{slug}-keep.txt")
    skip_file = str(_TMP_DIR / f"{slug}-skip.json")
    # Clear prior link cache so a re-run starts clean (filter + stage
    # already dedupe, but a stale links file would inflate `discovered`).
    Path(links_file).unlink(missing_ok=True)

    prior_count = 0
    pages_fetched = 0
    for page in range(1, max_pages + 1):
        page_url = index_url if page == 1 else _paginate_url(index_url, page)
        result = await pipeline.list_page_links(page_url, links_file)
        pages_fetched += 1
        if result["count"] == prior_count:
            # No new URLs on this page → catalog exhausted.
            break
        prior_count = result["count"]

    if prior_count == 0:
        return {
            "brand_id": brand_id,
            "slug": slug,
            "pages_fetched": pages_fetched,
            "links_discovered": 0,
            "job_id": None,
            "staged": 0,
            "error": "no links discovered from index_url",
        }

    filter_result = await filter_tool.filter_links(links_file, keep_file, skip_file)

    job = await catalog.create_scrape_job(brand_id)
    job_id = job["job_id"]

    stage = await pipeline.stage_products(job_id, brand_id, keep_file)

    # Only persist seed_url when staging actually produced something.
    # Filter can drop every URL (e.g. /collections/all returned just the
    # homepage, JS-rendered pages with no real product anchors); locking
    # in a URL that yields zero rows means `list-brands --without-seed`
    # will silently skip the brand on future passes.
    if stage["staged"] > 0:
        await catalog.update_brand(brand_id, seed_url=index_url)

    return {
        "brand_id": brand_id,
        "slug": slug,
        "pages_fetched": pages_fetched,
        "links_discovered": prior_count,
        "job_id": job_id,
        "kept": filter_result["kept"],
        "skipped": filter_result["skipped"],
        "skip_buckets": filter_result["skip_buckets"],
        "sample_skips": filter_result["sample_skips"],
        "staged": stage["staged"],
        "seed_url_set": stage["staged"] > 0,
    }
