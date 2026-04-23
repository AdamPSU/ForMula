
from typing import Optional

from pydantic import BaseModel, Field


class ProductExtraction(BaseModel):
    """Schema Firecrawl's LLM fills when scraping a product page.

    Every field is nullable because many pages the crawler surfaces are not
    product pages (e.g. /about, /blog). Extract-only — never invent values.
    """

    name: Optional[str] = Field(
        None,
        description="Product display name as shown on the page. Null if this is not a product page.",
    )
    product_type: Optional[str] = Field(
        None,
        description=(
            "Product category in lowercase: shampoo, conditioner, leave-in, "
            "styler, oil, mask, treatment, serum, cream, gel, mousse, etc. "
            "Null if it cannot be determined from the page."
        ),
    )
    description: Optional[str] = Field(
        None,
        description="Short marketing description, 1-2 sentences taken from the page. Null if absent.",
    )
    ingredient_text: Optional[str] = Field(
        None,
        description=(
            "The raw, comma-separated INCI ingredient list verbatim from the "
            "product label (e.g. 'WATER, GLYCERIN, CETYL ALCOHOL, ...'). "
            "Null if no ingredient list is visible on the page. "
            "Do not paraphrase, translate, or reorder."
        ),
    )
