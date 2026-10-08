-- Additive LouieCorp migration.
-- Safe to run in the Supabase SQL Editor.
-- Does not drop, recreate, or rename existing tables.
-- Preserves existing article and profile data.

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table if not exists public.authors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  bio text,
  photo_url text,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.authors
  add column if not exists title text;

alter table public.articles
  add column if not exists byline_author_id uuid references public.authors(id) on delete set null;

alter table public.articles
  add column if not exists document_url text;

alter table public.articles
  add column if not exists source_credit text;

alter table public.articles
  add column if not exists source_url text;

alter table public.articles
  add column if not exists editors_pick boolean not null default false;

alter table public.articles
  add column if not exists is_breaking boolean not null default false;

alter table public.articles
  add column if not exists view_count integer not null default 0;

alter table public.articles
  add column if not exists pdf_url text;

create index if not exists articles_byline_author_id_idx
  on public.articles (byline_author_id);

alter table public.authors enable row level security;

drop policy if exists "Public read authors" on public.authors;
create policy "Public read authors"
on public.authors
for select
using (true);

drop policy if exists "Authenticated insert authors" on public.authors;
create policy "Authenticated insert authors"
on public.authors
for insert
to authenticated
with check (true);

drop policy if exists "Authenticated update authors" on public.authors;
create policy "Authenticated update authors"
on public.authors
for update
to authenticated
using (true)
with check (true);

drop trigger if exists authors_set_updated_at on public.authors;
create trigger authors_set_updated_at
before update on public.authors
for each row execute function public.set_updated_at();

grant select on public.authors to anon, authenticated;
grant insert, update on public.authors to authenticated;

create or replace function public.increment_article_views(article_slug text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.articles
  set view_count = coalesce(view_count, 0) + 1
  where slug = article_slug
    and status = 'published';
end;
$$;

revoke all on function public.increment_article_views(text) from public;
grant execute on function public.increment_article_views(text) to anon, authenticated;
