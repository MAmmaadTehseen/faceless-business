-- Project-wide UTC accounting. Reservations include failed/uncertain API attempts.
create table if not exists quota_log (day text primary key, units int not null default 0);
alter table quota_log enable row level security;
insert into settings (key, value) values ('youtube_quota_units_per_day', '10000') on conflict (key) do nothing;
alter table content add column if not exists placeholder boolean default false;
alter table publications add column if not exists media_key text;
alter table publications add column if not exists thumbnail_key text;

create or replace function reserve_youtube_quota(p_units int, p_reserve int default 1000) returns boolean
language plpgsql security definer set search_path = public as $$
declare
  d text := to_char(now() at time zone 'UTC', 'YYYY-MM-DD');
  spent int;
  legacy int;
  budget int;
begin
  insert into quota_log(day, units) values(d, 0) on conflict(day) do nothing;
  select units into spent from quota_log where day = d for update;
  select coalesce(sum(1600 + case when c.thumbnail_path is not null then 50 else 0 end), 0)
    into legacy from publications p join content c on c.id = p.content_id
    where p.platform = 'youtube' and p.published_at >= (d::date::timestamp at time zone 'UTC')
      and p.published_at < ((d::date + 1)::timestamp at time zone 'UTC');
  select (value #>> '{}')::int into budget from settings where key = 'youtube_quota_units_per_day';
  if p_units < 1 or greatest(spent, legacy) + p_units > coalesce(budget, 10000) - greatest(p_reserve, 0) then
    return false;
  end if;
  update quota_log set units = greatest(spent, legacy) + p_units where day = d;
  return true;
end;
$$;
revoke all on function reserve_youtube_quota(int, int) from public;
grant execute on function reserve_youtube_quota(int, int) to service_role;
-- Private durable files for future sync runners.
insert into storage.buckets (id, name, public) values ('youtube-queue', 'youtube-queue', false)
on conflict (id) do nothing;
