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
- `list-site-urls` — rank URLs across a domain by semantic relevance to a search term. 1 credit.
- `list-page-links` — same-domain product links from one index page. 1 credit.
- `inspect-product` — single-URL JSON scrape, used for preflight. 5 credits.
- `create-scrape-job` — start a job for a brand; returns `job_id`.
- `stage-products` — insert URLs (one per line, from a file) as `pending`. Idempotent.
- `check-budget` — live Firecrawl credit balance. Free.
- `run-extraction` — scrape all `pending` rows for a job. 5 credits/URL. Loop until none remain.
- `list-products` — read rows for a job, optionally filtered by status.
- `retry-failed` — reset `failed` → `pending`.
- `scrape-page` — debug: raw markdown of a URL.
- `finish` — mark the job `complete`.

## Happy path

1. `list-brands`. If the brand exists with a `seed_url`, skip to step 5.
2. **New brand only:** `create-brand --slug ... --name "..." --website-url
   <domain>` with **no** `--seed-url` yet. The brand lands in the DB
   immediately so we have a record of what we're investigating.
3. `list-site-urls --seed-url <domain>` → pick a products-index URL
   (`/collections/all`, `/shop`, etc.). If none in the top 100, retry with
   `--limit 500`.
4. `list-page-links --url <candidate_index>`. If the page paginates (Shopify
   default 24/page), append `?limit=250` and re-run, then iterate `?page=2`,
   `?page=3` until empty/stable. Concatenate and dedupe. **Never stage from
   `list-site-urls` output** — the index page is the source of truth.
5. **Preflight** (see below).
   - **Pass:** `update-brand --brand-id <id> --seed-url <verified_index>` to
     lock in the verified index, then continue.
   - **Fail:** `update-brand --brand-id <id> --active false` to park the
     brand (this domain doesn't extract; look for an alternative retailer
     later). Do **not** stage or run extraction. Stop.
6. `create-scrape-job --brand-id <id>` → write the links to
   `/tmp/<jid>-urls.txt` → `stage-products --job-id <jid> --brand-id <id>
   --urls-file /tmp/<jid>-urls.txt`.
7. `check-budget`. Confirm `remaining_credits ≥ 2 + probes × 5 + pages × 5`
   (~262 for a 50-product brand with 2 probes).
8. `run-extraction --job-id <jid>`. Loop until no pending rows remain.
9. `finish --job-id <jid> --summary "..."`.

## Preflight

- **Pick** 1–2 URLs likely to carry INCI: shampoo, conditioner, cream, mask,
  oil, serum, treatment. Avoid bundles, tools, and accessories (they return
  `missing` even when extraction is fine — they prove nothing).
- **Probe** each with `inspect-product --url <u>`. 5 credits each.
- **Pass:** `extraction_attempt` meets the extraction success bar (below).
- **Decision:** if any probe passes, continue. If none pass, stop and park the brand per step 5.

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

- **Firecrawl Free:** 2 concurrent + 10 req/min on `/scrape`. `run-extraction`
  enforces both internally (semaphore + sliding-window limiter) and preflights
  live credits against `pages × 5`. Don't raise limits without a plan upgrade.
- **Reserve formula:** `2 + probes × 5 + pages × 5`. Never hard-code a balance
  in this file — read it from `check-budget`.

## Lessons

After a real failure or user correction, append a bullet to `LESSONS.md`
before `finish`:

```
- **<short title>** — <what went wrong>. <what to do next time>.
```

Skip anything already documented here or obvious from tool output.

@LESSONS.md
