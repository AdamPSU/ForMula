"""Single-query DB lookup for `rerank_doc`s by candidate id."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def fetch_rerank_docs(
    conn: asyncpg.Connection, ids: list[UUID]
) -> dict[UUID, str]:
    """Fetch `rerank_doc` for each id; rows with NULL doc are omitted.

    Returns a dict so callers can iterate `ids` in their preferred order
    while skipping ids that have no doc yet.
    """
    if not ids:
        return {}
    rows = await conn.fetch(
        "SELECT id, rerank_doc FROM products "
        "WHERE id = ANY($1::uuid[]) AND rerank_doc IS NOT NULL",
        ids,
    )
    return {row["id"]: row["rerank_doc"] for row in rows}
