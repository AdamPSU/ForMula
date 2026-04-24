-- =============================================================================
-- products.currency — 3-letter ISO 4217 code for the displayed price.
-- Previously we assumed USD in the price column's comment; that breaks once
-- we onboard UK / EU / etc. brands. The CHECK enumerates the closed set
-- defined by HairProductCurrency in scraper/validation/models.py — keep the
-- two in sync via `uv run python -m scraper dump-schema` when adding codes.
--
-- Crown Affair (slug = 'crown-affair') is known to be USD end-to-end, so we
-- backfill its rows in the same migration rather than re-running extraction.
-- =============================================================================

alter table products add column currency text;

alter table products add constraint products_currency_check
  check (currency is null or currency in (
    'USD',
    'GBP',
    'EUR',
    'CAD',
    'AUD',
    'JPY'
  ));

update products
   set currency = 'USD'
 where brand_id = (select id from brands where slug = 'crown-affair')
   and price is not null
   and currency is null;
