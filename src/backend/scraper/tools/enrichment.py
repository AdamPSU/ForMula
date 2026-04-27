"""Per-brand orchestrator for `run-and-finish`.

Replaces the prior agent-driven sequence of `run-extraction` (looped),
`tag-batch` (looped agent decisions), `generate-docs`, and `finish`.
The agent now invokes one CLI verb after staging — this module
consumes the staged products to completion, auto-tags any new INCI,
auto-generates rerank docs for the brand, and marks the job complete.

Early-abort: if the FIRST extraction batch returns no successes and
≥5 `missing` rows, park the brand (`active=false`) and mark the job
`failed`. Caps wasted spend at ~25 credits per dead brand vs. the 10
credits a passing preflight would have cost.
"""

from ..db import connection
from . import descriptions, ingredients, pipeline


_FIRST_BATCH_MISSING_THRESHOLD = 5
_ERROR_PREVIEW = 5  # Cap returned errors to keep agent context small.


def _cap_errors(stats: dict) -> dict:
    """Mutate `stats` in place: cap `errors` list to _ERROR_PREVIEW
    and surface a `total_errors` counter. Full detail lives in the
    pipeline's log files."""
    errs = stats.get("errors") or []
    stats["total_errors"] = len(errs)
    if len(errs) > _ERROR_PREVIEW:
        stats["errors"] = errs[:_ERROR_PREVIEW]
    return stats


async def _park_brand(brand_id: str) -> None:
    async with connection() as conn:
        await conn.execute(
            "update brands set active = false where id = $1::uuid",
            brand_id,
        )


async def _mark_job(job_id: str, status: str, error: str | None = None) -> None:
    async with connection() as conn:
        await conn.execute(
            """update scrape_jobs
               set status       = $2,
                   error        = coalesce($3, error),
                   completed_at = now()
               where id = $1::uuid""",
            job_id,
            status,
            error,
        )


async def _brand_id_for_job(job_id: str) -> str:
    async with connection() as conn:
        row = await conn.fetchrow(
            "select brand_id from scrape_jobs where id = $1::uuid",
            job_id,
        )
    if row is None:
        raise RuntimeError(f"unknown scrape_job: {job_id}")
    return str(row["brand_id"])


async def run_and_finish(job_id: str) -> dict:
    """End-to-end per-brand pipeline. Loops extraction, applies the
    early-abort park policy, then auto-fires ingredient tagging and
    rerank-doc generation for the brand. Returns aggregated stats."""
    brand_id = await _brand_id_for_job(job_id)

    extraction = {"processed": 0, "success": 0, "missing": 0, "failed": 0}
    aborted = False
    first_batch = True

    while True:
        batch = await pipeline.run_extraction(job_id)
        for k in extraction:
            extraction[k] += batch[k]
        if batch["processed"] == 0:
            break
        if first_batch:
            first_batch = False
            if (
                batch["success"] == 0
                and batch["missing"] >= _FIRST_BATCH_MISSING_THRESHOLD
            ):
                aborted = True
                await _park_brand(brand_id)
                await _mark_job(
                    job_id,
                    "failed",
                    f"early-abort: first batch produced 0 successes / "
                    f"{batch['missing']} no_inci_text=True rows",
                )
                break

    if aborted:
        return {
            "extraction": extraction,
            "aborted": True,
            "brand_parked": True,
            "tagging": None,
            "rerank_docs": None,
        }

    tagging = await ingredients.tag_unknowns_for_brand(brand_id)
    rerank_docs = await descriptions.generate_docs_for_brand(brand_id)

    await _mark_job(job_id, "complete")

    return {
        "extraction": extraction,
        "aborted": False,
        "brand_parked": False,
        "tagging": _cap_errors(tagging),
        "rerank_docs": _cap_errors(rerank_docs),
    }
