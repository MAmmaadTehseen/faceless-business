-- YouTube Data API quota resets at midnight Pacific time (America/Los_Angeles), not UTC.
-- Counting in UTC made the pipeline overspend between 00:00 and 08:00 UTC (Google still on
-- its previous day; hit quotaExceeded on 2026-11-17) and under-use after 08:00 UTC.
-- Same signatures and grants as migrations 010 and 012; only the day key changes.
begin;
create or replace function reserve_youtube_quota(p_units int, p_uploads int, p_reserve int, p_upload_reserve int) returns boolean
language plpgsql security definer set search_path = pg_catalog, public as $$
declare
  d text := to_char(now() at time zone 'America/Los_Angeles', 'YYYY-MM-DD');
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

create or replace function public.record_youtube_retry_usage(p_units int, p_uploads int) returns boolean
language plpgsql security definer set search_path = pg_catalog, public as $$
begin
  if p_units < 0 or p_uploads < 0 or p_units + p_uploads <= 0 then return false; end if;
  insert into public.quota_log(day, units, uploads)
  values(to_char(now() at time zone 'America/Los_Angeles', 'YYYY-MM-DD'), p_units, p_uploads)
  on conflict(day) do update set units = public.quota_log.units + excluded.units,
    uploads = public.quota_log.uploads + excluded.uploads;
  return true;
end;
$$;
revoke all on function public.record_youtube_retry_usage(int,int) from public, anon, authenticated;
grant execute on function public.record_youtube_retry_usage(int,int) to service_role;
commit;
