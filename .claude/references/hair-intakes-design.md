# Hair intakes — design

Step 2 of the rerank build order. Captures the user's quiz answers as the
input the reranker consumes. See `TODO.md` for the broader feature plan.

## Decisions

- **Storage shape: JSONB blob.** The quiz is iterating; static columns
  would force a migration per question change. Pydantic owns the answer
  schema; the DB stores a validated JSONB.
- **Append-only history.** One row per quiz submission. "Latest" is the
  user's current `HairProfile`. Users may retake; we keep the trail.
- **Table name: `hair_intakes`.** Distinct from `public.profiles` (the
  auth bridge). Each row is an intake event; the validated record is a
  `HairProfile` in code.
- **Quiz definition stays in JSON.** `src/backend/profiles/data/quiz.json`
  is the source of truth for both backend and frontend. Frontend reaches
  it via a symlink. A `quizzes` table would add a network hop and break
  static literal types without solving a real problem at this stage.
- **API surface: FastAPI + asyncpg.** Architectural pattern in CLAUDE.md
  ("Supabase Auth for auth only; FastAPI + asyncpg + pooler for all
  data"). Frontend talks to FastAPI directly with the Supabase JWT in
  `Authorization: Bearer`.
- **JWT verification: asymmetric (ES256) via JWKS.** Modern Supabase
  default. Public keys fetched from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`,
  cached for 1h.

## Schema

`src/backend/db/supabase/migrations/20260425010000_hair_intakes.sql`:

```sql
create table public.hair_intakes (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.profiles(id) on delete cascade,
  quiz_version int not null,
  answers      jsonb not null,
  created_at   timestamptz not null default now()
);

create index hair_intakes_user_latest
  on public.hair_intakes (user_id, created_at desc);

alter table public.hair_intakes enable row level security;

create policy "hair_intakes read own"
  on public.hair_intakes for select using (auth.uid() = user_id);
create policy "hair_intakes insert own"
  on public.hair_intakes for insert with check (auth.uid() = user_id);
-- No update/delete: append-only.
```

## Backend

```
src/backend/
├── auth/                              [NEW top-level module]
│   ├── __init__.py
│   └── jwt.py                         get_current_user_id FastAPI dep,
│                                       JWKS fetch + 1h cache, ES256 decode
└── profiles/
    ├── __init__.py                    [NEW]
    ├── data/quiz.json                 [EXISTS]
    ├── models.py                      [NEW] HairProfile + literals + validator
    ├── repository.py                  [NEW] insert_hair_intake / get_latest_hair_profile
    └── api.py                         [NEW] POST/GET /me/hair-profile
```

`main.py` gains a lifespan that opens an asyncpg pool from `DATABASE_URL`
on startup, closes it on shutdown, and stores it on `app.state.pool`.

New deps: `python-jose[cryptography]`, `cachetools`. (`httpx` already
present.)

## Frontend

```
src/frontend/
├── app/quiz/
│   ├── page.tsx                       [NEW] server-component shell
│   └── _components/
│       ├── quiz-flow.tsx              [NEW] step + answer state machine
│       ├── question-single.tsx        [NEW] radio
│       ├── question-multi.tsx         [NEW] checkbox (honors max_select)
│       └── question-image.tsx         [NEW] curl-pattern grid
├── lib/quiz/
│   ├── quiz.json                      [NEW SYMLINK → ../../../backend/profiles/data/quiz.json]
│   └── types.ts                       [NEW]
└── lib/api/
    └── hair-profile.ts                [NEW] reads access_token, POSTs to NEXT_PUBLIC_API_URL
```

Quiz flow handles the conditional skip on `chemical_recency` when
`chemical_history === ["none"]`, validates against the same constraints
as the Pydantic model (multi `max_select`, required goals), and submits
the transformed payload to FastAPI.

## Validation parity

Pydantic constraints the frontend must mirror:

- `chemical_history`: `min_length=1` — at least one choice (including "none").
- `concerns`: `max_length=3`.
- `goals`: `min_length=1` — exactly one in this quiz, wrapped per
  `wrap_in_list`.
- `chemical_recency`: must be `"na"` iff `chemical_history == ["none"]`.

## Out of scope (this PR)

- "Take the quiz" CTA on the home page — wire that with the rerank PR
  when the prompt has a destination.
- SSR of "do I have a profile?" — needs cookie-based JWT propagation.
- Beyond a single Pydantic-validation unit test, no automated tests.
- Edit / retake polish (mechanically: just submit again).

## Verification

1. Apply migration: `psql "$DATABASE_URL" -f src/backend/db/supabase/migrations/20260425010000_hair_intakes.sql`.
2. Start backend (`uv run uvicorn main:app --reload --port 8000`) and
   frontend (`bun dev`).
3. Sign in, navigate to `/quiz`, complete all 12 questions, submit.
4. `select * from public.hair_intakes` → exactly one row, `user_id`
   matches.
5. Pydantic edge case: `chemical_history=["bleach"]` + `chemical_recency="na"`
   → 422 from POST.
6. RLS: user A cannot select user B's row.
7. `bunx tsc --noEmit`, `bunx next lint` clean.
