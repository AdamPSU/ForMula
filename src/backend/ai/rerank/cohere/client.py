"""Lazy module-singleton AsyncClientV2.

The cohere SDK reads `CO_API_KEY` from env if no token is passed, but we
construct explicitly so a missing key fails loud at import-call time
rather than silently sending unauthenticated requests.
"""

from __future__ import annotations

import os

import cohere

_client: cohere.AsyncClientV2 | None = None


def get_client() -> cohere.AsyncClientV2:
    global _client
    if _client is None:
        key = os.environ.get("CO_API_KEY")
        if not key:
            raise RuntimeError("CO_API_KEY not set")
        _client = cohere.AsyncClientV2(api_key=key)
    return _client
