-- =============================================================================
-- ForMula — hair intakes
-- One row per quiz submission. Append-only; latest = the user's current
-- HairProfile. FK to public.profiles cascades on user deletion.
-- =============================================================================

create table public.hair_intakes (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.profiles(id) on delete cascade,
  quiz_version int not null,
  answers      jsonb not null,
  created_at   timestamptz not null default now()
);

create index hair_intakes_user_latest
  on public.hair_intakes (user_id, created_at desc);

alter table public.hair_intakes enable row level security;

create policy "hair_intakes read own"
  on public.hair_intakes for select using (auth.uid() = user_id);

create policy "hair_intakes insert own"
  on public.hair_intakes for insert with check (auth.uid() = user_id);
-- No update/delete policies: rows are immutable. Users retake by inserting
-- a new row; older intakes are preserved as history.
