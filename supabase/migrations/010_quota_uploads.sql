-- Independent UTC-day buckets; existing charges are retained, never refunded.
begin;
alter table public.quota_log add column if not exists uploads int not null default 0;
insert into public.settings (key, value) values ('youtube_uploads_per_day', '100') on conflict (key) do nothing;
drop function if exists public.reserve_youtube_quota(int, int);
create or replace function reserve_youtube_quota(p_units int, p_uploads int, p_reserve int, p_upload_reserve int) returns boolean
language plpgsql security definer set search_path = pg_catalog, public as $$
declare
  d text := to_char(now() at time zone 'UTC', 'YYYY-MM-DD');
  spent int;
  uploaded int;
  budget int;
  upload_budget int;
begin
  if p_units is null or p_uploads is null or p_reserve is null or p_upload_reserve is null
     or p_units < 0 or p_uploads < 0 or (p_units = 0 and p_uploads = 0) then
    return false;
  end if;
  insert into public.quota_log(day, units, uploads) values(d, 0, 0) on conflict(day) do nothing;
  select units, uploads into spent, uploaded from public.quota_log where day = d for update;
  select (value #>> '{}')::int into budget from public.settings where key = 'youtube_quota_units_per_day';
  select (value #>> '{}')::int into upload_budget from public.settings where key = 'youtube_uploads_per_day';
  if spent + p_units > coalesce(budget, 10000) - greatest(p_reserve, 0)
     or uploaded + p_uploads > coalesce(upload_budget, 100) - greatest(p_upload_reserve, 0) then
    return false;
  end if;
  update public.quota_log set units = spent + p_units, uploads = uploaded + p_uploads where day = d;
  return true;
end;
$$;
revoke all on function reserve_youtube_quota(int, int, int, int) from public, anon, authenticated;
grant execute on function reserve_youtube_quota(int, int, int, int) to service_role;
commit;
