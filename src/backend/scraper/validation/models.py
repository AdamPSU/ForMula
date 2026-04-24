from typing import Literal, get_args

from pydantic import BaseModel, Field, computed_field


# Source of truth: subcategory → category.
# The Literal type below and the migration CHECK are both derived from these keys.
# Add or remove an entry here and both must be updated.
SUBCATEGORY_TO_CATEGORY: dict[str, str] = {
    # cleansing
    "shampoo": "cleansing",
    "clarifying-shampoo": "cleansing",
    "dry-shampoo": "cleansing",
    "co-wash": "cleansing",
    "scalp-scrub": "cleansing",
    # conditioning
    "conditioner": "conditioning",
    "leave-in-conditioner": "conditioning",
    "hair-mask": "conditioning",
    # styling
    "styling-cream": "styling",
    "curl-cream": "styling",
    "curl-custard": "styling",
    "hair-butter": "styling",
    "edge-control": "styling",
    "curl-refresher": "styling",
    "mousse": "styling",
    "gel": "styling",
    "pomade": "styling",
    "texture-spray": "styling",
    "hairspray": "styling",
    "shine-spray": "styling",
    "anti-frizz-spray": "styling",
    "heat-protectant": "styling",
    # treatments
    "bond-repair-treatment": "treatments",
    "protein-treatment": "treatments",
    "treatment": "treatments",
    "scalp-serum": "treatments",
    "scalp-treatment": "treatments",
    # oils
    "hair-oil": "oils",
    "pre-wash-oil": "oils",
    # tools
    "paddle-brush": "tools",
    "round-brush": "tools",
    "detangling-brush": "tools",
    "boar-bristle-brush": "tools",
    "hair-brush": "tools",
    "wide-tooth-comb": "tools",
    "fine-tooth-comb": "tools",
    "hair-comb": "tools",
    "hair-clip": "tools",
    "scrunchie": "tools",
    "microfiber-towel": "tools",
    "scalp-brush": "tools",
    "hair-dryer": "tools",
    "flat-iron": "tools",
    "curling-iron": "tools",
    "hot-air-brush": "tools",
    "diffuser": "tools",
    # accessories
    "silk-bonnet": "accessories",
    "silk-scarf": "accessories",
    "silk-pillowcase": "accessories",
    # other
    "hair-perfume": "other",
    "bundle": "other",
    # Universal fallback: the validator lets `other` pair with any category.
    "other": "other",
}


HairProductCategory = Literal[
    "cleansing",
    "conditioning",
    "styling",
    "treatments",
    "oils",
    "tools",
    "accessories",
    "other",
]

# Closed set of ISO 4217 codes we currently accept. Add more here AND
# regenerate the CHECK migration with `uv run python -m scraper dump-schema`
# when onboarding a brand outside this list.
HairProductCurrency = Literal[
    "USD",
    "GBP",
    "EUR",
    "CAD",
    "AUD",
    "JPY",
]

HairProductSubcategory = Literal[
    "shampoo",
    "clarifying-shampoo",
    "dry-shampoo",
    "co-wash",
    "scalp-scrub",
    "conditioner",
    "leave-in-conditioner",
    "hair-mask",
    "styling-cream",
    "curl-cream",
    "curl-custard",
    "hair-butter",
    "edge-control",
    "curl-refresher",
    "mousse",
    "gel",
    "pomade",
    "texture-spray",
    "hairspray",
    "shine-spray",
    "anti-frizz-spray",
    "heat-protectant",
    "bond-repair-treatment",
    "protein-treatment",
    "treatment",
    "scalp-serum",
    "scalp-treatment",
    "hair-oil",
    "pre-wash-oil",
    "paddle-brush",
    "round-brush",
    "detangling-brush",
    "boar-bristle-brush",
    "hair-brush",
    "wide-tooth-comb",
    "fine-tooth-comb",
    "hair-comb",
    "hair-clip",
    "scrunchie",
    "microfiber-towel",
    "scalp-brush",
    "hair-dryer",
    "flat-iron",
    "curling-iron",
    "hot-air-brush",
    "diffuser",
    "silk-bonnet",
    "silk-scarf",
    "silk-pillowcase",
    "hair-perfume",
    "bundle",
    "other",
]


# Pydantic generates the Firecrawl JSON schema from the Literal, but
# `_category_consistency` dispatches on the dict — drift between them would
# let bad rows pass validation. Fail at import instead.
assert set(SUBCATEGORY_TO_CATEGORY) == set(get_args(HairProductSubcategory)), (
    "SUBCATEGORY_TO_CATEGORY keys and HairProductSubcategory Literal values have drifted"
)


