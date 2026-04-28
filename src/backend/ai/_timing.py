"""Single-line timing emitter shared by chat / rerank / filter graphs.

Writes to `sys.stderr` so output surfaces alongside uvicorn's own log
lines — `print()` to stdout gets block-buffered through uvicorn's
reload subprocess and silently disappears in dev. One emitter, one
format, one place to retarget if we ever want to ship these to a
proper logger.
"""

from __future__ import annotations

import sys
from typing import Any


def log_timing(node: str, **fields: Any) -> None:
    parts = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"[timing] node={node} {parts}", file=sys.stderr, flush=True)
