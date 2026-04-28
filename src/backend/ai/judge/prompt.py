"""Build the (system, user) pair for one selection LLM call.

A 'selection call' is one round of the TourRank tournament — the LLM
sees a group of n shuffled candidate products and returns the m it
considers the best fit for the user. The prompt is intentionally
*relative*, never absolute: we never ask 'is this good?' (the saturated
question that drove the v2 binary-judge plateau), only 'which of these
are best for this user?'.

Two facets matter for accuracy:

  - **Consistent vocabulary.** The profile section reuses the same
    HairProfile enum tokens (`curly`, `dryness`, `soaks`, …) that
    `rerank_doc` carries on the doc side, so the model can tie user
    attributes to doc facets without a translation step. Label strings
    (`Hair type:`, `Scalp:`, …) differ from the doc's `Hair types` /
    `Scalp fit` headings on purpose — values carry the signal, labels
    are scaffolding. The judge deliberately includes
    `chemical_treatment` and `heat_tool_frequency`, which the Cohere
    cross-encoder query (`cohere/query.py::build_query`) does not — a
    generative LLM can reason over them, a cross-encoder cannot.

  - **Description stripping.** `rerank_doc` embeds a `Description:`
    line of verbatim scraped marketing copy (when present). It is an
    external-influence vector — drop it before judgment. Stripped once
    at fetch time in `service.py::_fetch_rerank_docs`, not per call.
"""

from __future__ import annotations

from ai._persona import (
    COSMETIC_CHEMIST_IDENTITY,
    HAIR_LAWS,
    INCI_DISCIPLINE,
)
from profiles.models import HairProfile

_SYSTEM_PROMPT = (
    f"{COSMETIC_CHEMIST_IDENTITY} You will see the user's request, their "
    "hair profile, and a numbered set of candidate products represented "
    "by their INCI ingredient list and structured facets. Your job is to "
    "SELECT the best-fitting m products for this user.\n"
    "\n"
    f"{INCI_DISCIPLINE}\n"
    "\n"
    f"{HAIR_LAWS}\n"
    "\n"
    "=== HOW TO ANSWER ===\n"
    "Produce a single JSON object with two fields, in this order: "
    "`notes`, `selected`.\n"
    "\n"
    "  1. `notes` — work through the candidates against the laws and "
    "the user's profile. Surface the ingredient signals that fit or "
    "disqualify each contender. This is your reasoning before you "
    "commit; do not rank yet.\n"
    "  2. `selected` — your top-m, descending fit order.\n"
    "\n"
    "Only `selected` is read by the downstream system. `notes` exists "
    "so you reason before committing — per-field specifics are in the "
    "response schema."
)


def strip_description(rerank_doc: str) -> str:
    """Drop the `Description: ...` line from a rerank_doc YAML.

    `rerank_doc` is a flat sequence of single-line `Key: value` pairs;
    no multi-line blocks. Pure string operation. Called once per doc at
    fetch time (`service.py::_fetch_rerank_docs`), not in the per-call
    hot path.
    """
    return "\n".join(
        line for line in rerank_doc.splitlines()
        if not line.startswith("Description:")
    )


def serialize_profile(profile: HairProfile) -> str:
    """Compact one-line-per-field profile dump.

    Values reuse the HairProfile enum tokens that `rerank_doc` carries
    on the doc side, so the model sees the same vocabulary in both
    halves of the prompt. Positives-only: omit `concerns` if empty,
    omit porosity when 'unsure', omit chemical treatment when 'none',
    omit heat tools when 'never', omit `story` when blank — silence >
    false signal.

    The optional `Story:` line is the user's free-text personal-formulation
    history (things they've tried, what worked, what didn't). It lands as
    the trailing line so the structured enum block is read first; the
    `INCI_DISCIPLINE` persona instructs the model to treat any brand or
    product names inside it as ingredient-history hints, never as a
    match-by-brand signal.

    Diverges deliberately from `cohere/query.py::build_query`:
    chemical_treatment and heat_tool_frequency are included here but
    not there, because a generative LLM can reason over them and a
    cross-encoder reranker cannot. `story` is judge-only for the same
    reason.
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
    if profile.chemical_treatment != "none":
        lines.append(f"Chemical treatment: {profile.chemical_treatment}")
    if profile.heat_tool_frequency != "never":
        lines.append(f"Heat tools: {profile.heat_tool_frequency}")
    lines.append(f"Routine: {profile.wash_frequency}")
    lines.append(f"Climate: {profile.climate}")
    if profile.story:
        lines.append(f"Story: {profile.story}")
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
    product UUID after parsing). Docs are expected pre-stripped of
    their `Description:` line — see `service.py::_fetch_rerank_docs`.
    """
    n = len(group_docs)
    body_lines = ["=== USER REQUEST ===", query.strip(), ""]
    body_lines.append("=== USER HAIR PROFILE ===")
    body_lines.append(serialize_profile(profile))
    body_lines.append("")
    body_lines.append("=== CANDIDATES ===")
    for label, doc in group_docs:
        body_lines.append(f"[Document {label}]:")
        body_lines.append(doc)
        body_lines.append("")
    body_lines.append("=== TASK ===")
    body_lines.append(
        f"Select the {m} documents most relevant to this user's request "
        f"and profile out of the {n} candidates above, in descending fit "
        f"order. Follow the four steps from the system prompt."
    )
    return _SYSTEM_PROMPT, "\n".join(body_lines)
