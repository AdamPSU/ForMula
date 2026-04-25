# Reranking — feature plan

The active in-flight feature. Update this file as the plan firms up; the
root `CLAUDE.md` references it.

## User flow we are building toward

1. User says "I want a leave-in conditioner" (free-text into the prompt box).
2. Backend resolves intent → `subcategory` (or set of subcategories) and
   filters `products` by that subcategory. Expected: ~5,000 → ~400 rows.
3. Backend takes the user's `HairProfile` (curl type, scalp condition,
   density, porosity, goals — the quiz output, not yet implemented) and
   ranks the ~400 candidates by ingredient fit using a reranking model.
   Expected: 400 → ~150 rows.
4. Return ranked list. Stop. (Per-product judge-scoring with `judge.txt`
   is a later milestone, not part of this feature.)

## Inputs that already exist

- 5,000 scraped products in Supabase `products` (with `subcategory`,
  `ingredient_text`, `name`, `description`, `brand_id`, `price`).
- Quiz definition: `src/backend/profiles/data/quiz.json` (curl pattern,
  scalp condition, density, porosity, goals).
- Aesthetician rubric: `src/backend/prompts/judge.txt` — already names
  the three axes a reranker should optimize against (`moisture_fit`,
  `scalp_safety`, `structural_fit`). Reuse the framing; the reranker
  may use a faster model than the per-product judge.
- INCI function tags in `ingredients.function_tags` (humectant,
  surfactant, silicone, etc.) — useful as deterministic features
  alongside the model.

## Inputs that do NOT exist yet

- `HairProfile` type and persistence. Quiz JSON exists; the rendered
  quiz, the answer schema, and a `profiles` (or equivalent) table do
  not. Profile/onboarding lives as its own top-level backend module —
  not under `ai/`.
- A subcategory resolver (free-text → one or more `subcategory` values).
- The reranking module itself.

## Open design questions (resolve before building)

- **Reranking model.** Cohere Rerank, Voyage Rerank, a hosted
  cross-encoder, or an LLM call per candidate batch? Budget vs latency
  tradeoff. Don't tune knobs on one vendor — survey alternatives first.
- **Query construction.** How do we serialize a `HairProfile` + INCI
  into the rerank query/document pair? Profile as natural-language
  summary vs structured tags; INCI verbatim vs function-tag-augmented.
- **400-candidate ceiling.** Is 400 a hard cap or the typical case?
  Some subcategories may exceed (shampoo) or fall short (curl-custard).
  Plan for both ends.
- **Filter scope.** Subcategory only, or also brand-level filters
  (price, accessibility, regional availability)?
- **Caching.** Profile-keyed cache of (subcategory, top_k) results, or
  recompute every request? First pass: no cache.

## Build order (proposed, not yet approved)

1. **Module skeleton.** Create `src/backend/ai/rerank/` with a clear
   public interface: `rerank(profile, candidates) -> ranked[]`. Stub
   first; wire the model after step 3.
2. **HairProfile module.** Top-level `src/backend/profiles/` (already
   has `data/`) gains a Pydantic `HairProfile` model derived from the
   quiz schema, plus a profile-storage table and migration.
3. **Subcategory resolver.** Free-text → `subcategory[]`. Likely a
   single LLM call against the closed enum in
   `scraper/validation/models.py::HairProductSubcategory`. Trivial
   surface area; don't overbuild.
4. **Candidate fetch.** asyncpg query: `SELECT … FROM products WHERE
   subcategory = ANY($1) AND ingredient_text IS NOT NULL`. Returns the
   ~400.
5. **Rerank.** Pick a model, ship the query/document serialization,
   return top 150.
6. **API endpoint.** FastAPI route (`POST /recommend` or similar) that
   takes `{profile, query}` and returns ranked products. CORS to
   `localhost:3000` is already configured in `main.py`.
7. **Frontend wire-up.** The prompt box on `app/page.tsx` currently
   `console.log`s. Point it at the new endpoint; render results.

## Out of scope for this feature

- Per-product judge scoring (the `judge.txt` rubric run per candidate).
  That's a later, more expensive pass.
- User accounts / auth. A `HairProfile` may live anonymously (in
  Supabase keyed by a generated id, or in the URL) for now.
- Multi-product routines / "build me a regimen" flows.
