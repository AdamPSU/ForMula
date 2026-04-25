# ForMula

Match users to hair-care products by ingredient list (INCI), not marketing copy. User describes their hair, we filter the catalog by product type, then rerank by fit against their HairProfile.

## Active work
- **Next feature: reranking.** See `.claude/references/TODO.md` for the plan.

## Monorepo layout
- `src/frontend/` — Next.js 16 (App Router), React 19, Tailwind v4, TypeScript, bun. Supabase client via `@supabase/ssr`.
  - `app/` — routes (`page.tsx`, `layout.tsx`)
  - `components/ui/` — shared UI (`ai-prompt-box`, `border-glow`, `hero-shutter-text`, `breadcrumb`)
  - `lib/utils.ts` — `cn()` only
  - `public/curl-types/` — 12 reference images (1a–4c) for the quiz
- `src/backend/` — Python 3.12, FastAPI stub, uv. asyncpg direct (no ORM).
  - `scraper/` — Firecrawl + LLM product scraper (autonomous CLI agent). **Has its own `CLAUDE.md` — defer to it for any scraper work.**
  - `db/supabase/migrations/` — SQL migrations, timestamped `<YYYYMMDDHHMMSS>_*.sql`
  - `profiles/data/quiz.json` — hair profile quiz definition (curl pattern, scalp, density, porosity, goals)
  - `prompts/judge.txt` — aesthetician-persona rubric that scores a product's INCI against a HairProfile on `moisture_fit`, `scalp_safety`, `structural_fit`. Seed of the reranker.
  - `main.py` — FastAPI app stub (CORS to localhost:3000, single `/` route)

## Data model (Supabase Postgres)
- `brands` → `scrape_jobs` → `products`. `products.ingredient_text` is the raw INCI string — source of truth for ranking.
- `products` carries `category` (cleansing / conditioning / styling / treatments / oils / tools / accessories / other) and a more specific `subcategory` (e.g. `leave-in-conditioner`). The `category` value is derived from `subcategory` via `scraper/validation/models.py::SUBCATEGORY_TO_CATEGORY`.
- `ingredients` is a normalized INCI registry with `function_tags` (humectant, surfactant, silicone, …).
- RLS: public read on `brands`, `products`, `ingredients`; `scrape_jobs` is service-role only.
- 5,000 products currently populated. Inspect with the supabase CLI or via the backend.

## Module boundaries
- `backend/ai/` (when added) is for research / LLM / reranking code only.
- Profile, onboarding, and user-facing logic live as their own top-level backend modules — not under `ai/`.
- New SQL changes go through a new migration file; never edit applied migrations.

## Commands
- Typecheck (frontend): `cd src/frontend && bunx tsc --noEmit`
- Lint (frontend): `cd src/frontend && bunx next lint`
- Frontend dev: `cd src/frontend && bun dev`
- Backend dev: `cd src/backend && uv run uvicorn main:app --reload --port 8000`
- Scraper CLI: `cd src/backend && uv run python -m scraper <subcommand>` (see `scraper/CLAUDE.md`)
- Add Python dep: `cd src/backend && uv add <pkg>`

## Environment
- Frontend secrets: `src/frontend/.env.local` (Supabase anon key etc.)
- Backend secrets: `src/backend/.env` (Firecrawl, OpenAI, DB URL)
- Never commit `.env*` files.

## Conventions
- Don't add fallbacks, defaults, or backward-compat shims unless asked. Break cleanly, clear stale data, document the wipe.
- Per-row autocommit after every paid external call (Firecrawl, LLM) — never batch paid writes in one transaction.
- LLM-first, schema-driven extraction (Pydantic → Firecrawl JSON schema). Never hand-write CSS selectors.
