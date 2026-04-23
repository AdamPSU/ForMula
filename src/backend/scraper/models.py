from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field, model_validator


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
]


# Runtime safety: keep the dict and the Literal aligned.
assert set(SUBCATEGORY_TO_CATEGORY.keys()) == set(get_args(HairProductSubcategory)), (
    "SUBCATEGORY_TO_CATEGORY keys and HairProductSubcategory Literal values have drifted"
)
assert set(SUBCATEGORY_TO_CATEGORY.values()) <= set(get_args(HairProductCategory)), (
    "SUBCATEGORY_TO_CATEGORY values contain a category missing from HairProductCategory"
)


class ProductExtraction(BaseModel):
    """Schema Firecrawl's LLM fills when scraping a product page.

    Every field is nullable because many pages the crawler surfaces are not
    product pages (e.g. /about, /blog). Extract-only — never invent values.
    """

    name: Optional[str] = Field(
        None,
        description=(
            "Exact product display name from the page title, H1, or add-to-cart "
            "block. Null if this is not a single-product page."
        ),
    )
    subcategory: Optional[HairProductSubcategory] = Field(
        None,
        description=(
            "Pick the single most specific value from the allowed list. Rules:\n"
            "- Most specific wins. A scalp serum is 'scalp-serum', not "
            "'treatment'. A bond-repair product is 'bond-repair-treatment', "
            "not 'treatment'.\n"
            "- Styling vs treatment: products applied to wet or damp hair to "
            "influence how it dries or styles (creams, sprays, mousses, gels, "
            "pomades, finishing sprays, air-dry creams, smoothing creams) are "
            "styling subcategories — not 'treatment'. Treatments are targeted "
            "repair or nourishment products (bond repair, protein, hair mask, "
            "scalp treatment).\n"
            "- Tools: bristled items are brushes ('hair-brush', 'paddle-brush', "
            "'round-brush', 'detangling-brush', 'boar-bristle-brush', "
            "'scalp-brush'). Toothed items are combs ('wide-tooth-comb', "
            "'fine-tooth-comb', 'hair-comb'). Never classify a bristled item "
            "as a comb or vice versa.\n"
            "- Bundles, sets, trios, duos, collections, rituals, kits, and "
            "gift boxes — any page presenting multiple products together — "
            "return 'bundle'. Never invent 'set', 'trio', etc.\n"
            "- 2-in-1 shampoo-conditioner → 'shampoo' (primary function).\n"
            "- Never concatenate two values. Never return a value outside the "
            "enum. If nothing in the allowed list clearly applies, return null."
        ),
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Short marketing description, 1-2 sentences taken verbatim from "
            "this product's page (not a sibling product). Null if absent."
        ),
    )
    price: Optional[float] = Field(
        None,
        description=(
            "Displayed product price in the page's default currency (assume USD). "
            "For a price range (e.g. '$28–$64' for bundles with size options), "
            "return the low end (the default displayed value). Null if no price "
            "is visible on this product's page."
        ),
    )
    ingredient_text: Optional[str] = Field(
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

    @property
    def category(self) -> Optional[str]:
        """Derived from subcategory via SUBCATEGORY_TO_CATEGORY."""
        if self.subcategory is None:
            return None
        return SUBCATEGORY_TO_CATEGORY[self.subcategory]

    @model_validator(mode="after")
    def _category_consistency(self) -> "ProductExtraction":
        # Belt-and-suspenders: the Literal already constrains subcategory, but
        # a drift between SUBCATEGORY_TO_CATEGORY and the Literal would surface here.
        if self.subcategory is not None and self.subcategory not in SUBCATEGORY_TO_CATEGORY:
            raise ValueError(
                f"subcategory {self.subcategory!r} missing from SUBCATEGORY_TO_CATEGORY"
            )
        return self
