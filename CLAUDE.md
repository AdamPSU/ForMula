# ForMula

Match users to hair-care products by ingredient list (INCI), not marketing copy. User describes their hair, we filter the catalog by product type, then rerank by fit against their HairProfile.

## Active work
- **Next feature: reranking.** Plan: @.claude/references/TODO.md

## Monorepo layout
- `src/frontend/` — Next.js 16 (App Router), React 19, Tailwind v4, TypeScript, bun. Supabase auth via `@supabase/ssr`.
  - `app/` — routes (`page.tsx`, `layout.tsx`); `(auth)/sign-in`, `(auth)/sign-up`; `auth/callback`, `auth/sign-out`
  - `proxy.ts` — Next.js 16 proxy (formerly `middleware.ts`); refreshes the Supabase token on every request and gates the app: unauthenticated users are redirected to `/sign-in`. Every route except `/sign-in`, `/sign-up`, `/auth/*` requires auth.
  - `lib/supabase/{client,server,middleware}.ts` — browser client, RSC-safe server client, and the middleware helper. Always read the user via `supabase.auth.getClaims()` server-side; never `getSession()`.
  - `components/ui/` — shared UI (`ai-prompt-box`, `border-glow`, `hero-shutter-text`, `breadcrumb`)
  - `components/auth/` — `auth-form`, `user-menu`
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
- `profiles` is the auth bridge: one row per `auth.users` user, auto-created by the `on_auth_user_created` trigger. RLS lets a user read/update only their own row. **All future user-owned tables (e.g. `hair_profiles`) FK to `public.profiles(id)`.**
- RLS: public read on `brands`, `products`, `ingredients`; `scrape_jobs` is service-role only; `profiles` is owner-only.
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
- All env vars live in **`.env.local` at the repo root**. Single source of truth.
- Frontend: `src/frontend/.env.local` is a **symlink** to `../../.env.local`. Required because Next.js's edge runtime sandbox (where `proxy.ts` runs) only sees env vars from `.env*` files in the project directory — `loadEnvConfig` in `next.config.ts` populates the parent Node process but does not cross into the edge runtime.
- Backend reads via `python-dotenv`: `main.py` (FastAPI) and `scraper/__main__.py` both call `load_dotenv` against the repo-root path before any module touches `os.environ`.
- Never commit `.env*` files. The symlink itself is gitignored by the same `.env*` rule.

## Conventions
- Don't add fallbacks, defaults, or backward-compat shims unless asked. Break cleanly, clear stale data, document the wipe.
- Per-row autocommit after every paid external call (Firecrawl, LLM) — never batch paid writes in one transaction.
- LLM-first, schema-driven extraction (Pydantic → Firecrawl JSON schema). Never hand-write CSS selectors.
