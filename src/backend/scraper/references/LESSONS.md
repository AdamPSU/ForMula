# Scraper invariants

Bug-derived rules. Each was paid for by a real failure — treat none as
optional. Static tool behavior belongs in `CLAUDE.md`, not here.

For every rule below: short *why* lines so future agents can judge edge
cases instead of stripping the rule.

## Code

- **Per-row autocommit after every paid external call.** When a function pays Firecrawl (or any provider) and *then* writes to the DB, never wrap the writes in one transaction — one CHECK-constraint violation rolls back the entire batch and strands every paid scrape as `pending`. Per-row commits cap loss to 5 credits.

## Discovery: verify the seeded domain before spending credits

`brands.website_url` is wrong often enough that you cannot trust it. Confirm the apex actually serves the brand before any credit-spending tool.

- **DNS first.** `dig <apex>`. SERVFAIL → don't park. The fix is rarely a TLD swap; the canonical domain may share zero tokens with the brand name (e.g. a brand operating under a generic category domain like `naturalhair.org`). `WebSearch "<brand> official website DTC"`.
- **Resolve cross-domain redirects.** `curl -I <apex>`. Firecrawl doesn't follow cross-domain 301s, so `list-page-links` on the old path returns `[]` while the new host serves a healthy storefront. Always chase the `Location` header.
- **GoDaddy / parked-lander detection.** When `list-site-urls` surfaces only 1–2 URLs and one is `/lander`, `curl` the root and grep for `parking|wsimg.com/parking-lander|LANDER_SYSTEM`. Apex resolves and serves 200, it's just been repossessed; the real brand often lives on a hyphenated/alt variant.
- **Brand-name collision on short TLDs.** Short `.co` / `.io` apexes collide with VC-backed startups in unrelated industries (food, fintech, SaaS). When `list-site-urls` returns ≤3 URLs and none contain `/products|/shop|/collections|/store`, `inspect-product` the root before parking — if rendered markdown is unrelated to hair/beauty, search for `hello<brand>.com` / `<brand>beauty.com` / `<brand>haircare.com`.
- **Unrelated business on a name-matching domain.** Sometimes the apex resolves to a real but unrelated business (a salon, an agency). Symptom: `list-site-urls` returns only services pages; `list-page-links` on `/collections/all` returns 0 product links. Same fix as collision: confirm rendered content matches the brand, then search for the real domain.
- **Marketing-only apex with a parent conglomerate.** Legacy salon brands (Henkel/Zotos, L'Oréal Pro, P&G Pro, Kao/Goldwell, Shiseido Pro, Revlon Pro) routinely park their eponymous domain as a 1–2 page marketing landing while the real catalog lives at `{parent-storefront}/collections/<brand-slug>` (e.g. `zotosprofessional.com/collections/<slug>`). Always check parent-storefront before applying the "no DTC → park" rule. Do not conflate "no DTC on the brand's own site" with "no INCI anywhere."

## Catalog enumeration: union surfaces, never trust a single index

- **`/collections/all` is not authoritative on Shopify.** Merchants curate it; flagship SKUs can be missing. When discovery on `/collections/all` looks suspiciously thin, also try `/collections/shop-all` and per-category collections (`/collections/shop-shampoo-conditioners`, etc.). Union the URLs.
- **Sitemap XML when JS-rendered.** When `list-page-links` returns <5 products on `/collections/all?limit=250`, fetch `/sitemap_products_1.xml` (or `/sitemap.xml`) via `curl` and regex-extract `<loc>...</loc>`. Don't trust `/products.json` — Shopify can return a schema dump (typed shape descriptors, not real JSON).
- **No sitemap → union both axes.** When the site has no `/collections/all`-equivalent, no XML sitemap, AND `list-site-urls` returns <30 products, enumerate the merchandising-category axis (`/categories/<X>`) AND the brand-sub-line axis (`/brands/<brand>/<line>`) and union. Both are individually incomplete because the merchant curates which products appear in each index.
- **Pagination.** Append `?limit=250` and iterate `?page=N` until empty/stable.
- **Verify URL shape before staging.** Some WP themes emit relative `href="<slug>"` tags that `list-page-links` joins to the base URL, dropping a required `/<category>/` segment — every URL in `keep` then 404s. Sample 2–3 keep URLs with `curl -o /dev/null -w "%{http_code}"` before preflight; on 404, re-discover via category sub-indexes (`/products/<category>/`).
- **imweb.me brands.** Product URLs look like `/all/?idx=N` or `/haircare/?idx=N` (category path + `?idx=` query). `list-page-links` returns only nav links because the page is JS-rendered — extract via `curl | grep -oE '/[a-z]+/\?idx=[0-9]+'`. `filter-links` then classifies every one as `"reason": "list page"` because `?idx=` looks like pagination — skip filter-links or override its output for imweb sites.

## filter-links spot-checks: Grok has known false positives in `keep`

The skip side is not the only place misclassifications hide. Always eyeball the keep list before staging:

- **Accessory tokens.** Grep `keep` for `towel|brush|comb|filter`. URL-encoded unicode in slugs (e.g. TM symbol `%E2%84%A2`) flips classifications — a sibling URL without the encoding can be correctly skipped while the encoded one is kept.
- **Generic-noun bundle slugs.** Slugs like `/products/volume-fullness`, `/products/hydration-X`, `/products/strength-Y` on brands that visibly push bundles can be 3-product bundles dressed up as PDPs. The classifier has no lexical signal because there's no `bundle|kit|set|duo` token. `curl` the page and grep `<title>` for those tokens before staging.

## Preflight: trust `no_inci_text`

`inspect-product` returns `extraction_attempt.no_inci_text` — the LLM's own boolean verdict on whether this page yielded a real INCI list. It's the single principled signal:

- `False` → real INCI list extracted; proceed.
- `True` → no usable INCI on this URL, for any reason (wrong page type, image-only, B2B login, Cloudflare block, marketing-callout-only). Try another URL from the keep file. Two consecutive `True` results on different product URLs → park the brand.

Trust the verdict. Don't bolt on hallucination audits or token-vs-markdown diffs — the rare false positive isn't worth defensive scaffolding that adds tokens to every probe.

**Escape hatch:** `inspect-product --url <u> --full` adds raw markdown (10–50K tokens). Use only when `no_inci_text=True` contradicts something obvious — e.g. you can see in `--full` that there IS an INCI block Firecrawl's LLM missed.

## Salvage: per-line pruning beats all-or-nothing park

When most of the keep list extracts cleanly but a specific product line consistently returns null `ingredient_text` (an old packaging era, a hero-callout-only sub-collection like "Biotin"), drop that line's URLs from the keep file and proceed with the remainder. Don't park the whole brand for a confined failure.
