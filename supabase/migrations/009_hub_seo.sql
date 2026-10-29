-- Optional sharing summary and accurate modification dates for article metadata/sitemaps.
alter table articles add column if not exists summary_for_og text;
alter table articles add column if not exists updated_at timestamptz;

create or replace function set_article_updated_at() returns trigger
language plpgsql set search_path = public as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
drop trigger if exists articles_updated_at on articles;
create trigger articles_updated_at before update on articles
for each row when (old.* is distinct from new.*)
execute function set_article_updated_at();
