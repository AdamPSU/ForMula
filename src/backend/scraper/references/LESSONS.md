# Scraper lessons

Append here when a real failure or user correction surfaces a recurring
pitfall. Static tool behavior and recipes do **not** belong here — those
live in `CLAUDE.md`. A lesson is a bug we've actually hit.

Format:

```
- **<short title>** — <what went wrong>. <what to do next time>.
```

- **Per-row DB commits after paid external calls** — 2026-04-23 a `run-extraction` batch of 42 URLs burned 210 Firecrawl credits when one CHECK-constraint violation (`subcategory='other'` existed in the Pydantic enum but not the DB CHECK) rolled back the single wrapping transaction, stranding every paid scrape as still-`pending`. When a function pays an external provider *then* writes to the DB, never wrap the writes in one transaction — let each row commit independently so a single bad row only fails itself.
- **Python enum and DB CHECK must stay in lockstep** — adding a value to `SUBCATEGORY_TO_CATEGORY` / the `HairProductSubcategory` Literal without the matching migration lets bad rows pass Pydantic and fail at write time. When editing the enum, always add (or update) the corresponding migration in the same change.
