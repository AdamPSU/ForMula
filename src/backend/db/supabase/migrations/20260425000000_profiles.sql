-- =============================================================================
-- ForMula — auth bridge
-- One row per signed-in user, auto-created by a trigger on auth.users insert.
-- This is the FK target for everything user-owned (hair_profiles, searches, …).
-- Reuses the public.set_updated_at() trigger function defined in the init migration.
-- =============================================================================

create table public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create trigger profiles_updated_at
  before update on public.profiles for each row execute function set_updated_at();

-- security definer + empty search_path is the Supabase-recommended hardening
-- for triggers that bridge from auth.* into public.*.
create function public.handle_new_user()
  returns trigger
  language plpgsql
  security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'display_name');
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;

create policy "profiles read own row"
  on public.profiles for select using (auth.uid() = id);

create policy "profiles update own row"
  on public.profiles for update using (auth.uid() = id);
-- No insert/delete policies: rows are created by the trigger and removed by
-- the FK cascade. Application code never inserts/deletes directly.
