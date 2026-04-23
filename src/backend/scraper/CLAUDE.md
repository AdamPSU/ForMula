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

## Happy path

There are two flows. Always start with `list-brands` to see which applies.

### A. Onboarding — brand not yet in the DB (no verified seed_url)

Verify the seed **before** creating the brand. Nothing hits the DB until the
index is proven to return product URLs.

```
list-site-urls --seed-url <domain> [--search "hair products"] [--limit 100]
  │ read the ranked list, pick a products-index URL (collections/shop/all-products page)
  │ if nothing looks like an index in the top 100, re-run with --limit 500
→ list-page-links --url <candidate_index>
  │ verify the returned links look like individual product URLs
  │ if the links are clearly not products, repick from list-site-urls output
  │ if the page paginates, see "Pagination" below
→ create-brand --slug <s> --name <n> --website-url <domain> --seed-url <verified_index>
→ create-scrape-job --brand-id <id>
→ (write the verified links from list-page-links to /tmp/<job>-urls.txt)
→ stage-products --job-id <jid> --brand-id <id> --urls-file /tmp/<job>-urls.txt
→ check-budget
  │ confirm remaining_credits ≥ pages_found × 5 before proceeding
→ run-extraction --job-id <jid>     (loop until no pending rows remain)
→ finish --job-id <jid> --summary "..."
```

### B. Routine — brand already has a verified seed_url

```
list-brands                                      (read {id, seed_url})
→ create-scrape-job --brand-id <id>
→ list-page-links --url <brand.seed_url>         (catches new products)
→ (write the links to /tmp/<job>-urls.txt)
→ stage-products --job-id <jid> --brand-id <id> --urls-file /tmp/<job>-urls.txt
→ check-budget
  │ confirm remaining_credits ≥ pages_found × 5 before proceeding
→ run-extraction --job-id <jid>
→ finish --job-id <jid> --summary "..."
```

**There is no shortcut.** Do not stage URLs directly from `list-site-urls`
output — always route through `list-page-links` on an index page first. The
extra Firecrawl credit is insurance against wasting 5 credits per false positive.

**`seed_url` is the verified products-index URL** (e.g. `/collections/all`,
`/collections/frontpage`, `/shop`) — **not** the domain root. `website_url`
holds the domain. Never create a brand without a verified seed.

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
JSON format extracts `{name, subcategory, description, price, ingredient_text}` in
one call. Validates INCI (≥5 comma-separated tokens), upserts with final
`scrape_status`. Retries transient errors with exponential backoff (4 attempts).
On `RateLimitError` (429), honors the server's `Retry-After` header when
present. Preflights Firecrawl credits before the batch and raises if the
balance is below `len(batch) × 5`. **Call repeatedly until no pending rows
remain.**

### Budget

| Subcommand     | Flags | Returns                                                                           |
| -------------- | ----- | --------------------------------------------------------------------------------- |
| `check-budget` | —     | `{remaining_credits, plan_credits, billing_period_start, billing_period_end}`     |

Hits Firecrawl's live credit-usage endpoint. Free itself. Run this **before
every** `run-extraction` and whenever you plan to move to another brand.

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

### Current plan & rate limits

- **Firecrawl Free tier** — 2 concurrent + 10 req/min on `/scrape`.
- `run-extraction` enforces both quotas independently:
  - `Semaphore(2)` caps in-flight parallelism.
  - A module-level sliding-window limiter caps requests at 10 per 60s, so
    a burst of fast responses cannot self-trigger 429s.
- On `RateLimitError` it sleeps for `Retry-After` seconds if the header is
  present; otherwise falls back to 10/20/40/60s across 4 attempts.
- Do not raise any of these unless the plan is upgraded.

### Budget awareness

- A typical 50-product brand costs ~252 credits
  (1 map + 1 index + 50 × 5 extract).
- Source of truth for remaining credits is the `check-budget` tool, not this
  file. Never hard-code a balance here — it decays the moment anyone scrapes.
- `run-extraction` preflights the live balance against `len(batch) × 5` and
  raises if insufficient. That's the hard stop; `check-budget` is for planning
  across brands.

### Rate limits (reference, by plan)

- Free: 2 concurrent + 10 req/min
- Hobby: 5 concurrent + 100 req/min
- Standard: 50 concurrent + 500 req/min

## Lessons update protocol

After any user correction, unexpected failure, or non-obvious insight
discovered during a run, append a bullet to `LESSONS.md` before calling
`finish`. Format:

`- **<short title>** — <what went wrong>. <what to do next time>.`

Do **not** add bullets for things already documented in this CLAUDE.md or
obvious from tool output. Lessons are for recurring pitfalls only.

@LESSONS.md
