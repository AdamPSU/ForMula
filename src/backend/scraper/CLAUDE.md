# Scraper Agent

Populate the `products` table by discovering each brand's products via
Firecrawl, extracting structured data, and storing results in Postgres.
Operate autonomously — plan, run, verify, recover, finish.

## Environment

Run from `src/backend/`. Each subcommand prints JSON; `--help` lists flags.

```bash
cd src/backend
env -u VIRTUAL_ENV uv run python -m scraper <subcommand> [--flag value ...]
```

The `env -u VIRTUAL_ENV` prefix suppresses uv's warning about a stale
`VIRTUAL_ENV` shell variable that points at a non-project venv. uv
falls back to `.venv` correctly either way; the prefix just stops the
warning line from landing in your output every call.

## Context discipline

Default to the slim view. Every CLI verb returns minimum-viable output
by default; expansion flags (`--slug`, `--without-seed`, `--show-rows`)
exist for when you're genuinely stuck. Don't reach for them
preemptively — start with the counts/sample fields, and only widen the
view when the slim output leaves a real question unanswered. Same rule
for Firecrawl: `list-page-links` and `list-site-urls` already write the
full URL list to a file and return only `{count, sample}` — don't `cat`
the file unless the sample reveals a problem you actually need to debug.
Reading 40 KB to confirm "looks normal" is wasted context that compounds
across every brand in the loop.

## Commands

- `list-brands` — by default returns just `{total, with_seed, without_seed, parked}`. Use `--slug X` for one brand's full row (id/slug/name/website_url/seed_url/active), or `--without-seed` for the discovery worklist (`{count, brands:[{id,slug,name,website_url}]}`).
- `create-brand` — insert a brand. `seed_url` is optional; fill it via `update-brand` once the index is verified by a successful `run-and-finish`.
- `update-brand` — set `--seed-url` or toggle `--active true|false`. Used to record the verified index, or to park a brand the operator decides upfront has no DTC catalog.
- `list-page-links` — same-domain product links from one index page. Writes URLs to `--out-file` (paginated calls dedupe into the same file). Returns `{count, out_file, sample}` — never the full URL list. 1 credit.
- `filter-links` — Grok classifier that drops tool / accessory / merch / sample / gift-card URLs before staging. Inputs: `--urls-file`, `--keep-file`, `--skip-file`. Returns `{kept, skipped, keep_file, skip_file, skip_buckets, sample_skips}`. 0 Firecrawl credits (one LLM call).
- `create-scrape-job` — start a job for a brand; returns `job_id`.
- `stage-products` — insert URLs (one per line, from a file) as `pending`. Idempotent.
- `check-budget` — live Firecrawl credit balance. Free.
- `discover-and-stage` — `--brand-id X --index-url Y [--max-pages 5]`. Bundles `list-page-links` (paginated ?page=2..N until count plateaus), `filter-links` (Grok keep/skip), `update-brand --seed-url`, `create-scrape-job`, and `stage-products` into one call. Returns `{brand_id, slug, job_id, pages_fetched, links_discovered, kept, skipped, skip_buckets, sample_skips, staged}`. The `seed_url` is persisted as soon as the index returns links — re-running the same brand later won't redo discovery. Use this for the happy path; reach for the individual verbs only when discovery needs a non-standard pre-step (sitemap fallback, multi-axis union, etc.).
- `run-and-finish` — drain the staged batch through extraction (5 credits/URL, retried internally), auto-tag any new INCI introduced by this brand's products, auto-generate rerank docs for the brand's successful rows, and mark the job complete. Returns `{extraction, aborted, brand_parked, tagging, rerank_docs}`. **Early-abort:** if the first batch returns 0 successes and ≥5 `no_inci_text=True` rows, the brand is parked (`active=false`) and the job marked `failed` — caps wasted spend at ~25 credits per dead brand.
- `list-products` — by default returns `{job_id, total, status_counts}`. Pass `--show-rows` (with optional `--status X`, `--limit N`) to include the row list (id/url/status/error truncated to 80 chars) for inspection.
- `retry-failed` — reset `failed` → `pending`. Re-run `run-and-finish` afterwards to retry.
- `dump-schema` — print the DROP+ADD SQL for the `category` / `subcategory` / `function_tags` CHECK constraints, derived from the Python enum state in `models.py`. Use when you change `SUBCATEGORY_TO_CATEGORY`, the category Literal, or `FunctionTag`: `uv run python -m scraper dump-schema [--target products|ingredients] > db/supabase/migrations/<ts>_sync_enums.sql`, then apply. `run-and-finish` runs a drift check up front and refuses to start if Python and DB disagree — so you cannot burn credits on a mismatched schema.
- `list-site-urls` — fallback only. Ranks URLs across a domain by semantic relevance, writes to `--out-file`, returns `{count, out_file, sample}`. 1 credit. Use when the common index paths fail; on JS-rendered Shopify, parked landers, and wrong-TLD apexes it usually returns 1–3 URLs and discovery has to fall back to sitemap XML or `WebSearch` anyway.

## Happy path

