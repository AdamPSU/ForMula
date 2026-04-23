-- =============================================================================
-- Rename: product_category → category, product_type → subcategory
-- Taxonomy semantics stay identical; only column names change.
-- =============================================================================

alter table products rename column product_category to category;
alter table products rename column product_type     to subcategory;

-- Keep index / constraint names aligned with the new column names.
alter index products_type_idx rename to products_subcategory_idx;

alter table products rename constraint products_type_check to products_subcategory_check;
