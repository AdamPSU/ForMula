# Ingredient tagging

Walk every product's INCI list, tag each unique normalized ingredient
with function tags from a closed enum, store in the `ingredients`
table. The reranker (next milestone) consumes these tags via the
rich-description generator.

Repeatable: rerun the loop after any future product scrape and only
the newly-introduced ingredients hit the LLM.

## Tag from knowledge by default; look up only when genuinely unsure

You (the LLM) already know the vast majority of common INCI cold —
common surfactants, silicones, preservatives, fatty alcohols, plant
oils with standard Latin binomials, fragrance allergens, polyquats by
number, and so on. **Tag those from knowledge.** Every unnecessary
`lookup-ingredient` call burns 5 Firecrawl credits and ~3K of your
context for information you already have.

Use `lookup-ingredient` only when **genuinely uncertain**. Genuine
uncertainty looks like:

- A name with no clear INCI structural cues (no `-eth`, no `-cone`,
  no recognizable Latin binomial, no `polyquaternium-N`).
- A specialty / proprietary-sounding name you don't recognize at all.
- A novel active or recent ingredient you may not have training data
  on.
- A name where the function is structurally *plausible but not
  obvious* (e.g. complex copolymers, unusual esters, branded actives).
- A name where you're torn between two of our enum tags and the
  right answer would change a recommendation.

Do **not** look up when:

- The name follows a well-known INCI pattern that maps directly to a
  tag (`-trimonium chloride` → `cationic_surfactant`; `-yl alcohol`
  fatty alcohols; `cyclopentasiloxane` → `silicone_volatile`;
  `polyquaternium-N` → `polyquat`; binomial `___ oil` from a
  recognizable plant → `plant_oil, emollient`).
- The ingredient is in the everyday short list: water, glycerin,
  common preservatives, common humectants, common fragrance
  allergens.
- You'd recognize it on sight without thinking.

### When confident, tag and move on

Don't second-guess. The reranker is a coarse filter; tags within ±1
adjacent category (e.g. `emollient` vs `emollient, occlusive`) won't
change ranking outcomes. Save the lookup budget for the cases where
you'd otherwise have to guess.

### How `lookup-ingredient` works

```
uv run python -m scraper lookup-ingredient --name "BEHENTRIMONIUM CHLORIDE"
```

