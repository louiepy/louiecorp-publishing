-- Additive policies for the LouieCorp schema you already created.
-- Safe to run after your original SQL. Does not recreate tables.

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists articles_set_updated_at on public.articles;
create trigger articles_set_updated_at
before update on public.articles
for each row execute function public.set_updated_at();

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1), 'Editor'),
    'admin'
  )
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

drop policy if exists "Authors can view their articles" on public.articles;
create policy "Authors can view their articles"
on public.articles
for select
to authenticated
using (author_id = auth.uid());

drop policy if exists "Users can insert their profile" on public.profiles;
create policy "Users can insert their profile"
on public.profiles
for insert
to authenticated
with check (id = auth.uid());

drop policy if exists "Users can update their profile" on public.profiles;
create policy "Users can update their profile"
on public.profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "Authors can create tags" on public.tags;
create policy "Authors can create tags"
on public.tags
for insert
to authenticated
with check (true);

drop policy if exists "Authors can attach tags" on public.article_tags;
create policy "Authors can attach tags"
on public.article_tags
for insert
to authenticated
with check (
  exists (
    select 1 from public.articles a
    where a.id = article_id and a.author_id = auth.uid()
  )
);

drop policy if exists "Authors can detach tags" on public.article_tags;
create policy "Authors can detach tags"
on public.article_tags
for delete
to authenticated
using (
  exists (
    select 1 from public.articles a
    where a.id = article_id and a.author_id = auth.uid()
  )
);

insert into public.profiles (id, display_name, role)
select
  id,
  'Louie',
  'admin'
from auth.users
where email = 'louievolt@proton.me'
on conflict (id) do update
set
  display_name = excluded.display_name,
  role = excluded.role;

insert into storage.buckets (id, name, public)
values ('covers', 'covers', true)
on conflict (id) do nothing;

drop policy if exists "Public read covers" on storage.objects;
create policy "Public read covers"
on storage.objects
for select
using (bucket_id = 'covers');

drop policy if exists "Admins upload covers" on storage.objects;
create policy "Admins upload covers"
on storage.objects
for insert
to authenticated
with check (bucket_id = 'covers');

drop policy if exists "Admins update covers" on storage.objects;
create policy "Admins update covers"
on storage.objects
for update
to authenticated
using (bucket_id = 'covers')
with check (bucket_id = 'covers');

drop policy if exists "Admins delete covers" on storage.objects;
create policy "Admins delete covers"
on storage.objects
for delete
to authenticated
using (bucket_id = 'covers');

-- Additive: reusable bylines, without touching existing author_id (editor account).
create table if not exists public.authors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  bio text,
  photo_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.articles
  add column if not exists byline_author_id uuid references public.authors(id) on delete set null;

alter table public.articles
  add column if not exists document_url text;

alter table public.articles
  add column if not exists source_credit text;

alter table public.articles
  add column if not exists source_url text;

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

insert into storage.buckets (id, name, public)
values ('authors', 'authors', true)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('documents', 'documents', true)
on conflict (id) do nothing;

drop policy if exists "Public read authors photos" on storage.objects;
create policy "Public read authors photos"
on storage.objects
for select
using (bucket_id = 'authors');

drop policy if exists "Admins upload authors photos" on storage.objects;
create policy "Admins upload authors photos"
on storage.objects
for insert
to authenticated
with check (bucket_id = 'authors');

drop policy if exists "Admins update authors photos" on storage.objects;
create policy "Admins update authors photos"
on storage.objects
for update
to authenticated
using (bucket_id = 'authors')
with check (bucket_id = 'authors');

drop policy if exists "Public read documents" on storage.objects;
create policy "Public read documents"
on storage.objects
for select
using (bucket_id = 'documents');

drop policy if exists "Admins upload documents" on storage.objects;
create policy "Admins upload documents"
on storage.objects
for insert
to authenticated
with check (bucket_id = 'documents');

drop policy if exists "Admins update documents" on storage.objects;
create policy "Admins update documents"
on storage.objects
for update
to authenticated
using (bucket_id = 'documents')
with check (bucket_id = 'documents');

alter table public.articles
  add column if not exists featured boolean not null default false;

alter table public.articles
  add column if not exists editors_pick boolean not null default false;

alter table public.articles
  add column if not exists is_breaking boolean not null default false;

alter table public.articles
  add column if not exists view_count integer not null default 0;

alter table public.articles
  add column if not exists pdf_url text;

alter table public.authors
  add column if not exists title text;

insert into public.categories (name, slug)
select v.name, v.slug
from (values
  ('Politics', 'politics'),
  ('Business', 'business'),
  ('Technology', 'technology'),
  ('Africa', 'africa'),
  ('World', 'world'),
  ('Society', 'society'),
  ('Culture', 'culture'),
  ('Opinion', 'opinion'),
  ('Investigations', 'investigations'),
  ('Governance', 'governance'),
  ('Analysis', 'analysis')
) as v(name, slug)
where not exists (
  select 1 from public.categories c where c.slug = v.slug or c.name = v.name
);

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
