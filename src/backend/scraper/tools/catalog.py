"""DB-facing tools: brands, jobs, product rows."""

from typing import Optional

from ..db import connection


async def list_brands(
    slug: Optional[str] = None,
    without_seed: bool = False,
) -> dict:
    """Default: tiny summary `{total, with_seed, without_seed}`.

    `--slug X` returns one full brand row (or null) for the agent to act on.
    `--without-seed` returns just the worklist of slugs needing discovery.
    """
    async with connection() as conn:
        if slug is not None:
            row = await conn.fetchrow(
                """select id, slug, name, website_url, seed_url, active
                   from brands where slug = $1""",
                slug,
            )
            if row is None:
                return {"brand": None}
            return {
                "brand": {
                    "id": str(row["id"]),
                    "slug": row["slug"],
                    "name": row["name"],
                    "website_url": row["website_url"],
                    "seed_url": row["seed_url"],
                    "active": row["active"],
                }
            }

        if without_seed:
            rows = await conn.fetch(
                """select id, slug, name, website_url from brands
                   where active and seed_url is null
                   order by slug"""
            )
            return {
                "count": len(rows),
                "brands": [
                    {
                        "id": str(r["id"]),
                        "slug": r["slug"],
                        "name": r["name"],
                        "website_url": r["website_url"],
                    }
                    for r in rows
                ],
            }

        counts = await conn.fetchrow(
            """select
                 count(*) filter (where active)                                  as total,
                 count(*) filter (where active and seed_url is not null)         as with_seed,
                 count(*) filter (where active and seed_url is null)             as without_seed,
                 count(*) filter (where not active)                              as parked
               from brands"""
        )
    return {
        "total": counts["total"],
        "with_seed": counts["with_seed"],
        "without_seed": counts["without_seed"],
        "parked": counts["parked"],
    }


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
) -> None:
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
) -> None:
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


_ERROR_TRUNCATE = 80


def _trunc_error(err: Optional[str]) -> Optional[str]:
    if err is None:
        return None
    return err if len(err) <= _ERROR_TRUNCATE else err[:_ERROR_TRUNCATE] + "…"


async def list_products(
    job_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    show_rows: bool = False,
) -> dict:
    """Default: status counts only `{job_id, status_counts, total}`.

    `--show-rows` returns the row list (id, url, status, truncated error)
    for inspection — costly on large jobs, so opt-in only.
    """
    async with connection() as conn:
        count_rows = await conn.fetch(
            """select scrape_status, count(*) as n
               from products
               where scrape_job_id = $1::uuid
               group by scrape_status""",
            job_id,
        )
        status_counts = {r["scrape_status"]: r["n"] for r in count_rows}

        if not show_rows:
            return {
                "job_id": job_id,
                "total": sum(status_counts.values()),
                "status_counts": status_counts,
            }

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
    return {
        "job_id": job_id,
        "total": sum(status_counts.values()),
        "status_counts": status_counts,
        "rows": [
            {
                "id": str(r["id"]),
                "url": r["url"],
                "scrape_status": r["scrape_status"],
                "scrape_error": _trunc_error(r["scrape_error"]),
            }
            for r in rows
        ],
    }


async def get_job_stats(job_id: str) -> dict:
    # Stub — will return per-status counts once wired up.
    return {"stub": True, "job_id": job_id}
