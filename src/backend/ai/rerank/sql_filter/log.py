"""Append-only debug log for the filter LLM.

Discardable. `rm log.txt` whenever it grows noisy. Per-call entries
include the user input, raw LLM response, parsed intent, composed SQL +
params, and any validation traceback. Used during debugging — not a
production observability channel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_PATH = Path(__file__).resolve().parent / "log.txt"


def log_call(
    user_text: str,
    raw_response: str | None,
    parsed_intent_json: str | None,
    sql: str | None,
    params: list[Any] | None,
    row_count: int | None,
    error: str | None,
) -> None:
    """Append one entry. All args except `user_text` may be None when the
    corresponding stage didn't run (e.g. validation failed before SQL
    composition)."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"--- {ts} ---",
        f"user_text: {user_text!r}",
        f"raw_response: {raw_response!r}" if raw_response is not None else "raw_response: <none>",
        f"parsed_intent: {parsed_intent_json}" if parsed_intent_json else "parsed_intent: <none>",
        f"sql: {sql}" if sql else "sql: <none>",
        f"params: {params!r}" if params is not None else "params: <none>",
        f"row_count: {row_count}" if row_count is not None else "row_count: <none>",
    ]
    if error:
        lines.append(f"error: {error}")
    lines.append("")
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
