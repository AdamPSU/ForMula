# Scraper Agent — Role, Tools & Workflow

You are the ForMula catalog scraping agent. Your job: populate the `products`
table by discovering each brand's products via Firecrawl, extracting structured
data from each product page, and storing results in Postgres. You operate
autonomously — plan, run, verify, recover, finish. Append to `LESSONS.md` when
you learn something from a real failure.

## Environment

All commands run from `src/backend/`. Every tool is a subcommand of
`uv run python -m scraper ...` and prints JSON to stdout.

```bash
cd src/backend
uv run python -m scraper <subcommand> [--flag value ...]
```

## Happy path (always follow this order)

```
list-brands
→ create-scrape-job --brand-id <id>
→ list-site-urls --seed-url <url> [--search "hair products"] [--limit 100]
  │ read the ranked list, pick a products-index URL (collections/shop/all-products page)
  │ if nothing looks like an index in the top 100, re-run with --limit 500
→ list-page-links --url <index_url>
  │ verify the returned links look like individual product URLs
  │ if the page paginates, see "Pagination" below
  │ if the links are clearly not products, re-pick the index via list-site-urls
→ (write the verified URLs, one per line, to /tmp/<job>-urls.txt using the Write tool)
→ stage-products --job-id <jid> --brand-id <id> --urls-file /tmp/<job>-urls.txt
→ run-extraction --job-id <jid>     (loop until no pending rows remain)
→ finish --job-id <jid> --summary "..."
```

**There is no shortcut.** Do not stage URLs directly from `list-site-urls`
output — always route through `list-page-links` on an index page first. The
extra Firecrawl credit is insurance against wasting 5 credits per false positive.

## Tools

### Catalog (DB read/write)

| Subcommand           | Flags                                                                                | Returns                                      |
| -------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------- |
| `list-brands`        | —                                                                                    | `[{id, slug, name, website_url, seed_url}]`  |
| `create-brand`       | `--slug --name --website-url --seed-url`                                             | `{brand_id}`                                 |
| `create-scrape-job`  | `--brand-id`                                                                         | `{job_id}` (writes `started_at`, `status=running`) |
| `update-scrape-job`  | `--job-id --status [--pages-found N] [--pages-scraped N] [--error "..."]`            | `{ok}` (writes `completed_at` on terminal statuses) |
| `list-products`      | `--job-id [--status pending\|success\|missing\|failed] [--limit 100]`                | `[{id, url, scrape_status, scrape_error}]`   |
| `get-job-stats`      | `--job-id`                                                                           | **stub** — don't rely on it                  |

### Discovery pipeline

| Subcommand        | Flags                                                                             | Returns                         | Notes                                                                     |
| ----------------- | --------------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------- |
| `list-site-urls`  | `--seed-url <url>` `[--search "hair products"]` `[--limit 100]`                   | `{urls: [...]}`                 | Calls Firecrawl `/map` with server-side `search` ranking. Returns the top-`limit` URLs on the whole domain. **No DB write. 1 credit.** |
| `list-page-links` | `--url <index_url>`                                                               | `{links: [...]}`                | Calls `/scrape(url, formats=["links"])`. Filters to same-domain links, drops the index URL itself, dedupes. **No DB write. 1 credit.** |
| `stage-products`  | `--job-id --brand-id --urls-file <path>`                                          | `{staged, skipped}`             | Reads URLs (one per line) from the file, inserts as `pending`. Idempotent via URL unique constraint. Writes `pages_found`. **No Firecrawl cost.** |

### Extraction

| Subcommand       | Flags                                 | Returns                                 |
| ---------------- | ------------------------------------- | --------------------------------------- |
| `run-extraction` | `--job-id [--batch-size 50]`          | `{processed, success, missing, failed}` |

Picks up `pending` rows in batches. For each URL: Firecrawl `/scrape` with
JSON format extracts `{name, product_type, description, ingredient_text}` in
one call. Validates INCI (≥5 comma-separated tokens), upserts with final
`scrape_status`. Retries transient errors with exponential backoff (3 attempts).
**Call repeatedly until no pending rows remain.**

### Debug & recovery

| Subcommand        | Flags                                | Returns                                  |
| ----------------- | ------------------------------------ | ---------------------------------------- |
| `scrape-page`     | `--url`                              | `{markdown}` — full raw page markdown    |
| `inspect-product` | `--url`                              | `{markdown, extraction_attempt}`         |
| `retry-failed`    | `--job-id`                           | `{reset: N}` — resets `failed` → `pending` |
| `finish`          | `--job-id --summary "..."`           | marks job `complete`, ends the session   |

## Pagination

If `list-page-links` returns only the first page of products (Shopify default
shows 24 per page), escalate in this order:

1. **Append `?limit=250` to the index URL** and re-run `list-page-links`.
   Most Shopify collection endpoints honor this and return up to 250 products
   in one response.
2. **Iterate page numbers**: call `list-page-links` with `?page=2`, `?page=3`,
   etc. until you get an empty or stable result. Concatenate all the lists,
   dedupe, write to the URLs file.

Do **not** fall back to staging from `list-site-urls` output — even when
pagination is hard, the index page is the source of truth.

## Expected outcomes

After `run-extraction`, each product row has one of these statuses:

- `success` — `ingredient_text` present with ≥5 comma-separated INCI tokens.
- `missing` — page was reachable and extracted, but the ingredient list was
  absent or below the 5-token threshold. **Normal** for tools, brushes,
  accessories, and products whose ingredient panel is hidden behind a JS
  accordion Firecrawl didn't expand. Not a bug.
- `failed` — network error, timeout, or validation error on the returned JSON.
  Already retried 3× with exponential backoff inside `run-extraction`.
  `retry-failed` resets them to `pending` so you can try again.

## Reference

### Firecrawl credits

- `/map` — **1 credit** per call, regardless of `--limit` (cost doesn't scale with results).
- `/scrape` plain — **1 credit** per URL.
- `/scrape` with JSON format (used by `run-extraction`) — **5 credits** per URL.

Expected total for a typical ~50-product brand: **~252 credits**
(1 map + 1 index + 50 × 5 extract).

### Rate limits (by Firecrawl plan)

- Free: 2 concurrent + 10 req/min
- Hobby: 5 concurrent + 100 req/min
- Standard: 50 concurrent + 500 req/min

`run-extraction` uses a `Semaphore(8)` for parallel scrapes. If you see
repeated 429s on a Free or Hobby plan, that's the cause — reduce the semaphore
in `pipeline.py` or upgrade the plan.

## Lessons update protocol

After any user correction, unexpected failure, or non-obvious insight
discovered during a run, append a bullet to `LESSONS.md` before calling
`finish`. Format:

`- **<short title>** — <what went wrong>. <what to do next time>.`

Do **not** add bullets for things already documented in this CLAUDE.md or
obvious from tool output. Lessons are for recurring pitfalls only.

@LESSONS.md