1. `list-brands --without-seed` to grab the discovery worklist (every active brand with no `seed_url`, returned with id/slug/name/website_url). For one-off work on a known brand, `list-brands --slug X`; if `seed_url` is already set, skip to step 4.
2. **New brand only:** `create-brand --slug ... --name "..." --website-url <domain>` with **no** `--seed-url` yet (locked in by step 3 on success).
3. Pick a products-index URL by trying common paths in order: `/collections/all?limit=250` (Shopify default), `/shop`, `/products`, `/collections/shop-all`. If all return empty/404, fall back to `list-site-urls --seed-url <domain> --out-file /tmp/<brand>-map.txt` (1 credit) or fetch `/sitemap_products_1.xml` / `/sitemap.xml` directly. See LESSONS for wrong-TLD, redirected, parked-lander, brand-name-collision, and marketing-only-apex cases.
4. `discover-and-stage --brand-id <id> --index-url <picked_index>`. One call paginates the index, Grok-filters out tools/accessories/bundles, persists the verified `seed_url`, opens a job, and stages the keep set. Returns `{job_id, kept, skipped, skip_buckets, sample_skips, staged}`. Eyeball `skip_buckets` and `sample_skips` for sanity (LESSONS covers known classifier slips on accessory tokens and generic-noun bundle slugs). If `error: "no links discovered"` comes back, the index URL was wrong — go back to step 3 with a different path.
5. `check-budget`. Confirm `remaining_credits ≥ staged × 5`.
6. `run-and-finish --job-id <jid>`. Drains extraction, tags any new INCI, generates rerank docs, marks the job complete. On `aborted=true` + `brand_parked=true` the brand failed the first-batch INCI threshold — investigate or move on.

For brands that need pre-discovery handling (multi-axis union, sitemap-only catalogs, imweb `?idx=` extraction), use the lower-level `list-page-links` + `filter-links` + `create-scrape-job` + `stage-products` chain directly, then call `run-and-finish` as usual.

## Pacing & parallelism

`run-and-finish` is the only expensive verb (Firecrawl extraction +
tagging Grok + rerank-doc Grok, typically 30s–5min per brand). Don't
sit idle while it runs:

- **Always background `run-and-finish`** (`Bash` with `run_in_background: true`). The system fires a notification when it completes — don't poll, don't sleep, don't `wait`.
- **While one extraction runs**, do `discover-and-stage` for the next 1–3 brands in the foreground. Discovery is cheap (~1–5 credits, ~10s wallclock per brand) and never blocks the in-flight extraction.
- **Cap at ~2 concurrent `run-and-finish`** processes. Firecrawl's 50-concurrent and 500/min limits are enforced per-process by the local Semaphore + sliding-window limiter, so two parallel runs will momentarily exceed the 50-concurrent ceiling and earn some 429s — the retry/backoff path absorbs them with ~30–60s of slowdown on a few requests. Three or more parallel pushes the 429 rate high enough that throughput drops below the two-parallel case.
- **Cheap verbs** (`list-brands`, `check-budget`, `list-products`, `list-page-links`, `filter-links`, `update-brand`, `discover-and-stage`, `retry-failed`) never block extractions and can fire in the foreground at any time.
- **When you DO need to wait** for a background task with no other work to do, wait for the notification — never sleep on a guess.

The dispatch loop you should be running across the 124-brand worklist:

1. Pick the next brand from `list-brands --without-seed`.
2. Pick the index URL (the common `/collections/all?limit=250`, `/shop`, etc.).
3. `discover-and-stage` (foreground, cheap).
4. `run-and-finish --job-id <jid>` in the **background**.
5. Immediately go back to step 1 for the next brand. When you've launched the second background run-and-finish, hold off on the third until one of the in-flight notifications lands; in the meantime keep doing discoveries for brands waiting their turn.

## Success & outcomes

**Extraction success bar:** non-null `name` **and** `ingredient_text`
with ≥5 comma-separated INCI tokens. Set inside `run-and-finish`'s
extraction loop and used by both the success counter and the
early-abort check.

After `run-and-finish` returns, each row is:

- `success` — meets the bar above.
- `missing` — extracted cleanly, INCI absent or under 5 tokens. Normal for
  tools, accessories, and JS-hidden panels. Not a bug.
- `failed` — network/timeout/validation error. Already retried 4× with
  backoff (honors `Retry-After` on 429). `retry-failed` resets to `pending`,
  then re-run `run-and-finish` to retry.

## Rate limits & budget

- **Firecrawl Standard** (100k credits / cycle): 50 concurrent + 500 req/min
  on `/scrape`. The extraction loop enforces both internally (semaphore +
  sliding-window limiter) and preflights live credits against `pages × 5`.
  Don't raise the in-code limits without confirming a plan change.
- **Reserve formula:** `pages × 5`. Never hard-code a balance in this
  file — read it from `check-budget`.

## Lessons

After a real failure or user correction, append a bullet to
`references/LESSONS.md` before moving on:

```
- **<short title>** — <what went wrong>. <what to do next time>.
```

Skip anything already documented here or obvious from tool output.

@references/LESSONS.md
