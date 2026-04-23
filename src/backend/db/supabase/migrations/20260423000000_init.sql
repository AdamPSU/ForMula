-- =============================================================================
-- ForMula — initial schema
-- Run in Supabase SQL Editor after creating a new project.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Shared trigger: keep updated_at current on any mutable table
-- ---------------------------------------------------------------------------
create or replace function set_updated_at()
 returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- =============================================================================
-- CATALOG PIPELINE
-- Tracks which brand websites we scrape and the history of each scrape run.
-- =============================================================================

create table brands (
  id          uuid    primary key default gen_random_uuid(),
  slug        text    unique not null,   -- 'curlsmith'
  name        text    not null,          -- 'Curlsmith'
  website_url text    unique not null,   -- 'https://curlsmith.com'
  -- Entry point for Firecrawl /map. Nullable so brands can be added manually
  -- before a seed page is chosen.
  seed_url    text,
  active      boolean not null default true,
  created_at  timestamptz default now()
);

-- One row per crawl attempt for a brand.
-- Lets us retry failed runs and track crawl frequency without touching brand data.
create table scrape_jobs (
  id            uuid primary key default gen_random_uuid(),
  brand_id      uuid not null references brands(id),
  status        text not null default 'pending',
  started_at    timestamptz,
  completed_at  timestamptz,
  pages_found   int,
  pages_scraped int,
  error         text,
  created_at    timestamptz default now(),
  constraint scrape_jobs_status check (
    status in ('pending', 'running', 'complete', 'failed')
  )
);

create index scrape_jobs_brand_idx   on scrape_jobs (brand_id, created_at desc);
create index scrape_jobs_pending_idx on scrape_jobs (status) where status in ('pending', 'running');

-- =============================================================================
-- PRODUCT CATALOG
-- Core table. ingredient_text is the raw INCI string from the product label
-- ("WATER, GLYCERIN, CETYL ALCOHOL, ...") — the judge reads this directly.
-- =============================================================================

create table products (
  id              uuid    primary key default gen_random_uuid(),
  brand_id        uuid    references brands(id),
  scrape_job_id   uuid    references scrape_jobs(id),
  -- Nullable: discovery inserts sparse url-only rows before extraction runs.
  name            text,
  product_type    text,
  url             text    unique,
  description     text,
  -- Ordered INCI string straight from the label.
  -- Source of truth for everything downstream (judge input).
  ingredient_text text,
  scrape_status   text    not null default 'pending',
  scrape_error    text,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now(),
  constraint products_scrape_status check (
    scrape_status in ('pending', 'success', 'missing', 'failed')
  )
);

create trigger products_updated_at
  before update on products for each row execute function set_updated_at();

create index products_brand_idx         on products (brand_id);
create index products_type_idx          on products (product_type);
create index products_scrape_status_idx on products (scrape_status);

-- =============================================================================
-- INCI INGREDIENT REGISTRY
-- One row per canonical ingredient. Built up incrementally as products are
-- parsed. function_tags drives the judge's understanding of what each
-- ingredient does without it having to reason about raw chemistry names.
-- =============================================================================

create table ingredients (
  id                 uuid    primary key default gen_random_uuid(),
  inci_name          text    unique not null,  -- 'GLYCERIN' (uppercase normalized)
  common_name        text,                     -- 'Glycerin'
  function_tags      text[]  not null default '{}',
  has_safety_concern boolean not null default false,
  created_at         timestamptz default now(),
  constraint ingredients_inci_uppercase check (inci_name = upper(trim(inci_name))),
  constraint ingredients_function_tags check (
    function_tags <@ array[
      'humectant', 'occlusive', 'emollient',
      'protein', 'hydrolyzed_protein', 'amino_acid', 'keratin',
      'fatty_alcohol', 'drying_alcohol',
      'surfactant', 'sulfate_surfactant',
      'silicone', 'water_soluble_silicone',
      'film_former', 'emulsifier', 'preservative',
      'fragrance', 'essential_oil',
      'antifungal', 'exfoliant', 'vitamin',
      'botanical_extract', 'conditioning_agent',
      'chelating_agent', 'ph_adjuster',
      'viscosity_modifier', 'solvent', 'other'
    ]::text[]
  )
);

create index ingredients_inci_idx         on ingredients (inci_name);
create index ingredients_functions_gin    on ingredients using gin (function_tags);

-- =============================================================================
-- ROW-LEVEL SECURITY
-- Product catalog is public read (no PII).
-- scrape_jobs: service role only — pipeline internals, no public exposure.
-- =============================================================================

alter table brands      enable row level security;
alter table scrape_jobs enable row level security;
alter table products    enable row level security;
alter table ingredients enable row level security;

create policy "public read" on brands      for select using (true);
create policy "public read" on products    for select using (true);
create policy "public read" on ingredients for select using (true);
-- scrape_jobs: intentionally no public policy — service role only
