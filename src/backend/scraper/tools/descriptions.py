"""Rerank-doc generation — produce one positives-only YAML doc per
product for the runtime Cohere Rerank pass. Three subcommands wired
into `__main__.py`:

  list-without-doc → JSONL bundles for products needing generation
  generate-docs    → Grok call per row, render YAML, autocommit
  doc-status       → counts + sample rendered docs

Workflow lives in `scraper/references/RERANK-DOCS.md`.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from openai import AsyncOpenAI
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..db import connection
from ..prompts.rerank_doc import RERANK_DOC_PROMPT
from ..validation.models import RerankDocFacets
from .ingredients import _split_ingredient_text


# ─── Configuration ────────────────────────────────────────────────────

_MODEL = "grok-4-1-fast-reasoning"
_CONCURRENCY = 256
_MAX_ATTEMPTS = 5  # 1 initial + 4 retries with exp backoff (1/2/4/8s)
_LOG_PATH = Path(__file__).parent / "descriptions.log.txt"


# ─── Migration drift check ────────────────────────────────────────────


async def _check_columns_exist(conn) -> None:
    """Fail fast if the migration hasn't applied — both payload columns
    must exist on `products` before any LLM work."""
    rows = await conn.fetch(
        """select column_name from information_schema.columns
           where table_schema = 'public'
             and table_name   = 'products'
             and column_name in ('raw_doc', 'rerank_doc')"""
    )
    found = {r["column_name"] for r in rows}
    missing = {"raw_doc", "rerank_doc"} - found
    if missing:
        raise RuntimeError(
            f"products is missing columns {sorted(missing)}. "
            "Apply migration 20260426000000_product_rerank_doc.sql first."
        )


# ─── LLM ──────────────────────────────────────────────────────────────


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url="https://api.x.ai/v1",
    )


async def _llm_emit_facets(
    client: AsyncOpenAI, bundle: dict[str, Any]
) -> tuple[str, RerankDocFacets]:
    """One Grok call → validated RerankDocFacets. Retries on transient
    errors (5xx, validation failures) up to 5 attempts total with
    exponential backoff (1s/2s/4s/8s/16s).

    Returns (raw_json_string, parsed_facets).
    """
    schema = RerankDocFacets.model_json_schema()

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception_type((ValidationError, Exception)),
        reraise=True,
    ):
        with attempt:
            resp = await client.chat.completions.create(
                model=_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": RERANK_DOC_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Product:\n"
                            + json.dumps(bundle, indent=2, ensure_ascii=False)
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "RerankDocFacets",
                        "schema": schema,
                        "strict": True,
                    },
                },
            )
            raw = resp.choices[0].message.content or "{}"
            facets = RerankDocFacets.model_validate_json(raw)
            return raw, facets

    # tenacity reraise=True guarantees we never reach here, but mypy needs it
    raise RuntimeError("unreachable")


# ─── Renderer ─────────────────────────────────────────────────────────


def _render_yaml(
    facets: RerankDocFacets,
    row: dict[str, Any],
    ingredients: list[dict[str, str]],
) -> str:
    """Deterministic YAML doc. Key order matches the design spec; empty
    facet lists are omitted entirely (silence is positives-only-safe).

    Cohere truncates tail-first → high-signal facets first, full INCI
    list last.
    """
    # Mechanical fields from the row + scraped description (or LLM-gen)
    description = row.get("description") or facets.description
    ingredient_line = ", ".join(
        f"{ing['inci_name'].lower()} ({ing['function_tag']})" for ing in ingredients
    )

    doc: dict[str, Any] = {}
    doc["Category"] = row["category"]
    doc["Subcategory"] = row["subcategory"]
    if description:
        doc["Description"] = description
    if facets.hair_types:
        doc["Hair types"] = ", ".join(facets.hair_types)
    if facets.concerns_addressed:
        doc["Concerns addressed"] = ", ".join(facets.concerns_addressed)
    if facets.goals_served:
        doc["Goals served"] = ", ".join(facets.goals_served)
    if facets.scalp_fit:
        doc["Scalp fit"] = ", ".join(facets.scalp_fit)
    if facets.strand_thickness_fit:
        doc["Strand thickness fit"] = ", ".join(facets.strand_thickness_fit)
    if facets.density_fit:
        doc["Density fit"] = ", ".join(facets.density_fit)
    if facets.porosity_fit:
        doc["Porosity fit"] = ", ".join(facets.porosity_fit)
    if facets.climate_fit:
        doc["Climate fit"] = ", ".join(facets.climate_fit)
    if facets.routine_fit:
        doc["Routine fit"] = ", ".join(facets.routine_fit)
    if ingredient_line:
        doc["Ingredients"] = ingredient_line

    # sort_keys=False per Cohere's recommendation — key order matters
    # because long YAML strings get truncated tail-first.
    return yaml.dump(
        doc,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10**9,  # never wrap; one key per line
    )


# ─── Logging ──────────────────────────────────────────────────────────

_log_lock = asyncio.Lock()


async def _log_call(
    product_id: str,
    bundle: dict,
    raw: str | None,
    yaml_str: str | None,
    error: str | None = None,
) -> None:
    """Append one call's worth of debug data to log.txt under a lock so
    256 concurrent workers don't interleave entries."""
    ts = datetime.now(timezone.utc).isoformat()
    sep = "=" * 78
    lines = [
        f"\n{sep}",
        f"product_id: {product_id}",
        f"timestamp:  {ts}",
        sep,
        "INPUT BUNDLE:",
        json.dumps(bundle, indent=2, ensure_ascii=False),
    ]
    if raw is not None:
        lines += ["", "RAW LLM OUTPUT:", raw]
    if yaml_str is not None:
        lines += ["", "RENDERED YAML:", yaml_str]
    if error is not None:
        lines += ["", "ERROR:", error]
    lines += [""]
    async with _log_lock:
        with open(_LOG_PATH, "a") as f:
            f.write("\n".join(lines))


