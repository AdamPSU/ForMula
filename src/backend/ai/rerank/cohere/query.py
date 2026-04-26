"""Cohere query construction.

The reranker is a cross-encoder — it scores `query ↔ doc` jointly. To
maximize lexical alignment with `products.rerank_doc` (rendered by
`scraper/tools/descriptions.py`), the query reuses the same enum value
tokens (`curly`, `dryness`, `soaks`, `2_3_days`, …). Key strings need
not match the doc's `Hair types: …` / `Concerns addressed: …` headings
verbatim — the high-signal tokens are the values, not the labels.

Positives-only on this side too: `product_absorption == "unsure"` and
empty `concerns` collapse to omitted lines, matching the doc's
"silence > false positive" policy.
"""

from __future__ import annotations

from profiles.models import HairProfile


def build_query(profile: HairProfile, prompt: str) -> str:
    """Serialize free-text + HairProfile into a single Cohere query string.

    Free-text comes first so the cross-encoder anchors on user intent;
    HairProfile facets follow as one-line key/value pairs.
    """
    lines: list[str] = [f"User query: {prompt.strip()}", ""]

    lines.append(f"Hair type: {profile.curl_pattern}")
    lines.append(f"Scalp: {profile.scalp_condition}")
    lines.append(f"Density: {profile.density}")
    lines.append(f"Strand thickness: {profile.strand_thickness}")
    if profile.concerns:
        lines.append(f"Concerns: {', '.join(profile.concerns)}")
    lines.append(f"Goals: {', '.join(profile.goals)}")
    if profile.product_absorption != "unsure":
        lines.append(f"Porosity: {profile.product_absorption}")
    lines.append(f"Routine: {profile.wash_frequency}")
    lines.append(f"Climate: {profile.climate}")

    return "\n".join(lines)
