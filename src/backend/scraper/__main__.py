"""CLI dispatcher. Every subcommand maps 1:1 to an agent tool and prints JSON.

Run from `src/backend/`:
    uv run python -m scraper <subcommand> [--flag value ...]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .db import close
from .tools import (
    budget,
    catalog,
    debug,
    descriptions,
    filter as filter_tool,
    ingredients,
    pipeline,
)
from .validation import render_migration


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scraper")
    s = p.add_subparsers(dest="cmd", required=True)

    s.add_parser("list-brands")

    cb = s.add_parser("create-brand")
    cb.add_argument("--slug", required=True)
    cb.add_argument("--name", required=True)
    cb.add_argument("--website-url", required=True)
    cb.add_argument("--seed-url")

    ub = s.add_parser("update-brand")
    ub.add_argument("--brand-id", required=True)
    ub.add_argument("--seed-url")
    ub.add_argument("--active", choices=["true", "false"])

    csj = s.add_parser("create-scrape-job")
    csj.add_argument("--brand-id", required=True)

    usj = s.add_parser("update-scrape-job")
    usj.add_argument("--job-id", required=True)
    usj.add_argument("--status", required=True)
    usj.add_argument("--pages-found", type=int)
    usj.add_argument("--pages-scraped", type=int)
    usj.add_argument("--error")

    lp = s.add_parser("list-products")
    lp.add_argument("--job-id", required=True)
    lp.add_argument("--status")
    lp.add_argument("--limit", type=int, default=100)

    gjs = s.add_parser("get-job-stats")
    gjs.add_argument("--job-id", required=True)

    lsu = s.add_parser("list-site-urls")
    lsu.add_argument("--seed-url", required=True)
    lsu.add_argument("--out-file", required=True)
    lsu.add_argument("--search", default="hair products")
    lsu.add_argument("--limit", type=int, default=100)

    lpl = s.add_parser("list-page-links")
    lpl.add_argument("--url", required=True)
    lpl.add_argument("--out-file", required=True)

    fl = s.add_parser("filter-links")
    fl.add_argument("--urls-file", required=True)
    fl.add_argument("--keep-file", required=True)
    fl.add_argument("--skip-file", required=True)

    sp_cmd = s.add_parser("stage-products")
    sp_cmd.add_argument("--job-id", required=True)
    sp_cmd.add_argument("--brand-id", required=True)
    sp_cmd.add_argument("--urls-file", required=True)

    rx = s.add_parser("run-extraction")
    rx.add_argument("--job-id", required=True)
    rx.add_argument("--batch-size", type=int, default=50)

    s.add_parser("check-budget")

    ds = s.add_parser("dump-schema")
    ds.add_argument(
        "--target",
        choices=["products", "ingredients"],
        default="products",
    )

    lu = s.add_parser("list-untagged")
    lu.add_argument("--out-file", required=True)
    lu.add_argument("--limit", type=int)

    li = s.add_parser("lookup-ingredient")
    li.add_argument("--name", required=True)

    tb = s.add_parser("tag-batch")
    tb.add_argument("--file", required=True)

    s.add_parser("tag-status")

    lwd = s.add_parser("list-without-doc")
    lwd.add_argument("--out-file", required=True)
    lwd.add_argument("--limit", type=int)

    gd = s.add_parser("generate-docs")
    gd.add_argument("--in-file", required=True)

    s.add_parser("doc-status")

    ip = s.add_parser("inspect-product")
    ip.add_argument("--url", required=True)
    ip.add_argument(
        "--full",
        action="store_true",
        help="Also return raw page markdown (10-50K tokens). Use only when "
        "the structured extraction looks off and you want to read the page.",
    )

    rf = s.add_parser("retry-failed")
    rf.add_argument("--job-id", required=True)

    fn = s.add_parser("finish")
    fn.add_argument("--job-id", required=True)
    fn.add_argument("--summary", required=True)

    return p


async def _dispatch(args: argparse.Namespace):
    match args.cmd:
        case "list-brands":
            return await catalog.list_brands()
        case "create-brand":
            return await catalog.create_brand(
                args.slug, args.name, args.website_url, args.seed_url
            )
        case "update-brand":
            active = None if args.active is None else args.active == "true"
            return await catalog.update_brand(args.brand_id, args.seed_url, active)
        case "create-scrape-job":
            return await catalog.create_scrape_job(args.brand_id)
        case "update-scrape-job":
            return await catalog.update_scrape_job(
                args.job_id,
                args.status,
                args.pages_found,
                args.pages_scraped,
                args.error,
            )
        case "list-products":
            return await catalog.list_products(args.job_id, args.status, args.limit)
        case "get-job-stats":
            return await catalog.get_job_stats(args.job_id)
        case "list-site-urls":
            return await pipeline.list_site_urls(
                args.seed_url, args.out_file, args.search, args.limit
            )
        case "list-page-links":
            return await pipeline.list_page_links(args.url, args.out_file)
        case "filter-links":
            return await filter_tool.filter_links(
                args.urls_file, args.keep_file, args.skip_file
            )
        case "stage-products":
            return await pipeline.stage_products(args.job_id, args.brand_id, args.urls_file)
        case "run-extraction":
            return await pipeline.run_extraction(args.job_id, args.batch_size)
        case "check-budget":
            return await budget.check_budget()
        case "list-untagged":
            return await ingredients.list_untagged(args.out_file, args.limit)
        case "lookup-ingredient":
            return await ingredients.lookup_ingredient(args.name)
        case "tag-batch":
            return await ingredients.tag_batch(args.file)
        case "tag-status":
            return await ingredients.tag_status()
        case "list-without-doc":
            return await descriptions.list_without_doc(args.out_file, args.limit)
        case "generate-docs":
            return await descriptions.generate_docs(args.in_file)
        case "doc-status":
            return await descriptions.doc_status()
        case "inspect-product":
            return await debug.inspect_product(args.url, args.full)
        case "retry-failed":
            return await debug.retry_failed(args.job_id)
        case "finish":
            return await debug.finish(args.job_id, args.summary)
        case _:
            raise SystemExit(f"unknown command: {args.cmd}")


async def _run(args: argparse.Namespace) -> None:
    try:
        result = await _dispatch(args)
        print(json.dumps(result, default=str, indent=2))
    finally:
        await close()


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env.local")
    args = _build_parser().parse_args()
    # dump-schema prints raw SQL to stdout — it is meant to be piped into a
    # migration file, so it bypasses the JSON wrapper and skips DB init.
    if args.cmd == "dump-schema":
        print(render_migration(args.target))
        return
    try:
        asyncio.run(_run(args))
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
