"""DB-facing tools: brands, jobs, product rows."""

from typing import Optional

from ..db import connection


async def list_brands() -> list[dict]:
    async with connection() as conn:
        rows = await conn.fetch(
            """select id, slug, name, website_url, seed_url
               from brands where active order by name"""
        )
    return [
        {
            "id": str(r["id"]),
            "slug": r["slug"],
            "name": r["name"],
            "website_url": r["website_url"],
            "seed_url": r["seed_url"],
        }
        for r in rows
    ]


async def create_brand(
    slug: str,
    name: str,
    website_url: str,
    seed_url: Optional[str] = None,
) -> dict:
    async with connection() as conn:
        row = await conn.fetchrow(
            """insert into brands (slug, name, website_url, seed_url)
               values ($1, $2, $3, $4)
               returning id""",
            slug,
            name,
            website_url,
            seed_url,
        )
    return {"brand_id": str(row["id"])}


async def update_brand(
    brand_id: str,
    seed_url: Optional[str] = None,
    active: Optional[bool] = None,
) -> dict:
    async with connection() as conn:
        await conn.execute(
            """update brands
               set seed_url = coalesce($2, seed_url),
                   active   = coalesce($3, active)
               where id = $1::uuid""",
            brand_id,
            seed_url,
            active,
        )
    return {"ok": True}


async def create_scrape_job(brand_id: str) -> dict:
    async with connection() as conn:
        row = await conn.fetchrow(
            """insert into scrape_jobs (brand_id, status, started_at)
               values ($1::uuid, 'running', now())
               returning id""",
            brand_id,
        )
    return {"job_id": str(row["id"])}


async def update_scrape_job(
    job_id: str,
    status: str,
    pages_found: Optional[int] = None,
    pages_scraped: Optional[int] = None,
    error: Optional[str] = None,
) -> dict:
    terminal = status in ("complete", "failed")
    async with connection() as conn:
        await conn.execute(
            """update scrape_jobs
               set status        = $2,
                   pages_found   = coalesce($3, pages_found),
                   pages_scraped = coalesce($4, pages_scraped),
                   error         = coalesce($5, error),
                   completed_at  = case when $6 then now() else completed_at end
               where id = $1::uuid""",
            job_id,
            status,
            pages_found,
            pages_scraped,
            error,
            terminal,
        )
    return {"ok": True}


async def list_products(
    job_id: str, status: Optional[str] = None, limit: int = 100
) -> list[dict]:
    async with connection() as conn:
        if status:
            rows = await conn.fetch(
                """select id, url, scrape_status, scrape_error
                   from products
                   where scrape_job_id = $1::uuid and scrape_status = $2
                   order by url limit $3""",
                job_id,
                status,
                limit,
            )
        else:
            rows = await conn.fetch(
                """select id, url, scrape_status, scrape_error
                   from products
                   where scrape_job_id = $1::uuid
                   order by url limit $2""",
                job_id,
                limit,
            )
    return [
        {
            "id": str(r["id"]),
            "url": r["url"],
            "scrape_status": r["scrape_status"],
            "scrape_error": r["scrape_error"],
        }
        for r in rows
    ]


async def get_job_stats(job_id: str) -> dict:
    # Stub — will return per-status counts once wired up.
    return {"stub": True, "job_id": job_id}
