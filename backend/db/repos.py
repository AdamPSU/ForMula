"""All repository functions + input dataclasses for the FastAPI/asyncpg layer.

Grouped by aggregate for navigation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence
from uuid import UUID

from .pool import get_pool

if TYPE_CHECKING:
    from ai.orchestrator import HairProfile, ProductCandidate


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------

_PROFILE_COLUMNS = (
    "type",
    "density",
    "strand_thickness",
    "scalp_condition",
    "chemical_history",
    "chemical_recency",
    "heat_frequency",
    "concerns",
    "goals",
    "product_absorption",
    "wash_frequency",
    "climate",
    "styling_time",
    "free_text",
)


async def load_profile(user_id: UUID) -> "HairProfile | None":
    from ai.orchestrator import HairProfile
    row = await get_pool().fetchrow(
        f"select {', '.join(_PROFILE_COLUMNS)} from profiles where user_id = $1",
        user_id,
    )
    if row is None:
        return None
    return HairProfile(**dict(row))


async def save_profile(user_id: UUID, profile: "HairProfile") -> None:
    values = tuple(getattr(profile, c) for c in _PROFILE_COLUMNS)
    placeholders = ", ".join(f"${i}" for i in range(2, 2 + len(_PROFILE_COLUMNS)))
    updates = ", ".join(f"{c} = excluded.{c}" for c in _PROFILE_COLUMNS)
    await get_pool().execute(
        f"""
        insert into profiles (user_id, {', '.join(_PROFILE_COLUMNS)}, updated_at)
        values ($1, {placeholders}, now())
        on conflict (user_id) do update
        set {updates}, updated_at = now()
        """,
        user_id,
        *values,
    )


async def delete_profile(user_id: UUID) -> None:
    await get_pool().execute("delete from profiles where user_id = $1", user_id)


# ---------------------------------------------------------------------------
# products (shared catalog, pgvector HNSW dedup)
# ---------------------------------------------------------------------------

# cosine similarity > 0.97  ⇔  cosine distance (<=>) < 0.03
_DEDUP_COSINE_DISTANCE = 0.03


async def upsert_product(
    candidate: "ProductCandidate",
    embedding: list[float],
) -> tuple[UUID, bool]:
    """Return (product_id, created). Nearest-neighbor hit → reuse; else insert."""
    hit = await get_pool().fetchrow(
        """
        select id, embedding <=> $1 as distance
          from products
         order by embedding <=> $1
         limit 1
        """,
        embedding,
    )
    if hit is not None and hit["distance"] < _DEDUP_COSINE_DISTANCE:
        await get_pool().execute(
            "update products set last_seen_at = now() where id = $1",
            hit["id"],
        )
        return hit["id"], False
    row = await get_pool().fetchrow(
        """
        insert into products (
          brand, name, url, category, price,
          ingredients, key_actives, allergens, embedding
        ) values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        returning id
        """,
        candidate.brand,
        candidate.name,
        candidate.url,
        candidate.category,
        candidate.price,
        list(candidate.ingredients),
        list(candidate.key_actives),
        list(candidate.allergens),
        embedding,
    )
    return row["id"], True


# ---------------------------------------------------------------------------
# user_current_products
# ---------------------------------------------------------------------------


async def add_current_product(
    user_id: UUID, product_id: UUID, notes: str | None = None
) -> None:
    await get_pool().execute(
        """
        insert into user_current_products (user_id, product_id, notes)
        values ($1, $2, $3)
        on conflict (user_id, product_id) do update set notes = excluded.notes
        """,
        user_id,
        product_id,
        notes,
    )


async def remove_current_product(user_id: UUID, product_id: UUID) -> None:
    await get_pool().execute(
        "delete from user_current_products where user_id = $1 and product_id = $2",
        user_id,
        product_id,
    )


async def list_current_products(user_id: UUID) -> list[dict]:
    rows = await get_pool().fetch(
        """
        select p.id, p.brand, p.name, p.url, p.category, p.price,
               p.ingredients, p.key_actives, p.allergens,
               ucp.added_at, ucp.notes
          from user_current_products ucp
          join products p on p.id = ucp.product_id
         where ucp.user_id = $1
         order by ucp.added_at desc
        """,
        user_id,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# sessions + angles + session_products + per-judge panels + per-axis verdicts
# ---------------------------------------------------------------------------


@dataclass
class AxisVerdictInput:
    axis: str  # 'moisture_fit' | 'scalp_safety' | 'structural_fit'
    score: int
    rationale: str
    evidence_tokens: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    sub_criteria: dict[str, bool] = field(default_factory=dict)


@dataclass
class JudgePanelInput:
    judge: str
    overall_score: float
    summary: str
    axes: list[AxisVerdictInput] = field(default_factory=list)


@dataclass
class SessionProductInput:
    product_id: UUID
    rank: int | None
    overall_score: float
    summary: str
    queried_at: datetime
    judges: list[JudgePanelInput] = field(default_factory=list)


async def create_session(user_id: UUID, query: str) -> UUID:
    row = await get_pool().fetchrow(
        "insert into sessions (user_id, query) values ($1, $2) returning id",
        user_id,
        query,
    )
    return row["id"]


async def add_angles(session_id: UUID, angles: Sequence[str]) -> None:
    if not angles:
        return
    await get_pool().executemany(
        "insert into session_angles (session_id, position, angle) values ($1, $2, $3)",
        [(session_id, i, a) for i, a in enumerate(angles)],
    )


async def add_session_products(
    session_id: UUID,
    products: Sequence[SessionProductInput],
) -> None:
    if not products:
        return
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            sp_rows = await conn.fetch(
                """
                insert into session_products (
                  session_id, product_id, rank, overall_score, summary, queried_at
                )
                select $1, p.product_id, p.rank, p.overall_score, p.summary, p.queried_at
                  from unnest($2::uuid[], $3::int[], $4::numeric[], $5::text[], $6::timestamptz[])
                       as p(product_id, rank, overall_score, summary, queried_at)
                returning id, product_id
                """,
                session_id,
                [p.product_id for p in products],
                [p.rank for p in products],
                [p.overall_score for p in products],
                [p.summary for p in products],
                [p.queried_at for p in products],
            )
            sp_id_by_product: dict[UUID, UUID] = {r["product_id"]: r["id"] for r in sp_rows}

            panel_rows: list[tuple[Any, ...]] = []
            axis_rows: list[tuple[Any, ...]] = []
            for p in products:
                sp_id = sp_id_by_product[p.product_id]
                for jp in p.judges:
                    panel_rows.append((sp_id, jp.judge, jp.overall_score, jp.summary))
                    for ax in jp.axes:
                        axis_rows.append((
                            sp_id,
                            jp.judge,
                            ax.axis,
                            ax.score,
                            ax.rationale,
                            list(ax.evidence_tokens),
                            list(ax.weaknesses),
                            json.dumps(ax.sub_criteria),
                        ))
            if panel_rows:
                await conn.executemany(
                    """
                    insert into session_product_judge_panels
                      (session_product_id, judge, overall_score, summary)
                    values ($1, $2, $3, $4)
                    """,
                    panel_rows,
                )
            if axis_rows:
                await conn.executemany(
                    """
                    insert into session_product_axis_verdicts
                      (session_product_id, judge, axis, score, rationale,
                       evidence_tokens, weaknesses, sub_criteria)
                    values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                    """,
                    axis_rows,
                )


async def complete_session(session_id: UUID, summary: str | None) -> None:
    await get_pool().execute(
        """
        update sessions
           set status = 'complete',
               summary = $2,
               completed_at = now()
         where id = $1
        """,
        session_id,
        summary,
    )


async def fail_session(session_id: UUID) -> None:
    await get_pool().execute(
        "update sessions set status = 'failed', completed_at = now() where id = $1",
        session_id,
    )


async def list_sessions(user_id: UUID, limit: int = 50) -> list[dict]:
    rows = await get_pool().fetch(
        """
        select id, query, status, summary, created_at, completed_at
          from sessions
         where user_id = $1
         order by created_at desc
         limit $2
        """,
        user_id,
        limit,
    )
    return [dict(r) for r in rows]


async def get_session(user_id: UUID, session_id: UUID) -> dict | None:
    session = await get_pool().fetchrow(
        """
        select id, query, status, summary, created_at, completed_at
          from sessions
         where id = $1 and user_id = $2
        """,
        session_id,
        user_id,
    )
    if session is None:
        return None
    angles = await get_pool().fetch(
        "select position, angle, rationale from session_angles where session_id = $1 order by position",
        session_id,
    )
    products = await get_pool().fetch(
        """
        select sp.id as session_product_id,
               sp.rank, sp.overall_score, sp.summary, sp.queried_at,
               p.id as product_id,
               p.brand, p.name, p.url, p.category, p.price,
               p.ingredients, p.key_actives, p.allergens
          from session_products sp
          join products p on p.id = sp.product_id
         where sp.session_id = $1
         order by sp.rank nulls last, sp.overall_score desc nulls last
        """,
        session_id,
    )
    sp_ids = [r["session_product_id"] for r in products]
    panels = await get_pool().fetch(
        """
        select session_product_id, judge, overall_score, summary
          from session_product_judge_panels
         where session_product_id = any($1::uuid[])
        """,
        sp_ids,
    ) if sp_ids else []
    axes = await get_pool().fetch(
        """
        select session_product_id, judge, axis, score, rationale,
               evidence_tokens, weaknesses, sub_criteria
          from session_product_axis_verdicts
         where session_product_id = any($1::uuid[])
        """,
        sp_ids,
    ) if sp_ids else []

    panels_by_sp: dict[UUID, list[dict]] = {}
    for r in panels:
        panels_by_sp.setdefault(r["session_product_id"], []).append({
            "judge": r["judge"],
            "overall_score": float(r["overall_score"]),
            "summary": r["summary"],
        })
    axes_by_sp_judge: dict[tuple[UUID, str], list[dict]] = {}
    for r in axes:
        sc = r["sub_criteria"]
        if isinstance(sc, str):
            sc = json.loads(sc)
        axes_by_sp_judge.setdefault((r["session_product_id"], r["judge"]), []).append({
            "axis": r["axis"],
            "score": r["score"],
            "rationale": r["rationale"],
            "evidence_tokens": list(r["evidence_tokens"]),
            "weaknesses": list(r["weaknesses"]),
            "sub_criteria": sc,
        })

    candidates: list[dict] = []
    for r in products:
        sp_id = r["session_product_id"]
        judge_panels = panels_by_sp.get(sp_id, [])
        for jp in judge_panels:
            jp["axes"] = axes_by_sp_judge.get((sp_id, jp["judge"]), [])
        panel_scores = {jp["judge"]: jp["overall_score"] for jp in judge_panels}
        candidates.append({
            "session_product_id": sp_id,
            "product_id": r["product_id"],
            "rank": r["rank"],
            "overall_score": float(r["overall_score"]) if r["overall_score"] is not None else None,
            "summary": r["summary"],
            "queried_at": r["queried_at"],
            "brand": r["brand"],
            "name": r["name"],
            "url": r["url"],
            "category": r["category"],
            "price": r["price"],
            "ingredients": list(r["ingredients"]),
            "key_actives": list(r["key_actives"]),
            "allergens": list(r["allergens"]),
            "panel_scores": panel_scores,
            "judges": judge_panels,
        })

    return {
        **dict(session),
        "angles": [dict(a) for a in angles],
        "candidates": candidates,
    }