def _truncate_log() -> None:
    """Reset log.txt at the start of each run — discardable per project
    convention."""
    _LOG_PATH.write_text("")


# ─── Subcommands ──────────────────────────────────────────────────────


async def list_without_doc(out_file: str, limit: int | None) -> dict:
    """Write JSONL bundles for products that need rerank-doc generation.

    Each line is a fully self-contained input for the generator:
      {id, name, description, subcategory, category,
       ingredients: [{inci_name, function_tag}, ...]}

    The ingredients list is JOIN-ed against `ingredients` in label order,
    so the generator never re-queries the DB for tags.
    """
    async with connection() as conn:
        await _check_columns_exist(conn)
        product_rows = await conn.fetch(
            """select id, name, description, subcategory, category, ingredient_text
               from products
               where rerank_doc       is null
                 and ingredient_text  is not null
                 and scrape_status    = 'success'"""
        )
        ingredient_rows = await conn.fetch(
            "select inci_name, function_tags from ingredients"
        )

    tag_by_name: dict[str, str] = {}
    for r in ingredient_rows:
        tags = r["function_tags"] or []
        if tags:
            tag_by_name[r["inci_name"]] = tags[0]

    bundles: list[dict] = []
    for r in product_rows:
        tokens = _split_ingredient_text(r["ingredient_text"])
        ingredients: list[dict] = []
        seen: set[str] = set()
        for name in tokens:
            if name in seen:
                continue
            seen.add(name)
            tag = tag_by_name.get(name)
            if tag is None:
                # Unknown token — likely a footnote fragment / typo. Skip
                # rather than poison the rerank doc with `(other)`.
                continue
            ingredients.append({"inci_name": name, "function_tag": tag})
        if not ingredients:
            # Nothing tagged — can't produce a useful doc.
            continue
        bundles.append(
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r["description"],
                "subcategory": r["subcategory"],
                "category": r["category"],
                "ingredients": ingredients,
            }
        )

    written = bundles[:limit] if limit is not None else bundles

    out_path = Path(out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for b in written:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    return {
        "count": len(bundles),
        "written": len(written),
        "out_file": str(out_path),
        "sample_ids": [b["id"] for b in written[:5]],
    }


async def _process_one(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    bundle: dict,
) -> dict:
    """Process a single product: LLM call → render → autocommit. Returns
    {id, status, error?}. Logs every call to log.txt regardless of
    outcome."""
    pid = bundle["id"]
    async with sem:
        try:
            raw, facets = await _llm_emit_facets(client, bundle)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            await _log_call(pid, bundle, raw=None, yaml_str=None, error=err)
            return {"id": pid, "status": "failed", "error": err}

        try:
            yaml_str = _render_yaml(facets, bundle, bundle["ingredients"])
        except Exception as e:
            err = f"render: {type(e).__name__}: {e}"
            await _log_call(pid, bundle, raw=raw, yaml_str=None, error=err)
            return {"id": pid, "status": "failed", "error": err}

        try:
            async with connection() as conn:
                await conn.execute(
                    "update products set raw_doc = $1, rerank_doc = $2 where id = $3",
                    raw,
                    yaml_str,
                    bundle["id"],
                )
        except Exception as e:
            err = f"db: {type(e).__name__}: {e}"
            await _log_call(pid, bundle, raw=raw, yaml_str=yaml_str, error=err)
            return {"id": pid, "status": "failed", "error": err}

        await _log_call(pid, bundle, raw=raw, yaml_str=yaml_str)
        return {"id": pid, "status": "ok"}


async def generate_docs(in_file: str) -> dict:
    """Read JSONL bundles, fan out under Semaphore(256), autocommit per
    row. Failed rows append to `<in_file>.failed.jsonl` so they can be
    retried in isolation.
    """
    async with connection() as conn:
        await _check_columns_exist(conn)

    in_path = Path(in_file)
    failed_path = in_path.with_suffix(in_path.suffix + ".failed.jsonl")

    bundles: list[dict] = []
    with open(in_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            bundles.append(json.loads(line))

    if not bundles:
        return {"processed": 0, "succeeded": 0, "failed": 0, "failed_file": None}

    _truncate_log()
    client = _client()
    sem = asyncio.Semaphore(_CONCURRENCY)

    results = await asyncio.gather(
        *[_process_one(client, sem, b) for b in bundles]
    )

    succeeded = sum(1 for r in results if r["status"] == "ok")
    failed = [r for r in results if r["status"] == "failed"]
    failed_bundles = [b for b, r in zip(bundles, results) if r["status"] == "failed"]

    if failed_bundles:
        with open(failed_path, "w") as f:
            for b, r in zip(failed_bundles, [x for x in results if x["status"] == "failed"]):
                f.write(json.dumps({**b, "_error": r["error"]}, ensure_ascii=False) + "\n")

    return {
        "processed": len(results),
        "succeeded": succeeded,
        "failed": len(failed),
        "failed_file": str(failed_path) if failed else None,
        "log_file": str(_LOG_PATH),
    }


async def doc_status() -> dict:
    """Counts + 3 sample rendered docs for spot-checking."""
    async with connection() as conn:
        await _check_columns_exist(conn)
        total = await conn.fetchval(
            """select count(*) from products
               where ingredient_text is not null
                 and scrape_status   = 'success'"""
        )
        with_doc = await conn.fetchval(
            """select count(*) from products
               where rerank_doc       is not null
                 and ingredient_text  is not null
                 and scrape_status    = 'success'"""
        )
        samples = await conn.fetch(
            """select name, rerank_doc from products
               where rerank_doc is not null
               order by random()
               limit 3"""
        )

    return {
        "total_products_with_inci": total,
        "with_rerank_doc": with_doc,
        "without_rerank_doc": total - with_doc,
        "sample_docs": [
            {"name": r["name"], "rerank_doc": r["rerank_doc"]} for r in samples
        ],
    }
