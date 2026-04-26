-- Two payload columns on `products` for the rerank-doc preprocessing
-- pipeline (scraper/tools/descriptions.py).
--
--   raw_doc    — JSON serialization of the LLM's RerankDocFacets output.
--                Audit trail and re-render source.
--   rerank_doc — Rendered YAML doc consumed by the runtime reranker
--                (Cohere Rerank 4). Positives-only, HairProfile-aligned.
--
-- Both nullable; existing rows are untouched until backfilled by
-- `python -m scraper generate-docs`.
--
-- No indexes — both are payloads pulled by primary key from the
-- candidate set after sql_filter, never query predicates.

alter table products
  add column raw_doc    text,
  add column rerank_doc text;
