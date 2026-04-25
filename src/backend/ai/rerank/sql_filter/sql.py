"""AST validator for writer-emitted SQL.

The writer LLM produces parameterized Postgres SQL; this module gates it
before execution. Rules:

- Single SELECT statement only (no INSERT/UPDATE/DELETE/DROP/CTE-with-DML).
- Tables ⊆ {`products`, `brands`}; no schema qualifier (`auth.users`,
  `pg_catalog.*`, etc. all rejected).
- Columns ⊆ explicit allowlist. `ingredient_text` is structurally
  excluded — that's the whole point of v3.
- `SELECT *` rejected; columns must be enumerated.
- All data values must be `$N` placeholders. The only inline string
  literals allowed in the SQL are the three closed-enum sentinels:
  `'success'` (scrape_status), `'luxury'` and `'everyday'` (brands.tier).
  All inline numeric literals are rejected.
- Every query MUST filter `scrape_status = 'success'` somewhere in the
  WHERE — pending/failed/missing rows are never relevant downstream.

Pure function: no DB access, no LLM. Easy to unit-test the rules in
isolation.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

ALLOWED_TABLES: frozenset[str] = frozenset({"products", "brands"})

ALLOWED_COLUMNS_PRODUCTS: frozenset[str] = frozenset({
    "id", "name", "brand_id", "subcategory", "category",
    "price", "currency", "description", "url", "scrape_status",
})
ALLOWED_COLUMNS_BRANDS: frozenset[str] = frozenset({
    "id", "slug", "name", "tier",
})
ALLOWED_COLUMNS: frozenset[str] = ALLOWED_COLUMNS_PRODUCTS | ALLOWED_COLUMNS_BRANDS

# Closed-set sentinels the writer is allowed to emit inline. Everything
# else must come through a $N placeholder.
ALLOWED_INLINE_LITERALS: frozenset[str] = frozenset({"success", "luxury", "everyday"})


class SqlValidationError(Exception):
    """Raised by ast_validate on any rule violation."""


def ast_validate(sql: str) -> None:
    """Raise `SqlValidationError` if `sql` violates any rule. Otherwise
    return None and the SQL is safe to execute."""
    try:
        parsed = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise SqlValidationError(f"parse error: {e}") from e

    if len(parsed) != 1:
        raise SqlValidationError(
            f"must be exactly one statement (got {len(parsed)})"
        )

    tree = parsed[0]
    if not isinstance(tree, exp.Select):
        raise SqlValidationError(
            f"must be a SELECT statement (got {type(tree).__name__})"
        )

    for _ in tree.find_all(exp.Star):
        raise SqlValidationError(
            "SELECT * is not allowed; enumerate the columns you need"
        )

    for tbl in tree.find_all(exp.Table):
        if tbl.db:
            raise SqlValidationError(
                f"schema-qualified table {tbl.db}.{tbl.name} not allowed"
            )
        if tbl.name not in ALLOWED_TABLES:
            raise SqlValidationError(
                f"table {tbl.name!r} is not in the allowlist; only "
                f"{sorted(ALLOWED_TABLES)} are accessible"
            )

    for col in tree.find_all(exp.Column):
        if col.name == "ingredient_text":
            raise SqlValidationError(
                "column 'ingredient_text' is not available; use "
                "'subcategory', 'category', or 'description' for filtering"
            )
        if col.name not in ALLOWED_COLUMNS:
            raise SqlValidationError(
                f"column {col.name!r} is not in the allowed schema view"
            )

    for lit in tree.find_all(exp.Literal):
        # `$N` placeholders are exp.Parameter wrapping an inner Literal
        # holding the index. Skip those — the inner Literal is not
        # user data.
        if isinstance(lit.parent, exp.Parameter):
            continue
        if lit.is_string:
            if str(lit.this) not in ALLOWED_INLINE_LITERALS:
                raise SqlValidationError(
                    f"inline string literal {str(lit.this)!r} not allowed; "
                    f"use $N parameter placeholders"
                )
        else:
            raise SqlValidationError(
                f"inline numeric literal {lit.this!r} not allowed; "
                f"use $N parameter placeholders"
            )

    has_status = any(
        isinstance(eq, exp.EQ)
        and isinstance(eq.left, exp.Column)
        and eq.left.name == "scrape_status"
        and isinstance(eq.right, exp.Literal)
        and eq.right.is_string
        and str(eq.right.this) == "success"
        for eq in tree.find_all(exp.EQ)
    )
    if not has_status:
        raise SqlValidationError(
            "every query must filter scrape_status = 'success'"
        )
