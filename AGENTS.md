# Agent Instructions

## Monorepo Structure
- `frontend/` — Next.js 16, Tailwind v4, TypeScript, bun
- `backend/` — Python 3.12, FastAPI, uv

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

**Pipeline:** `User Input → Orchestrator → N Search Agents (parallel) → Pinecone Dedup → Synthesizer → Output`

### Agents
| Agent | Role |
|-------|------|
| Orchestrator | Parses hair profile, generates 5–7 search angles, spawns sub-agents |
| Search/Extract (×N) | One per angle; Tavily search → filter snippets → Tavily extract → write to shared state |
| Synthesizer | Ranks deduplicated products against hair profile, produces reasoned recommendation |

### Stack
| Component | Tool |
|-----------|------|
| Orchestration | LangGraph (dynamic fan-out, shared state) |
| Search & Extract | Tavily (`search` + `extract` APIs) |
| Deduplication | Pinecone (>97% embedding similarity = duplicate) |
| LLM | TBD |

## Key Conventions
- Sub-agents **check shared state before extracting** — never re-extract a URL another agent already processed
- Orchestrator must justify each angle before spawning — hard cap at 7 angles
- Pinecone stores: product name, brand, ingredients, price, URL, source angle
- `backend/main.py` is the FastAPI entrypoint; `POST /research` is the primary route
- Frontend calls `POST /research` with `multipart/form-data` (`prompt` + optional `images[]`)
