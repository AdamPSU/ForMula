"""Schema for the filter LLM's structured output.

The LLM never emits SQL. It populates a `FilterIntent` whose fields map
1:1 onto a `WHERE`-clause grammar the runtime composes. The schema
itself is the allowlist: there is no field for `ingredient_text` or any
other domain-knowledge surface, so the LLM cannot express
ingredient-level filtering even if asked.
"""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from scraper.validation.models import (
    HairProductCategory,
    HairProductCurrency,
    HairProductSubcategory,
)


class FilterClause(BaseModel):
    """One AND-group of predicates against `products`.

    Multiple clauses are OR'd together at the SQL layer, which lets the
    LLM express "leave-in under $20 OR deep conditioner under $40" — the
    one realistic intent shape that doesn't fit a flat filter.

    At least one of `subcategories` or `categories` must be populated;
    a clause with only `price_max` or `currency` would match the entire
    catalog and is rejected.
    """

    subcategories: list[HairProductSubcategory] = Field(default_factory=list)
    categories: list[HairProductCategory] = Field(default_factory=list)
    price_max: float | None = None
    currency: HairProductCurrency | None = None

    @model_validator(mode="after")
    def _require_subcategory_or_category(self) -> Self:
        if not self.subcategories and not self.categories:
            raise ValueError(
                "each clause must populate at least one of "
                "`subcategories` or `categories`"
            )
        return self


class FilterIntent(BaseModel):
    """The full LLM response: one or more OR'd clauses."""

    clauses: list[FilterClause] = Field(min_length=1)


class FilterRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class FilterResponse(BaseModel):
    intent: FilterIntent
    products: list[dict]
    count: int
