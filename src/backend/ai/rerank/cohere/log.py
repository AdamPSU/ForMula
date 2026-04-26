"""Append-only debug log for Cohere rerank calls. Discardable."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

_LOG_PATH = Path(__file__).resolve().parent / "log.txt"


def log_call(
    *,
    query: str,
    candidate_count: int,
    docs_sent: int,
    top_results: list[tuple[UUID, float]],
    elapsed_ms: float,
    error: str | None = None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"--- {ts} ---",
        f"query:\n{query}",
        f"candidates_in: {candidate_count}",
        f"docs_sent: {docs_sent}",
        f"elapsed_ms: {elapsed_ms:.1f}",
    ]
    if error:
        lines.append(f"error: {error}")
    else:
        lines.append("top_results:")
        for product_id, score in top_results:
            lines.append(f"  {product_id} {score:.4f}")
    lines.append("")
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
