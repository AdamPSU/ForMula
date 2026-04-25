# Scraper Agent

Populate the `products` table by discovering each brand's products via
Firecrawl, extracting structured data, and storing results in Postgres.
Operate autonomously — plan, run, verify, recover, finish.

## Environment

Run from `src/backend/`. Each subcommand prints JSON; `--help` lists flags.

```bash
cd src/backend
uv run python -m scraper <subcommand> [--flag value ...]
```

## Commands

- `list-brands` — read brands from the DB (`id`, `slug`, `website_url`, `seed_url`, `active`).
- `create-brand` — insert a brand. `seed_url` is optional; fill it via `update-brand` once verified.
- `update-brand` — set `--seed-url` or toggle `--active true|false`. Used to record the verified index, or to park a brand that didn't preflight.
- `list-page-links` — same-domain product links from one index page. Writes URLs to `--out-file` (paginated calls dedupe into the same file). Returns `{count, out_file, sample}` — never the full URL list. 1 credit.
- `filter-links` — Grok classifier that drops tool / accessory / merch / sample / gift-card URLs before staging. Inputs: `--urls-file`, `--keep-file`, `--skip-file`. Returns `{kept, skipped, keep_file, skip_file, skip_buckets, sample_skips}`. 0 Firecrawl credits (one LLM call).
- `inspect-product` — single-URL JSON scrape. Returns `{extraction_attempt}` only — the structured `ProductExtraction` dump, including `no_inci_text` (LLM-set boolean: True if this URL did not yield a real INCI list, for any reason — wrong page type, image-only INCI, blocked, B2B no-disclosure). Used for preflight. 5 credits. Add `--full` to also return raw page markdown (10–50K tokens) — only when something looks off and you want to read the page yourself.
- `create-scrape-job` — start a job for a brand; returns `job_id`.
- `stage-products` — insert URLs (one per line, from a file) as `pending`. Idempotent.
- `check-budget` — live Firecrawl credit balance. Free.
- `run-extraction` — scrape all `pending` rows for a job. 5 credits/URL. Loop until none remain.
- `list-products` — read rows for a job, optionally filtered by status.
- `retry-failed` — reset `failed` → `pending`.
- `finish` — mark the job `complete`.
- `dump-schema` — print the DROP+ADD SQL for the `category` / `subcategory` CHECK constraints, derived from the Python enum state in `models.py`. Use when you change `SUBCATEGORY_TO_CATEGORY` or the category Literal: `uv run python -m scraper dump-schema > db/supabase/migrations/<ts>_sync_enums.sql`, then apply. `run-extraction` runs a drift check up front and refuses to start if Python and DB disagree — so you cannot burn credits on a mismatched schema.
- `list-site-urls` — fallback only. Ranks URLs across a domain by semantic relevance, writes to `--out-file`, returns `{count, out_file, sample}`. 1 credit. Use when the common index paths in step 3 all return empty / 404; on JS-rendered Shopify, parked landers, and wrong-TLD apexes it usually returns 1–3 URLs and discovery has to fall back to sitemap XML or `WebSearch` anyway.

## Happy path

1. `list-brands`. If the brand exists with a `seed_url`, skip to step 5.
2. **New brand only:** `create-brand --slug ... --name "..." --website-url
   <domain>` with **no** `--seed-url` yet. The brand lands in the DB
   immediately so we have a record of what we're investigating.
3. Pick a products-index URL by trying the common paths in order:
   `/collections/all`, `/shop`, `/products`, `/collections/shop-all`. If
   the brand is on Shopify, `/collections/all` is almost always the
   answer. If all common paths return empty/404, fall back to
   `list-site-urls --seed-url <domain> --out-file /tmp/<brand>-map.txt`
   (1 credit) or fetch `/sitemap_products_1.xml` / `/sitemap.xml`
   directly. See LESSONS for wrong-TLD, redirected, parked-lander, and
   brand-name-collision cases.
4. `list-page-links --url <candidate_index> --out-file /tmp/<brand>-links.txt`.
   If the page paginates (Shopify default 24/page), append `?limit=250`
   and re-run with the same `--out-file`, then iterate `?page=2`,
   `?page=3` until `count` plateaus. The tool dedupes into the file
   automatically; the printed `count` is the post-dedupe total. **The
   index page is the source of truth — never stage URLs from
   `list-site-urls` output.** Eyeball the `sample` field for URL-shape
   traps (relative-href 404s, imweb `?idx=N`, etc.).
