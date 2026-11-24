-- Dashboard speed (2026-11-24). Additive: indexes and read-only functions only.
-- metrics had no index besides its primary key, so every per-publication read scanned the whole table.
create index if not exists metrics_pub_captured_idx on metrics(publication_id, captured_at desc, id desc);
create index if not exists comments_publication_idx on comments(publication_id);
create index if not exists content_parent_idx on content(parent_id);

-- Newest snapshot per publication: one row each instead of every snapshot of the last days.
create or replace function public.latest_metrics(p_ids bigint[])
returns setof metrics
language sql stable set search_path = pg_catalog, public as $$
  select m.* from unnest(p_ids) as pid
  cross join lateral (
    select * from metrics where publication_id = pid
    order by captured_at desc, id desc limit 1
  ) m;
$$;

-- Last snapshot at or before each requested time, per publication, without repeats.
-- Analytics only evaluates totals at these times, so it gets the same answers from far fewer rows.
create or replace function public.metric_snapshots_at(p_ids bigint[], p_times timestamptz[])
returns table(id bigint, publication_id bigint, captured_at timestamptz, views bigint, likes bigint, comments bigint, ctr double precision)
language sql stable set search_path = pg_catalog, public as $$
  select distinct on (m.id) m.id, m.publication_id, m.captured_at, m.views::bigint, m.likes::bigint, m.comments::bigint, m.ctr::double precision
  from unnest(p_ids) as pid
  cross join unnest(p_times) as t
  cross join lateral (
    select * from metrics where publication_id = pid and captured_at <= t
    order by captured_at desc, id desc limit 1
  ) m
  order by m.id;
$$;

revoke all on function public.latest_metrics(bigint[]) from public, anon, authenticated;
revoke all on function public.metric_snapshots_at(bigint[], timestamptz[]) from public, anon, authenticated;
grant execute on function public.latest_metrics(bigint[]) to service_role;
grant execute on function public.metric_snapshots_at(bigint[], timestamptz[]) to service_role;
