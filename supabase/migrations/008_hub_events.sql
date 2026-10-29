-- First-party, cookie-free hub telemetry. No anonymous or authenticated access.
create table if not exists public.hub_events (
 id bigserial primary key, ts timestamptz not null default now(),
 event text not null check (event in ('pageview','heartbeat','click','scroll')),
 path text, slug text, channel text, referrer_host text,
 utm_source text, utm_medium text, utm_campaign text, country text,
 device text, browser text, visitor text, session text,
 seconds int, percent int, target text, href text
);
create index if not exists hub_events_ts_idx on public.hub_events(ts);
create index if not exists hub_events_slug_idx on public.hub_events(slug);
create index if not exists hub_events_visitor_idx on public.hub_events(visitor);
alter table public.hub_events enable row level security;
revoke all on public.hub_events from anon, authenticated;
revoke all on sequence public.hub_events_id_seq from anon, authenticated;
grant select, insert on public.hub_events to service_role;
grant usage, select on sequence public.hub_events_id_seq to service_role;

-- Aggregate inside Postgres: no raw history download or PostgREST row-limit truncation.
create or replace function public.hub_analytics(since timestamptz, until_ts timestamptz, channel_key text default null)
returns jsonb language sql stable security invoker set search_path = public as $$
with raw as materialized (
 select h.*, coalesce(a.channel,h.channel) as article_channel
 from hub_events h left join articles a on a.slug=h.slug
 where h.ts >= since and h.ts < until_ts
 and (channel_key is null or coalesce(a.channel,h.channel)=channel_key)
), e as (
 select raw.*, count(*) filter(where event='pageview') over(partition by visitor,session,path order by ts,id) as visit from raw
), pages as (
 select visitor,session,path,slug,max(article_channel) as channel,
 count(*) filter(where event='pageview') as views,
 coalesce(max(seconds),0) as seconds,coalesce(max(percent),0) as depth,
 count(*) filter(where event='click' and target='youtube_embed') as embeds,
 count(*) filter(where event='click' and target in ('youtube_embed','youtube_channel')) as youtube
 from e group by visitor,session,path,slug,visit
), sessions as (
 select visitor,session,sum(views) as views,sum(seconds) as seconds from pages group by visitor,session
), stats as (
 select count(*) filter(where event='pageview') as views,
 count(distinct visitor) filter(where event='pageview') as uniques,
 count(distinct (visitor,session)) filter(where event='pageview') as sessions,
 count(*) filter(where event='click' and target in ('youtube_embed','youtube_channel')) as youtube
 from e
), article_stats as (
 select slug,sum(views) as views,count(distinct visitor) filter(where views>0) as uniques,
 coalesce(round(sum(seconds)::numeric/nullif(sum(views),0),1),0) as seconds,
 sum(embeds) as embeds,sum(youtube) as youtube from pages where slug is not null
 group by slug order by sum(views) desc limit 10
), channel_stats as (
 select channel,sum(views) as views,sum(youtube) as youtube from pages where channel is not null group by channel
), dimensions as (
 select 'referrers' as kind,coalesce(referrer_host,'Direct') as name,count(*) as value from e where event='pageview' group by 2
 union all select 'sources',coalesce(utm_source,'None'),count(*) from e where event='pageview' group by 2
 union all select 'countries',coalesce(country,'Unknown'),count(*) from e where event='pageview' group by 2
 union all select 'devices',coalesce(device,'Unknown'),count(*) from e where event='pageview' group by 2
 union all select 'outbound',target,count(*) from e where event='click' and target is not null group by 2
), ranked as (select *,row_number() over(partition by kind order by value desc,name) as rank from dimensions)
select jsonb_build_object(
 'total',(select to_jsonb(stats) from stats),
 'seconds',(select coalesce(round(sum(seconds)::numeric/nullif(sum(views),0),1),0) from pages),
 'scroll',(select coalesce(percentile_cont(0.5) within group(order by depth),0) from pages where views>0),
 'bounce',(select coalesce(round(100.0*count(*) filter(where views=1 and seconds<10)/nullif(count(*),0),1),0) from sessions where views>0),
 'articles',coalesce((select jsonb_agg(to_jsonb(article_stats)) from article_stats),'[]'::jsonb),
 'channels',coalesce((select jsonb_agg(to_jsonb(channel_stats)) from channel_stats),'[]'::jsonb),
 'daily',coalesce((select jsonb_agg(jsonb_build_object('date',day,'views',views) order by day) from (
 select to_char(ts at time zone 'UTC','YYYY-MM-DD') as day,count(*) views from e where event='pageview' group by 1) d),'[]'::jsonb),
 'dimensions',coalesce((select jsonb_agg(to_jsonb(ranked)-'rank') from ranked where rank<=10),'[]'::jsonb)
);
$$;
revoke all on function public.hub_analytics(timestamptz,timestamptz,text) from public,anon,authenticated;
grant execute on function public.hub_analytics(timestamptz,timestamptz,text) to service_role;