Slugifies the INCI name and Firecrawl-scrapes
`https://incidecoder.com/ingredients/<slug>` (5 credits). Returns
`{name, slug, url, source, credits_used, markdown}`. The markdown
contains the **CosIng official functions** ("antistatic, hair
conditioning, preservative", etc.), CAS number, IUPAC name, and any
SCCS safety opinions. Read it, then translate to our 31-tag enum
(see modeling notes below — CosIng's vocabulary doesn't match ours
1:1, e.g. "antistatic + hair conditioning" maps to our
`cationic_surfactant`).

On a 404 / unknown slug, the call automatically falls back to
`https://incidecoder.com/search?query=<name>` (5 more credits, total
10). The agent picks the correct slug from the search results and
re-runs `lookup-ingredient`.

**Use `lookup-ingredient` over WebSearch** when you do need to look
something up — Firecrawl is the project's existing paid integration
and the structured incidecoder page is much cleaner signal.

If `lookup-ingredient` returns nothing useful (genuinely obscure
brand-proprietary blend, no incidecoder entry, no useful search
results), tag conservatively from surface-form clues in the name and
set `has_safety_concern: false`. If you can't even guess, tag
`[other]`. Add a bullet to LESSONS.md noting the family that gave
you trouble.

### Junk tokens (tag `other` without lookup)

Some normalized strings are not real ingredients — they're footnote
fragments concatenated by the comma-split. Tag `[other]` and move
on, no lookup needed. Examples:

- Footnote text: `*CERTIFIED ORGANIC. OM021`,
  `LINALOOL. *CERTIFIED ORGANIC. OM021`, anything containing
  trailing `*___` after a real ingredient name
- Cross-product noise: long strings containing
  `SOURCED FROM`, `ALLERGENS/ALLERG`, `MAY CONTAIN: CI ___`
- Tokens fused by missing commas: `LIMONENELINALOOL`, `LLAURETH-3`
  (likely `LAURETH-3` mangled), `PHENOXYETHANO` (typo)
- `+/-` colorant section markers

If a string clearly contains a real ingredient name embedded in
junk, you can extract just the ingredient and tag it with the
appropriate function tag (e.g., `LINALOOL. *CERTIFIED ORGANIC. OM021`
→ tag the row as `LINALOOL` with `[fragrance]`). Otherwise `[other]`.

## Commands

- `list-untagged --out-file <path> [--limit N]` — unique normalized
  INCI strings used by `products` that aren't yet in `ingredients`.
  Normalization: UPPERCASE, trimmed, whitespace collapsed,
  asterisks/edge punctuation stripped, parens preserved. Returns
  `{count, written, out_file, sample, top_by_frequency}`.
- `lookup-ingredient --name "<INCI>"` — Firecrawl /scrape on
  `incidecoder.com/ingredients/<slug>` (5 credits). Returns the
  page markdown with CosIng functions, CAS/IUPAC, and SCCS safety
  opinions. Auto-falls back to the site's search page on a 404
  (5 more credits, total 10). See "Look up first" above.
- `tag-batch --file <jsonl>` — upsert tagged rows. Each line is
  `{inci_name, function_tags, common_name, has_safety_concern}`.
  Drift-checks the `ingredients_function_tags` constraint up front;
  per-row autocommit (a single bad row never rolls back the rest).
  Returns `{inserted, updated, errors}`.
- `tag-status` — `{total_unique_in_products, tagged, untagged,
  other_rate, top_untagged_by_frequency}`. Free, run anytime.

## Tag enum (closed; 31 values)

Source of truth: `FunctionTag` Literal in
`scraper/validation/models.py`. Multi-label per ingredient.

```
Vehicles & moisture: solvent, humectant, emollient, occlusive,
                     fatty_alcohol, drying_alcohol
Surfactants:         anionic_surfactant, cationic_surfactant,
                     nonionic_surfactant, amphoteric_surfactant
Silicones:           silicone_water_soluble, silicone_non_water_soluble,
                     silicone_volatile
Proteins:            protein_hydrolyzed, protein_intact
Lipids (botanical):  plant_oil, butter
Polymers:            polyquat, film_former
Adjuncts:            preservative, chelator, ph_adjuster,
                     fragrance, essential_oil, exfoliant,
                     antioxidant, ceramide
Targeted actives:    heat_protectant, uv_filter, antidandruff
Catch-all:           other
```

If you change the enum, regenerate + apply the migration:

```
uv run python -m scraper dump-schema --target ingredients > \
  db/supabase/migrations/<ts>_ingredient_function_tags_vN.sql
# then apply
```

## Workflow

1. `tag-status` to see scope.
2. `list-untagged --out-file /tmp/untagged.txt`.
3. Read ~50 lines. For each:
   - **Recognized from knowledge** (most ingredients): tag directly.
     Common surfactants, silicones, preservatives, fatty alcohols,
     plant oils, fragrance allergens, polyquats — you know these.
   - **Genuinely unsure** (rare/novel/proprietary, no clear INCI
     structural cues): `lookup-ingredient --name "<INCI>"`, then tag
     based on the page.
   - **Junk / unparseable** (footnote fragments, fused tokens, color
     markers): tag `[other]` — no lookup.
4. Build a JSONL batch, `tag-batch --file /tmp/batch-N.jsonl`.
5. Loop until `list-untagged` returns count=0.
6. `tag-status` — if `other` rate > 5%, surface top `other`
   ingredients for enum review.

Budget guard: `lookup-ingredient` costs 5 credits per call. Realistic
expectation for a full ~8K backfill: a few hundred lookups (the
genuinely-unknown long tail), well under 5K credits total. If you
find yourself looking up >20% of ingredients, you're being too
cautious — re-read the "Tag from knowledge by default" rule above.
Run `check-budget` periodically to confirm headroom.

## Modeling notes

- **Surfactants split by ionic class is non-negotiable** — anionic +
  cationic form an insoluble complex, so the reranker needs the
  distinction to handle co-wash profiles. Sulfates →
  `anionic_surfactant`. Behentrimonium / cetrimonium / quats →
  `cationic_surfactant`. Cocamidopropyl betaine and similar →
  `amphoteric_surfactant`. Decyl glucoside / coco glucoside →
  `nonionic_surfactant`. **If you're not 100% sure of an ingredient's
  ionic class, look it up.**
- **Silicones split by rinsability**: anything water-soluble (PEG-
  prefixed dimethicone copolyols) → `silicone_water_soluble`;
  cyclomethicone / cyclopentasiloxane / cyclohexasiloxane evaporate
  → `silicone_volatile`; everything else → `silicone_non_water_soluble`.
- **Proteins split by penetration**: hydrolyzed (small Da, enters
  cortex) → `protein_hydrolyzed`; intact (surface-coating) →
  `protein_intact`. Source (keratin/silk/wheat/rice) is marketing —
  the molecular weight is the science. **Look it up to confirm
  hydrolysis status.**
- **Plant oils vs emollient**: coconut, olive, avocado, argan
  actually penetrate the cortex (triglyceride polarity) — tag
  `plant_oil` AND `emollient` (and `occlusive` if heavy).
- **Butters**: shea, mango, cocoa — `butter` AND `emollient` AND
  `occlusive`. Heavier than oils, deposits differently.
- **`vitamin` tag is intentionally absent**: panthenol → `humectant`
  + `film_former`; tocopherol → `antioxidant`; niacinamide → `other`.
- **`antidandruff` covers what other catalogs call "antifungal"** —
  piroctone olamine, climbazole, zinc pyrithione, ketoconazole,
  selenium sulfide, salicylic acid at scalp doses. We use
  use-case-relevant naming because that's what the quiz asks about.
- **Fragrance allergens** (limonene, linalool, citronellol, hexyl
  cinnamal, geraniol, citral): tag `fragrance`. They're declared
  per EU rules but functionally are scent compounds.

## Safety concern flag

Set `has_safety_concern: true` only when the incidecoder page
explicitly flags one of: documented endocrine disruption, formaldehyde
release, MIT/MCI above EU limits, banned dyes, or restricted-use under
EU/Health Canada (the "Cosmetic Restrictions" and "SCCS Opinions"
fields on the page). Don't flag for vague "may irritate sensitive
skin" copy — that's true of most surfactants. This field is consumed
by future safety-warning UI; false positives are worse than false
negatives.

## Lessons

Same convention as the scraper agent's `LESSONS.md` — append a bullet
when a tagging mistake or workflow snag is worth remembering. Skip
anything obvious from this document or the tool output.
