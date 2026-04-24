-- =============================================================================
-- Add universal 'other' subcategory as fallback for product pages that don't
-- fit any specific subcategory. Valid under any category (Python validator
-- permits it regardless of the category value).
-- =============================================================================

alter table products drop constraint products_subcategory_check;

alter table products add constraint products_subcategory_check
  check (subcategory is null or subcategory in (
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
    -- other (3: hair-perfume, bundle, plus universal fallback 'other')
    'hair-perfume',
    'bundle',
    'other'
  ));
