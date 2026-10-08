-- LouieCorp newsroom automation, additive migration.
-- Run this once in Supabase SQL Editor before enabling GitHub Actions.

alter table public.articles
  alter column author_id drop not null;

create table if not exists public.newsroom_runs (
  id uuid primary key default gen_random_uuid(),
  track text not null check (track in ('news','knowledge')),
  mode text not null default 'auto',
  success boolean not null default false,
  article_id uuid references public.articles(id) on delete set null,
  error_message text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.newsroom_candidates (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  url text,
  track text not null check (track in ('news','knowledge')),
  importance_score integer,
  status text not null default 'discovered',
  article_id uuid references public.articles(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.newsroom_sources (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.newsroom_runs(id) on delete cascade,
  candidate_id uuid references public.newsroom_candidates(id) on delete cascade,
  url text not null,
  title text,
  publisher text,
  retrieved_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists newsroom_runs_created_idx on public.newsroom_runs(created_at desc);
create index if not exists newsroom_candidates_created_idx on public.newsroom_candidates(created_at desc);
create index if not exists newsroom_sources_candidate_idx on public.newsroom_sources(candidate_id);

alter table public.newsroom_runs enable row level security;
alter table public.newsroom_candidates enable row level security;
alter table public.newsroom_sources enable row level security;

-- No public or browser write access. The server-side GitHub Action uses the Supabase service role.
revoke all on public.newsroom_runs from anon, authenticated;
revoke all on public.newsroom_candidates from anon, authenticated;
revoke all on public.newsroom_sources from anon, authenticated;

-- Additive article metadata for editorial provenance and knowledge classification.
alter table public.articles add column if not exists newsroom_track text;
alter table public.articles add column if not exists newsroom_importance_score integer;
alter table public.articles add column if not exists image_caption text;
alter table public.articles add column if not exists image_license text;
alter table public.articles add column if not exists image_source_url text;
alter table public.articles add column if not exists review_status text default 'manual';

create index if not exists articles_newsroom_track_idx on public.articles(newsroom_track);
