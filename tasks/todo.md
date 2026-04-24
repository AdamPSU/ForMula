# Scraper run plan

- [x] Read scraper instructions and confirm the happy-path commands.
- [x] Inspect current brand records, budget, and active terminal work to avoid duplicate runs.
- [x] Run the scrape pipeline for `kerasys`.
- [x] Run the scrape pipeline for `innisfree`.
- [x] Run the scrape pipeline for `aromatica`.
- [x] Run the scrape pipeline for `whamisa`.
- [x] Resolve the blocked `nature-republic` run without using browser fallback.
- [x] Verify job outcomes and record a short review.

## Review

- `Aromatica` and `Whamisa` completed successfully through the normal Firecrawl path.
- `Kerasys` and `Innisfree` were parked because discovery did not produce a viable same-domain hair catalog.
- `Nature Republic` hit the Firecrawl-blocked condition during preflight and was parked with a failed job instead of using browser fallback.
- Remaining Firecrawl credits after the run: `73,745`.
