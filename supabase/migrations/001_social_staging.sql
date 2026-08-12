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
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists media_assets_cleanup_idx on public.media_assets(status, cleanup_after_epoch);
create table if not exists public.publish_jobs (
  job_id uuid primary key default gen_random_uuid(),
  content_id text not null,
  provider text not null default 'buffer',
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
  last_error text
);
alter table public.media_assets enable row level security;
alter table public.publish_jobs enable row level security;
alter table public.publish_targets enable row level security;
-- No anon policies: service-role-only backend access.
