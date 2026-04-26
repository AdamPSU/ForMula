# Rerank docs

Generate one positives-only YAML doc per product, optimized for Cohere
Rerank 4. The runtime reranker scores candidate products against a
free-text user query that has been augmented with the user's
`HairProfile`. Two payload columns on `products` carry the data:
`raw_doc` (the LLM's structured output as JSON) and `rerank_doc` (the
rendered YAML).

Repeatable: rerun the loop after any future scrape. Only products
without a `rerank_doc` are touched.

## Why positives-only

The reranker is a cross-encoder. It scores `query ↔ doc` jointly by
attending over both token streams. Negative phrasing ("not for straight
hair") still puts "for straight hair" tokens in the doc, and the model
cannot reliably flip the sign on a buried negation. Encoding only the
positives means every token in the doc contributes signal in the right
direction; absent facets are simply absent, not penalized.

This applies to the LLM-generated `Description` and to all 9 facet
lists. It does NOT apply to scraped marketing descriptions, which are
written verbatim — brands almost never put "not for X" on bottles, and
sanitizing them is more risk than reward.

## Why YAML

Cohere's official best-practices doc explicitly recommends semi-
structured YAML for cases like ours (`yaml.dump(doc, sort_keys=False)` —
key order matters because long docs get truncated tail-first). The
renderer puts the highest-signal facets first (Category, Subcategory,
Description, then HairProfile-aligned fits) and the long INCI list
last, so truncation costs us the least useful tokens.

## Doc shape

```yaml
Category: conditioning
Subcategory: leave-in-conditioner
Description: A lightweight, moisturizing leave-in built for definition and slip on dry, frizz-prone curls.
Hair types: curly, coily, wavy
Concerns addressed: frizz, dryness, breakage
Goals served: definition, shine, strength
Scalp fit: dry, balanced, sensitive
Strand thickness fit: fine, medium
Density fit: medium, thick
Porosity fit: soaks
Climate fit: humid, dry
Routine fit: weekly
Ingredients: water (solvent), glycerin (humectant), behentrimonium chloride (cationic_surfactant), ...
```

- `Category` / `Subcategory` — direct from `products` row, mechanical.
- `Description` — `products.description` if non-NULL; LLM-generated
  otherwise. Positives-only when generated; verbatim when scraped.
- 9 fit lists — LLM output, every value drawn from the corresponding
  `HairProfile` enum so query tokens line up exactly.
- `Ingredients` — full INCI in label order, each rendered as
  `inci_name (function_tag[0])` from a JOIN on `ingredients`.

Empty fit lists collapse to **the key being omitted entirely**.

## Field → HairProfile mapping

- `Hair types` ⇄ `curl_pattern` (straight / wavy / curly / coily)
- `Concerns addressed` ⇄ `concerns` (frizz / breakage / thinning /
  dandruff / dryness / dullness / flatness / irritation)
- `Goals served` ⇄ `goals` (definition / volume / strength / length /
  scalp_health / shine)
- `Scalp fit` ⇄ `scalp_condition` (oily / dry / flaky / sensitive /
  balanced)
- `Strand thickness fit` ⇄ `strand_thickness` (fine / medium / coarse)
- `Density fit` ⇄ `density` (thin / medium / thick)
- `Porosity fit` ⇄ `product_absorption` (soaks=high, sits=low,
  greasy=low+oily-scalp; "unsure" omitted)
- `Climate fit` ⇄ `climate` (humid / dry / cold / mixed)
- `Routine fit` ⇄ `wash_frequency` (daily / 2_3_days = gentle daily-use;
  weekly / less = intensive treatments)

`drying_method` is intentionally excluded — too noisy a mapping
(heat-protectant presence) for too little discriminative value at the
rerank stage.

## Commands

- `list-without-doc --out-file <path> [--limit N]` — write a JSONL of
  bundles for products that need doc generation
  (`rerank_doc IS NULL` AND `ingredient_text IS NOT NULL` AND
  `scrape_status = 'success'`). Each line is a self-contained input:
  `{id, name, description, subcategory, category, ingredients:
  [{inci_name, function_tag}, ...]}`. The ingredients list is JOIN-ed
  in label order so the generator never re-queries.
- `generate-docs --in-file <jsonl>` — read the bundles, fan out under
  `Semaphore(256)`, autocommit each successful row. Failed rows append
  to `<input>.failed.jsonl` so they can be retried in isolation.
  Returns `{processed, succeeded, failed, failed_file, log_file}`.
- `doc-status` — `{total_products_with_inci, with_rerank_doc,
  without_rerank_doc, sample_docs}`. Free, run anytime.

## Workflow

1. `doc-status` to see scope.
2. **Smoke first.** `list-without-doc --out-file /tmp/smoke.jsonl --limit 10`,
   then `generate-docs --in-file /tmp/smoke.jsonl`. Inspect the rendered
   docs (see acceptance criteria below). All 10 must pass before the
   full backfill.
3. **Full backfill.** `list-without-doc --out-file /tmp/all.jsonl`,
   then `generate-docs --in-file /tmp/all.jsonl`. Expected: ~$1, <2 min
   wall-clock at 256-way concurrency.
4. `doc-status` to confirm `without_rerank_doc` is 0 (or matches the
   number of products with no usable INCI tokens after JOIN).
5. If `failed.jsonl` is non-empty, re-run `generate-docs --in-file
   <failed_file>` once. Genuine failures (Pydantic-rejected enums,
   Grok 5xx after 5 retries) need manual investigation via `log.txt`.

## Smoke-test acceptance criteria

- All 10 succeeded (no `failed.jsonl` produced).
- Every facet list value is in its `HairProfile` enum vocabulary.
- `Ingredients` line lists all known INCI in label order, each with a
  function tag in parens.
- YAML key order matches the spec exactly.
- `raw_doc` parses back to a valid `RerankDocFacets` object.
- LLM-generated `Description` (when scraped is NULL) contains no
  exclusionary phrasing. Scraped descriptions are verbatim and may
  legitimately contain marketing claims like "silicone-free" — that's
  the policy, don't flag.

## Refresh policy

None. If a re-scrape changes a product's `ingredient_text` or
`description`, the `rerank_doc` and `raw_doc` for that row go stale
until the pipeline runs again. To force regeneration after a re-scrape:

```sql
update products set raw_doc = null, rerank_doc = null where id = $1;
```

Then run the workflow above.

## Observability

`scraper/tools/descriptions.log.txt` (gitignored) captures, per call:
input bundle, raw LLM output, parsed Pydantic, rendered YAML. Truncated
at the start of every `generate-docs` run — discardable. Use it to
diagnose any row in `failed.jsonl`.

## Modeling notes

- **Silence > false positive.** When the LLM is unsure whether a leave-
  in works on wavy hair, the prompt instructs it to leave wavy out of
  `hair_types` rather than include it defensively. Silence on a facet
  is positives-only-safe; the reranker never penalizes what it doesn't
  see.
- **`unsure` is never written for porosity.** The `ProductAbsorption`
  enum includes `unsure`, but a product can't be a positive fit for
  "unsure". The LLM omits it.
- **Routine_fit collapses two pairs.** `daily` + `2_3_days` →
  gentle daily-use cleansers and conditioners. `weekly` + `less` →
  intensive treatments and rich masks. The LLM chooses one or both
  depending on the product type, not both pairs at once.
- **Ingredient list order matters.** INCI label order is concentration-
  descending and regulatorily meaningful. The renderer preserves it,
  giving Cohere an implicit "first listed = highest concentration"
  positional signal even though the cross-encoder doesn't formally know
  the convention.
- **Unknown tokens are silently skipped.** If `_split_ingredient_text`
  produces a token that isn't in the `ingredients` table (footnote
  fragments, fused tokens), it's dropped from the rendered list rather
  than tagged with a fallback. Polluting the doc with `(other)`
  placeholders would be worse than slightly under-coverage.
- **Per-row autocommit.** Same discipline as the tagging pipeline —
  every successful Grok call writes its row immediately. A crash mid-
  batch loses no completed work.

## Lessons

Same convention as the scraper agent's `LESSONS.md` — append a bullet
when a generation mistake or workflow snag is worth remembering. Skip
anything obvious from this document or the tool output.