5. `filter-links --urls-file /tmp/<brand>-links.txt --keep-file /tmp/<brand>-keep.txt --skip-file /tmp/<brand>-skip.json`.
   Grok partitions into `keep` (shampoos, conditioners, styling,
   treatments, oils, masks, hair perfumes) and `skip` (bundles, tools,
   accessories, merch, samples, gift cards) — skipped URLs have no
   recommendable INCI, so extracting them is pure credit waste; bundles
   skip because their constituent products appear separately. Scan
   `skip_buckets` and `sample_skips` for sanity, and spot-check the
   keep file for accessory tokens (towel/brush/comb) and generic-noun
   bundle slugs before proceeding (see LESSONS).
6. **Preflight** (see below). Probe URLs should come from `keep_file`,
   not the raw links file.
   - **Pass:** `update-brand --brand-id <id> --seed-url <verified_index>` to
     lock in the verified index, then continue.
   - **Fail:** `update-brand --brand-id <id> --active false` to park the
     brand (this domain doesn't extract; look for an alternative retailer
     later). Do **not** stage or run extraction. Stop.
7. `create-scrape-job --brand-id <id>` → `stage-products --job-id <jid>
   --brand-id <id> --urls-file /tmp/<brand>-keep.txt`.
8. `check-budget`. Confirm `remaining_credits ≥ 2 + probes × 5 + kept × 5`.
9. `run-extraction --job-id <jid>`. Loop until no pending rows remain.
10. `finish --job-id <jid> --summary "..."`.

## Preflight

- **Pick** 1–2 URLs likely to carry INCI: shampoo, conditioner, cream, mask,
  oil, serum, treatment. Avoid bundles, tools, and accessories (they return
  `no_inci_text=True` even when extraction is fine — they prove nothing).
- **Probe** each with `inspect-product --url <u>`. 5 credits each.
- **Read** `extraction_attempt.no_inci_text` — Firecrawl's LLM has decided
  whether this page yielded a real INCI list:
  - `False` → probe passes; `ingredient_text` is real INCI. Proceed.
  - `True` → no usable INCI (any reason: wrong page type, image-only,
    B2B login wall, Cloudflare block, marketing-callout-only). Try a
    different URL from the keep file.
- **Decision:** at least one probe with `no_inci_text=False` → continue
  with `update-brand --seed-url`. Two consecutive `no_inci_text=True`
  probes on different product URLs → park (`update-brand --active false`).
- **Escape hatch:** if `no_inci_text` looks wrong (e.g. you can see in
  `--full` markdown that there IS an INCI block Firecrawl missed), re-run
  with `--full` to read the raw page yourself. Costs no extra Firecrawl
  credits but adds 10–50K tokens. Last resort, not routine.

## Success & outcomes

**Extraction success bar** (used by preflight, `run-extraction` validation,
and abort rules): non-null `name` **and** `ingredient_text` with ≥5
comma-separated INCI tokens.

After `run-extraction`, each row is:

- `success` — meets the bar above.
- `missing` — extracted cleanly, INCI absent or under 5 tokens. Normal for
  tools, accessories, and JS-hidden panels. Not a bug.
- `failed` — network/timeout/validation error. Already retried 4× with
  backoff (honors `Retry-After` on 429). `retry-failed` resets to `pending`.

## Rate limits & budget

- **Firecrawl Standard** (100k credits / cycle): 50 concurrent + 500 req/min
  on `/scrape`. `run-extraction` enforces both internally (semaphore +
  sliding-window limiter) and preflights live credits against `pages × 5`.
  Don't raise the in-code limits without confirming a plan change.
- **Reserve formula:** `2 + probes × 5 + pages × 5`. Never hard-code a balance
  in this file — read it from `check-budget`.

## Lessons

After a real failure or user correction, append a bullet to
`references/LESSONS.md` before `finish`:

```
- **<short title>** — <what went wrong>. <what to do next time>.
```

Skip anything already documented here or obvious from tool output.

@references/LESSONS.md
