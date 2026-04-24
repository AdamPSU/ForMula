"""Prompt + schema for Firecrawl's JSON-format product extraction.

The Pydantic schema (`ProductExtraction`) lives in `scraper.validation`
because it is the durable domain type — its category / subcategory enums
double as the DB CHECK constraints. This module owns only the prompt string.
"""

EXTRACT_PROMPT = (
    "Extract structured data about ONE specific product from its product "
    "detail page. Scope strictly to this product — ignore 'shop similar' "
    "carousels, 'you may also like' rails, bundle-constituent listings, "
    "and sibling-product cards.\n"
    "\n"
    "Verbatim-extraction only: never paraphrase, translate, reorder, "
    "invent, or concatenate values.\n"
    "\n"
    "Null is always valid. Return null for every field on non-product "
    "pages (editorial, policy, ritual guides, collection pages). Return "
    "null for an individual field when the value isn't shown on this "
    "product's page, or when attribution is ambiguous. A wrong value is "
    "worse than a null value."
)
