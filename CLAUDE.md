# ForMula

## Monorepo Structure
- `src/frontend/` — Next.js, Tailwind v4, TypeScript, bun
- `src/backend/` — Python 3.12, FastAPI, uv

## Package Managers
- **Frontend:** `bun` — `bun install`, `bun dev`, `bun run build`
- **Backend:** `uv` — `uv add <pkg>`, `uv run uvicorn main:app --reload`

## File-Scoped Commands
| Task | Command |
|------|---------|
| Typecheck | `cd src/frontend && bunx tsc --noEmit` |
| Lint | `cd src/frontend && bunx next lint` |
| Backend run | `cd src/backend && uv run uvicorn main:app --reload --port 8000` |
| Frontend dev | `cd src/frontend && bun dev` |

## Data
- `src/backend/profiles/data/quiz.json` — hair profile quiz definition
- `src/frontend/public/curl-types/` — 12 reference images (1a–4c) used by the quiz

## Prompts
- `src/backend/prompts/` — LLM prompt templates
