-- =============================================================================
-- products.price — per-product display price in the brand's default currency
-- (assumed USD). Numeric so we can filter/sort; nullable because many product
-- pages (bundles, tools) do not surface a single price value.
-- For pages with a price range, extraction stores the low end (the displayed
-- default price), not a range.
-- =============================================================================

alter table products add column price numeric(10, 2);
