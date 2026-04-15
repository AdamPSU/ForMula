"""Semantic query cache for the /research pipeline.

Key:   embedding of profile_to_summary(HairProfile)  (384-d bge-small-en-v1.5)
Value: final judged top-5 candidates + recommendation
Hit:   cosine >= 0.99 AND created_at within TTL
Store: Pinecone Serverless (index 'formula-query-cache')
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from pinecone import Pinecone, ServerlessSpec

from ai.embeddings import EMBEDDING_DIM, embed

INDEX_NAME = "formula-query-cache"
SIMILARITY_THRESHOLD = 0.99
TTL_SECONDS = 90 * 24 * 60 * 60

_pc: Pinecone | None = None
_index = None


def _get_index():
    global _pc, _index
    if _index is not None:
        return _index
    _pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    existing = {idx["name"] for idx in _pc.list_indexes()}
    if INDEX_NAME not in existing:
        _pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    _index = _pc.Index(INDEX_NAME)
    return _index


def _vector_id(profile_summary: str) -> str:
    return hashlib.sha1(profile_summary.encode("utf-8")).hexdigest()


def lookup(profile_summary: str) -> dict | None:
    """Return {'candidates': [...], 'recommendation': str} on hit, else None."""
    index = _get_index()
    [vec] = embed([profile_summary])
    min_created = time.time() - TTL_SECONDS
    res = index.query(
        vector=vec,
        top_k=1,
        include_metadata=True,
        filter={"created_at": {"$gte": min_created}},
    )
    matches = res.get("matches") or []
    if not matches:
        return None
    top = matches[0]
    if top["score"] < SIMILARITY_THRESHOLD:
        return None
    meta = top.get("metadata") or {}
    payload = meta.get("payload")
    if not payload:
        return None
    return json.loads(payload)


def upsert(profile_summary: str, candidates: list, recommendation: str | None) -> None:
    index = _get_index()
    [vec] = embed([profile_summary])
    payload = {
        "candidates": [c.model_dump(mode="json") for c in candidates],
        "recommendation": recommendation,
    }
    index.upsert(
        vectors=[
            {
                "id": _vector_id(profile_summary),
                "values": vec,
                "metadata": {
                    "created_at": time.time(),
                    "payload": json.dumps(payload),
                },
            }
        ]
    )
