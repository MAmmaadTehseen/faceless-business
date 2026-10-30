-- Atomic accounting for owner-forced attempts; bypass local limits only.
begin;
create or replace function public.record_youtube_retry_usage(p_units int, p_uploads int) returns boolean
language plpgsql security definer set search_path = pg_catalog, public as $$
begin
  if p_units < 0 or p_uploads < 0 or p_units + p_uploads <= 0 then return false; end if;
  insert into public.quota_log(day, units, uploads)
  values(to_char(now() at time zone 'UTC', 'YYYY-MM-DD'), p_units, p_uploads)
  on conflict(day) do update set units = public.quota_log.units + excluded.units,
    uploads = public.quota_log.uploads + excluded.uploads;
  return true;
end;
$$;
revoke all on function public.record_youtube_retry_usage(int,int) from public, anon, authenticated;
grant execute on function public.record_youtube_retry_usage(int,int) to service_role;
commit;
