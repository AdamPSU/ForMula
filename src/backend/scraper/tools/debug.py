"""Debug & recovery tools: per-URL extraction, failure reset."""

from pydantic import ValidationError

from ..db import connection
from ..prompts import EXTRACT_PROMPT
from ..validation import ProductExtraction
from .pipeline import _client


async def inspect_product(url: str, full: bool = False) -> dict:
    fc = _client()
    schema = ProductExtraction.model_json_schema()
    formats: list = [{"type": "json", "prompt": EXTRACT_PROMPT, "schema": schema}]
    if full:
        formats.append("markdown")
    doc = await fc.scrape(url, formats=formats)
    data = getattr(doc, "json", None) or {}
    try:
        extraction = ProductExtraction(**data).model_dump()
    except ValidationError as ve:
        extraction = {"error": f"validation: {ve}", "raw": data}
    out: dict = {"extraction_attempt": extraction}
    if full:
        out["markdown"] = getattr(doc, "markdown", None)
    return out


async def retry_failed(job_id: str) -> dict:
    async with connection() as conn:
        tag = await conn.execute(
            """update products
               set scrape_status = 'pending', scrape_error = null
               where scrape_job_id = $1::uuid and scrape_status = 'failed'""",
            job_id,
        )
    # asyncpg returns e.g. "UPDATE 7" — parse the count
    try:
        reset = int(tag.split()[-1])
    except (ValueError, IndexError):
        reset = 0
    return {"reset": reset}


async def finish(job_id: str, summary: str) -> dict:
    async with connection() as conn:
        await conn.execute(
            """update scrape_jobs
               set status = 'complete', completed_at = now()
               where id = $1::uuid""",
            job_id,
        )
    return {"ok": True, "summary": summary}
