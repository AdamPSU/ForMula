"""Append-only debug log for the chat agent.

Discardable — `rm log.txt` whenever it grows noisy. One block per turn
captures the inputs, the LLM call payload, the assistant message, and
the resume value (when present). Used during debugging only; do not
parse this file from production code.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_PATH = Path(__file__).resolve().parent / "log.txt"


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)[:2000]
    except Exception:
        return repr(obj)[:2000]


def log_turn(
    *,
    phase: str,
    user_text: str | None,
    pending_warning: str | None,
    surfaced_count: int | None,
    sent_messages: list[dict[str, Any]] | None,
    assistant_content: str | None,
    resume_value: dict[str, Any] | None = None,
    final_error: str | None = None,
) -> None:
    """Append one block per chat turn."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"--- {ts} ---",
        f"phase: {phase}",
        f"user_text: {user_text!r}" if user_text is not None else "user_text: <none>",
        f"pending_warning: {pending_warning}" if pending_warning else "pending_warning: <none>",
        f"surfaced_count: {surfaced_count}" if surfaced_count is not None else "surfaced_count: <none>",
    ]
    if sent_messages is not None:
        lines.append(f"sent: {_safe_json(sent_messages)}")
    if assistant_content is not None:
        lines.append(f"assistant: {assistant_content[:1000]!r}")
    if resume_value is not None:
        lines.append(f"resume: {_safe_json(resume_value)}")
    if final_error:
        lines.append(f"final_error: {final_error}")
    lines.append("")
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
