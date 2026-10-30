-- Public media bucket-relative path; nullable for existing articles.
alter table public.articles add column if not exists thumbnail_path text;
