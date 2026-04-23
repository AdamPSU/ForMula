# ForMula Scraper — Functional Requirements & Decisions

## Functional Requirements

### FR-1: Pipeline stages are independent
Discovery (find product URLs) and Extraction (get data from a URL) are separate operations.
A failed extraction does not block discovery or other extractions.

### FR-2: Idempotency — upsert, never duplicate
Products are keyed on `url`. Re-running a scrape updates fields only when the new value is non-null.

### FR-3: Resumability — checkpointed progress
A job that dies midway resumes from the last successful URL. `scrape_status = 'pending'` rows
show exactly what remains.

### FR-4: Per-product extraction status
Each product row carries `scrape_status`:
- `pending` — discovered but not yet processed
- `success` — ingredient_text extracted and validated
- `missing` — page found, no ingredient block detectable (ingredient_text = NULL)
- `failed` — network error, parse error, timeout (retryable)
- `blocked` — bot detection / CAPTCHA (requires human intervention)

### FR-5: Ingredient validation
Extracted `ingredient_text` must contain ≥5 comma-separated tokens.
Fails check → store NULL, mark `missing`.

### FR-6: Null is a valid outcome
A product without a findable ingredient list is stored with `ingredient_text = NULL`.
Not skipped, not a failure.

### FR-7: Per-site config is a seed URL only
Each brand entry requires one field: `seed_url`. No CSS selectors, no URL filters, no regex.
Firecrawl crawls from the seed; the LLM determines if a page is a product page.

### FR-8: LLM-first extraction
Every page: Firecrawl renders → markdown → LLM extracts `{name, product_type, description,
ingredient_text}` verbatim. LLM must extract only — never generate or infer.

### FR-9: Retry with exponential backoff
Failed extractions are retried with exponential backoff up to N attempts.
After N failures, mark `failed` and continue.

### FR-10: Observability on scrape_jobs
`scrape_jobs` tracks `pages_found` and `pages_scraped`. Per-product status enables detailed
querying (`SELECT COUNT(*) ... GROUP BY scrape_status`).

---

## Executive Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Site scope | Brand-direct only | Simpler anti-scraping; retailers deferred |
| JS-gated ingredients | Store NULL / `missing` | Don't block MVP pipeline |
| Extraction strategy | LLM-first, no CSS selectors | Universal coverage; selectors break on redesign |
| Status granularity | Per-product `scrape_status` column | Enables per-URL retry and debugging |
| Agent model | claude-sonnet-4-6 | Orchestrating agent |
| Crawl limit | 500 pages per brand | Covers all known brand catalogs |
| DB driver | asyncpg (no ORM) | Bulk insert perf, async pipeline, simple schema |
| Supabase client | Not used on backend | asyncpg direct is sufficient |

---

## Open Decisions

- **Extraction LLM**: haiku-4-5 (~10x cheaper) vs sonnet-4-6 (same as agent) for per-page extraction?
