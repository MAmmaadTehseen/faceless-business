-- No new tables, policies or grants. Existing publication RLS remains in force.
alter table public.publications add column if not exists status_changed_at timestamptz;
-- Historical failures have no known transition time: do not invent recent failures.
update public.publications set status_changed_at = published_at where status_changed_at is null and status = 'live';
alter table public.publications alter column status_changed_at set default now();
create or replace function public.publication_status_timestamp() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.status is distinct from old.status then new.status_changed_at = now();
  else new.status_changed_at = old.status_changed_at;
  end if;
  return new;
end $$;
drop trigger if exists publication_status_timestamp on public.publications;
create trigger publication_status_timestamp before update on public.publications
for each row execute function public.publication_status_timestamp();
revoke all on function public.publication_status_timestamp() from public, anon, authenticated;
