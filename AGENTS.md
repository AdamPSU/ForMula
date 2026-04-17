# Agent Instructions

## Monorepo Structure
- `frontend/` — Next.js 16, Tailwind v4, TypeScript, bun
- `backend/` — Python 3.12, FastAPI, uv
- `supabase/migrations/` — versioned Postgres schema; applied via `supabase db push`

## Package Managers
- **Frontend:** `bun` — `bun install`, `bun dev`, `bun run build`
- **Backend:** `uv` — `uv add <pkg>`, `uv run uvicorn main:app --reload`

## File-Scoped Commands
| Task | Command |
|------|---------|
| Typecheck | `cd frontend && bunx tsc --noEmit` |
| Lint | `cd frontend && bunx next lint` |
| Backend run | `cd backend && uv run uvicorn main:app --reload --port 8000` |
| Frontend dev | `cd frontend && bun dev` |

## Architecture — Multi-Agent Hair Recommender

**Pipeline:** `User Input → Orchestrator → Search → URL-dedup → Extract (upsert to products catalog) → 3-Judge Panel → Synthesizer → Output`

### Agents
| Agent | Role |
|-------|------|
| Orchestrator | Loads `HairProfile`, auto-prompts Exa queries, drives the LangGraph pipeline |
| Search / Extract | Exa search; per-URL extraction embeds the product and upserts it into the shared `products` catalog (pgvector dedup) |
| Judge panel | Grok + Gemini + Claude (blind, same input) — every judge's full axis verdict is persisted |
| Synthesizer | Ranks panel-averaged scores, produces the top-k recommendation |

### Stack
| Component | Tool |
|-----------|------|
| Orchestration | LangGraph |
| Search & Extract | Exa (`search` + `get_contents`) |
| URL dedup (pre-extract) | Local BGE embeddings (`BAAI/bge-small-en-v1.5`, 384-d) |
| Product dedup (catalog) | pgvector HNSW, cosine similarity > 0.97 (`products.embedding vector(384)`) |
| Persistence | Supabase Postgres (asyncpg via transaction-mode pooler) |
| Auth | Supabase Auth (JWT via JWKS in FastAPI, SSR cookies in Next.js) |
| Realtime | Supabase Realtime on `sessions` (status transitions) |
| LLM judges | Grok 4.1 Fast (xAI) + Gemini 3.1 Pro + Claude Sonnet 4.6 (OpenRouter) |

## Key Conventions
- Orchestrator runs purely in-memory during the pipeline; `main.py` persists the final state (angles + session_products + judges + axes) at the end of `/research`.
- Product catalog is shared across users. A duplicate extraction reuses the existing `products.id` (HNSW nearest-neighbor hit > 0.97 similarity).
- Every judge's full verdict (rationale, evidence, sub_criteria) is persisted per (session_product, judge, axis) — we no longer discard Gemini's / Claude's narratives.
- Frontend reads `profiles` and `sessions` directly from Supabase under RLS; writes still go through FastAPI.
- `backend/main.py` is the FastAPI entrypoint; `POST /research` is the primary route.
- Frontend calls `POST /research` with `multipart/form-data` (`prompt` + optional `images[]`).

## Schema
- Migrations live in `supabase/migrations/`. Apply with `supabase db push` (CLI) or `psql -f`.
- Tables: `profiles`, `products`, `user_current_products`, `sessions`, `session_angles`, `session_products`, `session_product_judge_panels`, `session_product_axis_verdicts`.
- RLS is enabled on every table. Nested-table policies use the `private.user_owns_session(uuid)` SECURITY DEFINER helper.

## Planned Scope (design pending)
- **Current-products UI** — the `user_current_products` table and `/profile/current-products` endpoints exist; the UI surface for adding / browsing hasn't been built yet.
- **Async `/research` + Realtime progress** — today `/research` blocks until done; the schema is ready for per-stage DB writes and client-side Realtime subscriptions when we want to stream progress.
- **Feedback loop** — deliberately deferred; will attach to `(user_id, product_id)` once current-products ships.

## Lessons
- **Judge prompts must never prime score distribution.** Do not tell the judge what score is "common" or "expected" — this biases the output and defeats blinded evaluation. Tighten via ingredient/profile logic only, not score-anchoring hints.