class ProductExtraction(BaseModel):
    """Schema Firecrawl's LLM fills when scraping a product page.

    Every field is nullable because many pages the crawler surfaces are not
    product pages (e.g. /about, /blog). Extract-only — never invent values.
    """

    name: str | None = Field(
        None,
        description=(
            "Exact product display name from the page title, H1, or add-to-cart "
            "block. Null if this is not a single-product page."
        ),
    )
    subcategory: HairProductSubcategory | None = Field(
        None,
        description=(
            "Pick the SINGLE most specific subcategory for this product. "
            "Mentally commit to a category (cleansing / conditioning / "
            "styling / treatments / oils / tools / accessories / other) "
            "before picking, and choose only from that category's "
            "sub-list below. The `category` column is derived from your "
            "subcategory in post-processing — you do not output it, so "
            "`subcategory` must be specific enough to identify the "
            "section unambiguously.\n"
            "\n"
            "Sub-lists:\n"
            "- cleansing: shampoo, clarifying-shampoo (deep-clean / "
            "detox), dry-shampoo (powder or aerosol applied to dry hair "
            "— this is the correct value for any product labeled 'Dry "
            "Shampoo'), co-wash, scalp-scrub (liquid / gel / powder "
            "exfoliant for the scalp — NOT the silicone brush).\n"
            "- conditioning: conditioner (rinse-out), "
            "leave-in-conditioner (any no-rinse conditioning product — "
            "cream, spray, mist — even if it advertises heat protection "
            "or frizz control), hair-mask (deep / intensive treatment "
            "mask — this is the correct value for any product labeled "
            "'Mask', 'Hair Mask', 'Renewal Mask', etc.).\n"
            "- styling: styling-cream (air-dry / smoothing / styling "
            "creams applied to damp hair — this is the correct value "
            "for any product labeled 'Air-Dry Cream', 'Smoothing "
            "Cream'), curl-cream, curl-custard, hair-butter, "
            "edge-control, curl-refresher, mousse, gel (finishing / "
            "styling gels — this is the correct value for any product "
            "labeled 'Gel' or 'Finishing Gel'), pomade, texture-spray, "
            "hairspray (finishing / hold sprays), shine-spray, "
            "anti-frizz-spray, heat-protectant.\n"
            "- treatments: bond-repair-treatment (Olaplex-style "
            "disulfide repair), protein-treatment, scalp-serum, "
            "scalp-treatment, treatment. `treatment` is ONLY for "
            "targeted repair products that don't fit a more specific "
            "sibling (bond-repair, protein, scalp-serum, "
            "scalp-treatment). DO NOT use `treatment` as a catch-all "
            "for uncategorizable products — if nothing in ANY sub-list "
            "fits, use `other`, not `treatment`. Dry shampoos are "
            "`dry-shampoo`, hair masks are `hair-mask`, scalp scrubs "
            "are `scalp-scrub`, styling creams are `styling-cream` — "
            "none of these are `treatment`.\n"
            "- oils: hair-oil (default), pre-wash-oil (only when the "
            "label says pre-shampoo / pre-wash).\n"
            "- tools: paddle-brush, round-brush, detangling-brush, "
            "boar-bristle-brush, hair-brush (bristled fallback); "
            "wide-tooth-comb, fine-tooth-comb, hair-comb (toothed — "
            "never cross with brushes); hair-clip, scrunchie, "
            "microfiber-towel, scalp-brush (silicone massager, NOT an "
            "exfoliant); hair-dryer, flat-iron, curling-iron, "
            "hot-air-brush, diffuser.\n"
            "- accessories: silk-bonnet, silk-scarf, silk-pillowcase.\n"
            "- other: hair-perfume, bundle (ANY multi-product page — "
            "never invent 'set', 'trio', etc.), other (universal "
            "fallback when nothing above fits).\n"
            "\n"
            "2-in-1 shampoo-conditioner → `shampoo` (primary function). "
            "Never concatenate two values. Null only if the page isn't "
            "a single-product page."
        ),
    )
    description: str | None = Field(
        None,
        description=(
            "Short marketing description, 1-2 sentences taken verbatim from "
            "this product's page (not a sibling product). Null if absent."
        ),
    )
    price: float | None = Field(
        None,
        description=(
            "Numeric product price AS DISPLAYED on the page — don't convert "
            "currencies, don't assume USD. For a price range (e.g. '$28-$64' "
            "for bundles with size options), return the low end (the default "
            "displayed value). Null if no price is visible on this product's "
            "page. The currency symbol or code on the page belongs in the "
            "`currency` field, not here."
        ),
    )
    currency: HairProductCurrency | None = Field(
        None,
        description=(
            "3-letter ISO 4217 currency code of the displayed `price`. Map "
            "from the symbol or context on the page: '$' on a US / .com site "
            "→ USD; '£' → GBP; '€' → EUR; 'C$' or Canadian context → CAD; "
            "'A$' or Australian context → AUD; '¥' Japanese yen → JPY. Prefer "
            "explicit ISO codes when the page lists one. Null if no price is "
            "visible, or if the currency cannot be determined unambiguously."
        ),
    )
    ingredient_text: str | None = Field(
        None,
        description=(
            "The COMPLETE, raw, comma-separated INCI ingredient list, verbatim "
            "from this product's label. Real INCI uses standardized cosmetic "
            "chemical nomenclature: 'WATER, GLYCERIN, CETYL ALCOHOL, CETEARYL "
            "ALCOHOL, BEHENTRIMONIUM METHOSULFATE, ...' (the trailing '...' is "
            "only illustrative — your output must not contain '...' or 'etc.').\n"
            "Return the full list from the first ingredient to the last, "
            "including any trailing 'may contain' or '(+/-)' section if "
            "present. Never truncate, summarize, abbreviate, or shorten — INCI "
            "lists are routinely 500–1500 characters and that is expected.\n"
            "Return null when:\n"
            "- No INCI ingredient list appears on this product's page.\n"
            "- The list shown is a materials / construction spec (e.g. 'boar "
            "bristle, nylon, wood handle') rather than INCI chemistry.\n"
            "- The ingredients belong to a sibling or related product (carousel, "
            "'shop similar', bundle constituent) — not this one.\n"
            "Do not paraphrase, translate, or reorder."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def category(self) -> HairProductCategory | None:
        """Derived from `subcategory` via SUBCATEGORY_TO_CATEGORY.

        `subcategory` is the only classification the LLM emits; the DB
        `category` column is populated from this property. Asking the LLM
        for both fields produced inconsistent pairs in practice
        (e.g. category='conditioning' + subcategory='gel'), costing a
        paid extraction per mismatch. Deriving eliminates that failure
        mode entirely.
        """
        if self.subcategory is None:
            return None
        return SUBCATEGORY_TO_CATEGORY[self.subcategory]  # type: ignore[return-value]
