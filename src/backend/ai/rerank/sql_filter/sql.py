"""SQL composition + execution for the filter LLM.

Pure functions — no LLM, no I/O beyond the asyncpg fetch. The LLM never
touches SQL; runtime composes a parameterized SELECT from the validated
FilterIntent.

Layout per clause:
    ( <type-pred> AND <price-pred?> AND <currency-pred?> )

where:
- <type-pred> is `subcategory = ANY($N)`, `category = ANY($M)`, or
  `(subcategory = ANY($N) OR category = ANY($M))` when both are
  populated. The model validator guarantees at least one is populated.
- <price-pred> is `(price <= $K OR price IS NULL)` — NULL-tolerant
  because most products in the catalog have NULL prices.
- <currency-pred> is `(currency = $L OR currency IS NULL)` — same
  reason.

Clauses are OR'd together. There is intentionally no LIMIT — the
reranker is the consumer and wants every candidate.
"""

from __future__ import annotations

from typing import Any

from asyncpg import Connection, Record

from ai.rerank.sql_filter.models import FilterClause, FilterIntent

_BASE_SELECT = (
    "SELECT id, name, brand_id, subcategory, category, price, currency, "
    "ingredient_text, description, url "
    "FROM products "
    "WHERE scrape_status = 'success' "
    "AND ingredient_text IS NOT NULL"
)


def _build_clause(
    clause: FilterClause, params: list[Any]
) -> str:
    """Append clause params to `params`, return the SQL fragment.

    Mutating `params` in place keeps the placeholder numbering ($1, $2,
    …) trivially correct across all clauses.
    """
    type_preds: list[str] = []
    if clause.subcategories:
        params.append(list(clause.subcategories))
        type_preds.append(f"subcategory = ANY(${len(params)})")
    if clause.categories:
        params.append(list(clause.categories))
        type_preds.append(f"category = ANY(${len(params)})")

    # Validator guarantees at least one of subcategories / categories.
    type_pred_sql = (
        type_preds[0] if len(type_preds) == 1 else f"({' OR '.join(type_preds)})"
    )

    parts = [type_pred_sql]
    if clause.price_max is not None:
        params.append(float(clause.price_max))
        parts.append(f"(price <= ${len(params)} OR price IS NULL)")
    if clause.currency is not None:
        params.append(clause.currency)
        parts.append(f"(currency = ${len(params)} OR currency IS NULL)")

    return "(" + " AND ".join(parts) + ")"


def build_filter_sql(intent: FilterIntent) -> tuple[str, list[Any]]:
    """Compose the full parameterized SELECT for a FilterIntent."""
    params: list[Any] = []
    clause_sqls = [_build_clause(c, params) for c in intent.clauses]
    where_clauses = (
        clause_sqls[0] if len(clause_sqls) == 1 else " OR ".join(clause_sqls)
    )
    sql = f"{_BASE_SELECT} AND ({where_clauses})"
    return sql, params


async def apply_filter(conn: Connection, intent: FilterIntent) -> list[Record]:
    """Execute the composed query and return matching product rows."""
    sql, params = build_filter_sql(intent)
    return await conn.fetch(sql, *params)
