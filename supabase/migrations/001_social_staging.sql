-- Temporary media staging for Buffer. TeraBox remains the durable archive.
create table if not exists public.media_assets (
  media_id text primary key,
  content_id text not null,
  object_path text not null unique,
  public_url text not null,
  mime_type text not null,
  size_bytes bigint not null,
  sha256 text not null,
  status text not null check (status in ('staged','scheduled','published','error')),
  cleanup_after timestamptz,
  cleanup_after_epoch bigint,
  source_provider text,
  source_reference text,
  source_fs_id bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists media_assets_cleanup_idx on public.media_assets(status, cleanup_after_epoch);
create table if not exists public.publish_jobs (
  job_id uuid primary key default gen_random_uuid(),
  content_id text not null,
  provider text not null default 'buffer',
  idempotency_key text not null,
  status text not null check (status in ('draft','scheduled','sent','error')),
  scheduled_at timestamptz,
  published_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.publish_targets (
  target_id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.publish_jobs(job_id) on delete cascade,
  account integer not null,
  platform text not null,
  channel_id text not null,
  buffer_post_id text,
  status text not null default 'scheduled',
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(job_id, account, platform, channel_id)
);
alter table public.media_assets enable row level security;
alter table public.publish_jobs enable row level security;
alter table public.publish_targets enable row level security;
-- No anon policies: service-role-only backend access.


-- Forward-compatible additions for installations created by the earlier schema.
alter table public.media_assets add column if not exists source_provider text;
alter table public.media_assets add column if not exists source_reference text;
alter table public.media_assets add column if not exists source_fs_id bigint;
alter table public.publish_jobs add column if not exists idempotency_key text;
-- A non-partial unique index is required for PostgREST
-- on_conflict=provider,idempotency_key atomic reservations/upserts. NULL legacy
-- rows remain permitted by PostgreSQL uniqueness semantics.
drop index if exists public.publish_jobs_provider_idempotency_idx;
create unique index if not exists publish_jobs_provider_idempotency_unique
  on public.publish_jobs(provider, idempotency_key);
alter table public.publish_targets add column if not exists created_at timestamptz not null default now();
alter table public.publish_targets add column if not exists updated_at timestamptz not null default now();
create unique index if not exists publish_targets_identity_idx
  on public.publish_targets(job_id, account, platform, channel_id);
create index if not exists publish_targets_buffer_post_idx
  on public.publish_targets(buffer_post_id) where buffer_post_id is not null;

-- Idempotent status reconciliation and automatic timestamp maintenance.
create or replace function public.set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
drop trigger if exists media_assets_updated_at on public.media_assets;
create trigger media_assets_updated_at before update on public.media_assets
for each row execute function public.set_updated_at();
drop trigger if exists publish_jobs_updated_at on public.publish_jobs;
create trigger publish_jobs_updated_at before update on public.publish_jobs
for each row execute function public.set_updated_at();
drop trigger if exists publish_targets_updated_at on public.publish_targets;
create trigger publish_targets_updated_at before update on public.publish_targets
for each row execute function public.set_updated_at();

-- Storage itself is private to the service role; the adapter exposes only the
-- deliberately stable public object URL recorded in media_assets.
insert into storage.buckets (id, name, public)
values ('social-staging', 'social-staging', true)
on conflict (id) do update set public = excluded.public;
