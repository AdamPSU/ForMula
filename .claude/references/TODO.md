# Reranking — feature plan

The active in-flight feature. Update this file as the plan firms up; the
root `CLAUDE.md` references it.

## User flow we are building toward

1. User says "I want a leave-in conditioner" (free-text into the prompt box).
2. Backend translates free-text → parameterized SQL against `products`,
   validates via AST, executes. Expected: ~5,000 → ~150–2,000 rows
   (highly variable: "shampoo or conditioner" → ~1,990;
   "leave-in conditioner" → ~309).
3. Backend takes the user's `HairProfile` and ranks the candidates by
   ingredient fit using a reranking model. Expected: → top ~150.
4. Return ranked list. Stop. (Per-product judge-scoring with `judge.txt`
   is a later milestone, not part of this feature.)

## Already shipped

- **Auth + `public.profiles`** (2026-04-25). Email/password via
  `@supabase/ssr`; whole app gated. All user-owned tables FK to
  `public.profiles(id)`.
- **`HairProfile` + `hair_intakes`.** `src/backend/profiles/`:
  Pydantic `HairProfile` (`models.py`), asyncpg `insert_hair_intake` /
  `get_latest_hair_profile` (`repository.py`), `POST`/`GET
  /me/hair-profile` (`api.py`), migration
  `20260425010000_hair_intakes.sql` (append-only quiz history, RLS
  owner-only).
- **sql_filter v3** (`src/backend/ai/rerank/sql_filter/`). LangGraph
  workflow: writer LLM (Grok-4-fast) emits `{sql, params}`,
  AST-validated by sqlglot against an allowlist (tables `products` +
  `brands`, columns excl. `ingredient_text`, mandatory
  `scrape_status='success'`), executed via the pooled asyncpg conn.
  Failure (AST or DB) feeds the verbatim error back to the writer for
  rewrite — cap 3 attempts. Refusal pattern: `WHERE ... AND false` →
  200 / count=0. `POST /filter` is JWT-gated.
- **Frontend → /filter wiring.** Prompt box on the home page POSTs to
  `/filter` with the Supabase JWT and `console.log`s the response. No
  rendering / loading / error UI yet — backend-only by design.
- **Ingredient tagging** (2026-04-25/26). All 6,929 unique INCI in
  `products` tagged into `ingredients.function_tags` via the
  `scraper/tools/ingredients.py` workflow (autonomous Claude Code
  agent, Firecrawl-backed `lookup-ingredient` for genuinely unknown
  rows). 31-tag closed enum on `FunctionTag`; CHECK constraint enforced
  by migration `20260425020000_ingredient_function_tags_v2.sql`.
- **Rerank doc generation** (2026-04-26). Per-product YAML doc
  optimized for Cohere Rerank 4 — positives-only, HairProfile-aligned,
  with the full INCI list and function tags. Two new payload columns
  on `products`: `raw_doc` (LLM JSON output) and `rerank_doc`
  (rendered YAML). Pipeline at `scraper/tools/descriptions.py`:
  Grok-4-fast (`temperature=0`), Pydantic-typed structured output
  (`RerankDocFacets`), deterministic Python renderer, per-row
  autocommit, `Semaphore(256)`, 5-retry exponential backoff. Three
  CLI verbs: `list-without-doc`, `generate-docs`, `doc-status`.
  Operator manual: `scraper/references/RERANK-DOCS.md`. Migration
  `20260426000000_product_rerank_doc.sql`. Smoke test on 10 products
  passed cleanly; full backfill of remaining ~4,590 products is the
  next action.

## Inputs that already exist (for the reranker)

- 5,000 scraped products in `products` (`subcategory`,
  `ingredient_text`, `name`, `description`, `brand_id`, `price`,
  `currency`).
- INCI function tags in `ingredients.function_tags` (humectant,
  surfactant, silicone, etc.) — useful as deterministic features
  alongside the model.
- Aesthetician rubric: `src/backend/prompts/judge.txt` — names the
  three axes (`moisture_fit`, `scalp_safety`, `structural_fit`).
  Reuse the framing; reranker may use a faster model than the
  per-product judge.

## Inputs that do NOT exist yet

- The reranking module itself (`src/backend/ai/rerank/` is created;
  only `sql_filter/` lives there so far — no `rerank()` interface).

## Open design questions (resolve before building)

- **Reranking model: decided — Cohere Rerank 4 Fast.** Cross-encoder
  with 32K context per query+doc; YAML-recommended document format;
  ~$0.038 per 1900-doc query at quoted pricing.
- **Query construction.** Doc side decided: see "Rerank doc
  generation" above (`rerank_doc` column carries the YAML). Query
  side still open: how to serialize the user's free-text prompt + the
  user's `HairProfile` into a single Cohere query string. Likely a
  templated concatenation that mirrors the YAML key vocabulary so
  query and doc tokens align.
- **Candidate-set size.** sql_filter can return a handful to ~2,000
  rows. Cohere caps at 10,000 docs per call so a single rerank request
  is fine; the reranker just pulls each candidate's `rerank_doc` from
  the DB and ships them in one batch.
- **Pipeline shape.** Reranker queries the DB directly with the
  candidate IDs from sql_filter to fetch `rerank_doc`; sql_filter
  itself does not need to expose the docs. Confirmed direction.
- **Caching.** First pass: no cache.

## Build order

1. ✅ Ingredient tagging (shipped 2026-04-26).
2. ✅ Rerank doc generation (shipped 2026-04-26; full backfill pending).
3. ✅ Reranker module (shipped 2026-04-26). `src/backend/ai/rerank/cohere/`:
   `rerank(conn, profile, query, candidate_ids, top_k=150) -> list[ScoredProduct]`.
   Pulls each candidate's `rerank_doc`, builds a Cohere query string
   from free-text + HairProfile (same enum vocabulary as the YAML
   keys), calls `client.v2.rerank(model="rerank-v4.0-fast", …)` under
   3-attempt tenacity retry on 429/5xx. Discardable `log.txt` per call.
4. ✅ `/filter` extended (shipped 2026-04-26). Same route now does
   sql_filter → fetch latest `HairProfile` → if profile, rerank;
   else return unranked. Cohere failure surfaces as 502 (loud, not
   silent). Response shape adds `reranked: bool` and per-product
   `relevance_score`/`rank` when reranked.
5. ✅ Frontend wire-up (shipped 2026-04-26). Prompt section renders a
   ranked product list below the input with score chips, link-out to
   product URL, and an unranked-fallback note when the user has no
   `HairProfile`.

## Out of scope for this feature

- Per-product judge scoring (the `judge.txt` rubric run per candidate).
  Later, more expensive pass.
- Multi-product routines / "build me a regimen" flows.
- Streaming results to the client.
