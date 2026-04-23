-- =============================================================================
-- product_type / product_category taxonomy
-- Closed enum of 51 product_type values across 8 product_category sections.
-- Python (scraper/models.py: TYPE_TO_CATEGORY) is the source of truth and
-- derives product_category from product_type at insert time. These CHECKs
-- are defense-in-depth against writes that bypass the app.
-- =============================================================================

alter table products add column product_category text;

create index products_category_idx on products (product_category);

alter table products add constraint products_category_check
  check (product_category is null or product_category in (
    'cleansing',
    'conditioning',
    'styling',
    'treatments',
    'oils',
    'tools',
    'accessories',
    'other'
  ));

alter table products add constraint products_type_check
  check (product_type is null or product_type in (
    -- cleansing (5)
    'shampoo',
    'clarifying-shampoo',
    'dry-shampoo',
    'co-wash',
    'scalp-scrub',
    -- conditioning (3)
    'conditioner',
    'leave-in-conditioner',
    'hair-mask',
    -- styling (14)
    'styling-cream',
    'curl-cream',
    'curl-custard',
    'hair-butter',
    'edge-control',
    'curl-refresher',
    'mousse',
    'gel',
    'pomade',
    'texture-spray',
    'hairspray',
    'shine-spray',
    'anti-frizz-spray',
    'heat-protectant',
    -- treatments (5)
    'bond-repair-treatment',
    'protein-treatment',
    'treatment',
    'scalp-serum',
    'scalp-treatment',
    -- oils (2)
    'hair-oil',
    'pre-wash-oil',
    -- tools (17)
    'paddle-brush',
    'round-brush',
    'detangling-brush',
    'boar-bristle-brush',
    'hair-brush',
    'wide-tooth-comb',
    'fine-tooth-comb',
    'hair-comb',
    'hair-clip',
    'scrunchie',
    'microfiber-towel',
    'scalp-brush',
    'hair-dryer',
    'flat-iron',
    'curling-iron',
    'hot-air-brush',
    'diffuser',
    -- accessories (3)
    'silk-bonnet',
    'silk-scarf',
    'silk-pillowcase',
    -- other (2)
    'hair-perfume',
    'bundle'
  ));
