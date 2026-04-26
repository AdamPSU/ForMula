"""Build the (system, user) pair for one selection LLM call.

A 'selection call' is one round of the TourRank tournament — the LLM
sees a group of n shuffled candidate products and returns the m it
considers the best fit for the user. The prompt is intentionally
*relative*, never absolute: we never ask 'is this good?' (the saturated
question that drove the v2 binary-judge plateau), only 'which of these
are best for this user?'.

Two facets matter for accuracy:

  - **HairProfile vocabulary alignment.** The user-profile section uses
    the same enum tokens as the rerank_doc YAML (curl_pattern, scalp,
    porosity, etc.), so the LLM's attention can match query tokens to
    doc tokens directly. Mirrors `cohere/query.py::_serialize_profile`.

  - **Description stripping.** rerank_doc embeds a `Description: ...`
    line that is verbatim scraped marketing copy (when present). It is
    an external-influence vector — drop it before judgment.
"""

from __future__ import annotations

from profiles.models import HairProfile

_SYSTEM_PROMPT = (
    "You are a senior cosmetic chemist helping a specific user pick "
    "haircare products that fit their hair. You will see the user's "
    "request, their hair profile, and a numbered set of candidate "
    "products represented by their INCI ingredient list and structured "
    "facets. Your job is to SELECT the best-fitting m products for "
    "this user.\n"
    "\n"
    "Judge by ingredient fit to the user's hair profile and request — "
    "never by brand, name, or marketing language (which has been "
    "withheld). Be ruthless: many products are plausible; pick the "
    "ones whose formulation actually matches this user. Do not "
    "speculate about brand identity from the INCI fingerprint.\n"
    "\n"
    "Output a single JSON object with key `selected` containing the m "
    "chosen document numbers in descending order of fit. Example for "
    "m=3: {\"selected\": [4, 1, 7]}. Do not output anything else."
)


def strip_description(rerank_doc: str) -> str:
    """Drop the `Description: ...` line from a rerank_doc YAML.

    Same single-line filter as the v2 judge used. rerank_doc is rendered
    as a flat sequence of single-line `Key: value` pairs; no multi-line
    YAML blocks. Pure string operation, no YAML parser needed.
    """
    return "\n".join(
        line for line in rerank_doc.splitlines()
        if not line.startswith("Description:")
    )


def serialize_profile(profile: HairProfile) -> str:
    """Compact one-line-per-field profile dump.

    Vocabulary mirrors `cohere/query.py` and the rerank_doc YAML keys so
    the cross-encoder-style attention has aligned tokens on both sides.
    Positives-only: omit `concerns` if empty, omit porosity when the
    user said 'unsure'.
    """
    lines: list[str] = [
        f"Hair type: {profile.curl_pattern}",
        f"Scalp: {profile.scalp_condition}",
        f"Density: {profile.density}",
        f"Strand thickness: {profile.strand_thickness}",
    ]
    if profile.concerns:
        lines.append(f"Concerns: {', '.join(profile.concerns)}")
    lines.append(f"Goals: {', '.join(profile.goals)}")
    if profile.product_absorption != "unsure":
        lines.append(f"Porosity: {profile.product_absorption}")
    lines.append(f"Routine: {profile.wash_frequency}")
    lines.append(f"Climate: {profile.climate}")
    lines.append(f"Drying: {profile.drying_method}")
    return "\n".join(lines)


def build_selection_prompt(
    *,
    query: str,
    profile: HairProfile,
    group_docs: list[tuple[int, str]],
    m: int,
) -> tuple[str, str]:
    """Compose (system, user) for one selection call.

    `group_docs` is `[(label_id, rerank_doc_yaml), ...]` of length n,
    where label_id is 1..n within this group (the LLM sees stable
    `Document N` labels per call; the caller maps each label back to a
    product UUID after parsing).
    """
    n = len(group_docs)
    body_lines = ["=== USER REQUEST ===", query.strip(), ""]
    body_lines.append("=== USER HAIR PROFILE ===")
    body_lines.append(serialize_profile(profile))
    body_lines.append("")
    body_lines.append("=== CANDIDATES ===")
    for label, doc in group_docs:
        body_lines.append(f"[Document {label}]:")
        body_lines.append(strip_description(doc))
        body_lines.append("")
    body_lines.append("=== TASK ===")
    body_lines.append(
        f"Select the {m} documents most relevant to this user's request "
        f"and profile, out of the {n} candidates above. Output a JSON "
        f"object with key 'selected' containing exactly {m} document "
        f"numbers (each in [1, {n}]), in descending order of fit. "
        "Output nothing else."
    )
    return _SYSTEM_PROMPT, "\n".join(body_lines)
