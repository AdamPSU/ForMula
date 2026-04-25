"""Append-only debug log for the writer LLM.

Discardable — `rm log.txt` whenever it grows noisy. One entry per
request, written by the route handler from the final graph state. Used
during debugging only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_PATH = Path(__file__).resolve().parent / "log.txt"


def log_from_state(state: dict[str, Any]) -> None:
    """Append one entry from a FilterState (or a partial dict on bubbled
    exceptions). Fields populated reflect how far the pipeline ran."""
    user_text = state.get("user_text", "<missing>")
    attempt = state.get("attempt")
    sql = state.get("sql")
    params = state.get("params")
    rows = state.get("rows")
    error = state.get("error")
    final_error = state.get("final_error")

    row_count = len(rows) if rows is not None else None

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"--- {ts} ---",
        f"user_text: {user_text!r}",
        f"attempt: {attempt}" if attempt is not None else "attempt: <none>",
        f"sql: {sql}" if sql else "sql: <none>",
        f"params: {params!r}" if params is not None else "params: <none>",
        f"row_count: {row_count}" if row_count is not None else "row_count: <none>",
    ]
    if error:
        lines.append(f"error: {error}")
    if final_error:
        lines.append(f"final_error: {final_error}")
    lines.append("")
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
