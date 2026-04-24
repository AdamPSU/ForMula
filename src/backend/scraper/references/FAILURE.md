# Failure runbooks

Read only when CLAUDE.md points here. These are detailed recovery
procedures for specific failure modes that don't apply on the happy
path.

## Agent-browser fallback for hidden INCI

**Trigger.** During preflight, compare `extraction_attempt.ingredient_text`
against the same response's `markdown`. If >70% of the comma-separated
tokens are absent from the markdown, Firecrawl is hallucinating and
`run-extraction` will mark every row `success` with fabricated INCI.
Treat the brand as blocked on the Firecrawl path.

**Approach.** This fallback replaces Firecrawl for the blocked brand; it
does not run on top of it. `agent-browser` drives real Chrome, opens
each PDP, clicks the ingredients modal, and reads every field we need
from the rendered DOM in one pass. `run-extraction` is never called for
these brands, so no Firecrawl credits are spent and there is no
hallucinated `ingredient_text` to override.

No scraper code changes. Flow:

1. `filter-links` as normal → `/tmp/<brand>-keep.txt`.
2. `create-brand` + `create-scrape-job` + `stage-products` as normal —
   this inserts one `pending` row per URL with the right brand / job
   linkage. **Skip `check-budget` and `run-extraction`.**
3. Dispatch one `general-purpose` subagent per URL in a single message
   (all Task calls in parallel). Each subagent drives `agent-browser`
   per the recipe below and returns a JSON object conforming to the
   `ProductExtraction` schema (`scraper/validation/models.py`).
4. Collect results into `/tmp/<brand>-rows.json`, a map
   `{url: ProductExtraction-dict}`. Rows a subagent returns as
   `NOT_FOUND` stay `pending` and can be retried.
5. Write a one-off `/tmp/<brand>_fill_rows.py` that, for each URL in the
   map, runs `ProductExtraction(**data)` to validate, then `UPDATE
   products SET name=$2, subcategory=$3, category=$4, description=$5,
   price=$6, currency=$7, ingredient_text=$8, scrape_status='success'
   WHERE url=$1 AND scrape_job_id=<jid>`. Reuse `scraper.db.connection()`
   and load `.env` via `dotenv.load_dotenv(Path("src/backend/.env"))`
   the way `scraper/__main__.py` does. Per-row autocommit (no wrapping
   transaction) — see `references/LESSONS.md` on stranded credits.
6. `finish` with a summary that names the fallback so the provenance is
   in the job record.

### Subagent prompt template

Self-contained — subagents don't see this file or the parent
conversation. Paste the full `EXTRACT_PROMPT` string
(`scraper/prompts/extract.py`) and the enum lists from
`scraper/validation/models.py` into the prompt so the subagent's output
is schema-valid.

> Extract structured data about the product at `<URL>` using the
> `agent-browser` CLI, then return ONE JSON object matching this schema
> (include every field; use null if unknown):
>
> ```
> { "name": string|null, "subcategory": <enum>|null,
>   "category": <enum>|null, "description": string|null,
>   "price": number|null, "currency": <enum>|null,
>   "ingredient_text": string|null }
> ```
>
> Enum values for `subcategory`, `category`, `currency` — copy verbatim
> from `scraper/validation/models.py` and paste below:
> `<paste-enums-here>`
>
> Rules: verbatim-extraction only. Null is always valid. A wrong value
> is worse than a null value.
>
> Steps:
> 1. `agent-browser open <URL>`
> 2. `agent-browser wait --load networkidle`
> 3. `agent-browser snapshot -i`. If a newsletter / SMS / email popup
>    iframe appears, click its Dismiss / Close ref and re-snapshot.
> 4. Extract name, description, price, currency from the snapshot.
> 5. Trigger the ingredients modal. Try in order:
>    a. `agent-browser eval "document.querySelector('button[data-modal-handle=\"productIngredients\"]')?.click()"`
>       (Shopify / Fenty theme).
>    b. Otherwise search the snapshot for a button whose accessible
>       name matches `/full ingredients|ingredients/i` and click its
>       ref.
> 6. `agent-browser wait 1500`.
> 7. Extract the INCI paragraph:
>
>    ```
>    agent-browser eval --stdin <<'EOF'
>    const ps = Array.from(document.querySelectorAll('p'));
>    const inci = ps.find(p =>
>      /Aqua\/Water|Water,\s|Water\/Aqua/i.test(p.textContent) &&
>      p.textContent.split(',').length > 10);
>    inci ? inci.textContent.trim() : 'NOT_FOUND'
>    EOF
>    ```
>
>    If the heuristic misses, fall back to `agent-browser get text` on
>    the ref under the `FULL INGREDIENTS` heading from the snapshot.
> 8. Infer `subcategory` and `category` from the product's name +
>    description using the enum list. Prefer the most specific
>    subcategory; if none fit, `other`.
> 9. `agent-browser close` before returning.
> 10. Print exactly one line: `RESULT: <compact-JSON>` — or
>     `RESULT: NOT_FOUND <one-line reason>` if extraction failed.

### Cost

Token-expensive. Each subagent returns snapshots / DOM chunks and runs
a full classification — easily tens of thousands of tokens. A
14-product brand runs ~150k–400k tokens. Use only as fallback;
Firecrawl's 5-credit scrape is orders of magnitude cheaper for brands
that don't hide INCI.

### Parallelism

Chrome sessions are independent. Launch all subagents in one message so
they run concurrently. 5–10 in parallel is safe on a laptop; cap at
~10 to avoid Chrome memory pressure.
