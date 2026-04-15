"""Per-request near-duplicate URL collapse before Exa /contents.

Embeds `{title} | {highlights}` for each /search result, then greedy-clusters
cosine > 0.97 and keeps the first-seen result per cluster.
"""

from __future__ import annotations

from ai.embeddings import embed

DEDUP_THRESHOLD = 0.97


def _signal(result) -> str:
    title = getattr(result, "title", None) or ""
    highlights = getattr(result, "highlights", None) or []
    return f"{title} | {' '.join(highlights)}".strip()


def _cosine(a: list[float], b: list[float]) -> float:
    # Inputs are L2-normalized by embed(), so dot product == cosine.
    return sum(x * y for x, y in zip(a, b))


def dedup_search_results(results: list) -> list:
    if len(results) <= 1:
        return list(results)
    signals = [_signal(r) for r in results]
    vectors = embed(signals)
    survivors: list = []
    survivor_vecs: list[list[float]] = []
    for r, vec in zip(results, vectors):
        if any(_cosine(vec, sv) > DEDUP_THRESHOLD for sv in survivor_vecs):
            continue
        survivors.append(r)
        survivor_vecs.append(vec)
    return survivors
