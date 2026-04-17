-- ForMula initial schema: profiles, products catalog (pgvector), sessions.
-- Replaces the retired monolithic backend/schema.sql.

create extension if not exists pgcrypto;
create extension if not exists vector;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

-- profiles: 1:1 with auth.users. Holds the 14-field HairProfile.
create table profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  type text not null,
  density text not null,
  strand_thickness text not null,
  scalp_condition text not null,
  chemical_history text[] not null default '{}',
  chemical_recency text not null,
  heat_frequency text not null,
  concerns text[] not null default '{}',
  goals text[] not null default '{}',
  product_absorption text not null,
  wash_frequency text not null,
  climate text not null,
  styling_time text not null,
  free_text text not null default '',
  updated_at timestamptz not null default now()
);

-- products: global shared catalog. Canonical dedup via pgvector (HNSW cosine).
-- Embedding dimension matches BAAI/bge-small-en-v1.5 (ai/embeddings.py).
create table products (
  id uuid primary key default gen_random_uuid(),
  brand text not null,
  name text not null,
  url text not null,
  category text not null,
  price text,
  ingredients text[] not null default '{}',
  key_actives text[] not null default '{}',
  allergens text[] not null default '{}',
  embedding vector(384) not null,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index products_embedding_hnsw
  on products using hnsw (embedding vector_cosine_ops);

-- user_current_products: products the user already owns / uses.
create table user_current_products (
  user_id uuid not null references auth.users(id) on delete cascade,
  product_id uuid not null references products(id) on delete cascade,
  added_at timestamptz not null default now(),
  notes text,
  primary key (user_id, product_id)
);

-- sessions: one /research run.
create table sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  query text not null,
  status text not null default 'pending',
  summary text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create index sessions_user_created_idx on sessions (user_id, created_at desc);

-- session_angles: the queries the orchestrator generated for this run.
create table session_angles (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  position int not null,
  angle text not null,
  rationale text not null default ''
);
create index session_angles_session_idx on session_angles (session_id, position);

-- session_products: junction between a session and the shared catalog.
create table session_products (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  product_id uuid not null references products(id) on delete restrict,
  rank int,
  overall_score numeric,
  summary text,
  queried_at timestamptz not null,
  unique (session_id, product_id)
);
create index session_products_ranked_idx
  on session_products (session_id, rank) where rank is not null;

-- session_product_judge_panels: one row per (session_product, judge).
create table session_product_judge_panels (
  session_product_id uuid not null references session_products(id) on delete cascade,
  judge text not null,
  overall_score numeric not null,
  summary text not null,
  primary key (session_product_id, judge)
);

-- session_product_axis_verdicts: one row per (session_product, judge, axis).
create table session_product_axis_verdicts (
  session_product_id uuid not null references session_products(id) on delete cascade,
  judge text not null,
  axis text not null,
  score int not null check (score between 1 and 5),
  rationale text not null,
  evidence_tokens text[] not null default '{}',
  weaknesses text[] not null default '{}',
  sub_criteria jsonb not null,
  primary key (session_product_id, judge, axis)
);

-- RLS helper: session ownership check (avoids per-row re-evaluation in subqueries).
create or replace function private.user_owns_session(sid uuid) returns boolean
  language sql
  security definer
  set search_path = ''
  stable
as $$
  select exists (
    select 1 from public.sessions s
    where s.id = sid and s.user_id = auth.uid()
  );
$$;

-- RLS policies.
alter table profiles enable row level security;
create policy own_profile on profiles
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

alter table products enable row level security;
create policy products_read on products for select using (true);
-- No insert/update/delete policy → only service role can write.

alter table user_current_products enable row level security;
create policy own_current_products on user_current_products
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

alter table sessions enable row level security;
create policy own_sessions on sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

alter table session_angles enable row level security;
create policy own_angles on session_angles
  for all
  using (private.user_owns_session(session_id))
  with check (private.user_owns_session(session_id));

alter table session_products enable row level security;
create policy own_session_products on session_products
  for all
  using (private.user_owns_session(session_id))
  with check (private.user_owns_session(session_id));

alter table session_product_judge_panels enable row level security;
create policy own_judge_panels on session_product_judge_panels
  for all
  using (
    exists (
      select 1 from session_products sp
      where sp.id = session_product_id
        and private.user_owns_session(sp.session_id)
    )
  )
  with check (
    exists (
      select 1 from session_products sp
      where sp.id = session_product_id
        and private.user_owns_session(sp.session_id)
    )
  );

alter table session_product_axis_verdicts enable row level security;
create policy own_axis_verdicts on session_product_axis_verdicts
  for all
  using (
    exists (
      select 1 from session_products sp
      where sp.id = session_product_id
        and private.user_owns_session(sp.session_id)
    )
  )
  with check (
    exists (
      select 1 from session_products sp
      where sp.id = session_product_id
        and private.user_owns_session(sp.session_id)
    )
  );

-- Realtime: broadcast sessions status transitions to the frontend.
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (
       select 1 from pg_publication_tables
       where pubname = 'supabase_realtime'
         and schemaname = 'public'
         and tablename = 'sessions'
     ) then
    alter publication supabase_realtime add table sessions;
  end if;
end $$;
