-- Faceless business schema. Run once in Supabase SQL editor (or used by the SQLite fallback with minor type coercion).

create table if not exists content (
  id text primary key,                       -- slug: 2026-10-27-ai-agents-2027
  channel text not null default 'futurework',
  placeholder boolean default false,
  media_url text,
  kind text not null,                        -- long | short
  parent_id text references content(id),     -- shorts point at their long video
  topic text not null,
  title text not null,
  title_variants jsonb default '[]',          -- untested alternatives for optimize.py
  description text,
  script text,
  chapters jsonb default '[]',
  tags jsonb default '[]',
  duration_sec real,
  file_path text,                            -- local path during the run; artifact url after
  thumbnail_path text,
  qa_status text default 'pending',          -- pending | passed | failed
  qa_notes text,
  status text default 'draft',               -- draft | rendered | published | failed | killed
  claude_cost_usd real default 0,
  created_at timestamptz default now()
);

create table if not exists publications (
  id bigserial primary key,
  content_id text references content(id),
  platform text not null,                    -- youtube | instagram | facebook | tiktok
  media_key text,
  thumbnail_key text,
  platform_id text,                          -- video id / media id
  url text,
  privacy text,                              -- private | public | scheduled
  publish_at timestamptz,
  published_at timestamptz,
  status text default 'pending',             -- pending | live | failed
  error text,
  unique (content_id, platform)
);

create table if not exists metrics (
  id bigserial primary key,
  publication_id bigint references publications(id),
  captured_at timestamptz default now(),
  views bigint default 0,
  likes bigint default 0,
  comments bigint default 0,
  shares bigint default 0,
  ctr real,                                  -- youtube only
  avg_view_duration_sec real,                -- youtube only
  impressions bigint
);

create table if not exists comments (
  id bigserial primary key,
  publication_id bigint references publications(id),
  platform text not null,
  platform_comment_id text unique not null,
  author text,
  text text not null,
  posted_at timestamptz,
  flagged boolean default false,             -- legal/medical/abuse: never auto-reply
  flag_reason text,
  draft_reply text,
  reply_text text,
  reply_status text default 'new',           -- new | drafted | sent | skipped | failed
  reply_sent_at timestamptz,
  liked boolean default false,
  fetched_at timestamptz default now()
);

create table if not exists topic_queue (
  id bigserial primary key,
  channel text not null default 'futurework',
  topic text not null,
  source_url text,
  source_headline text,
  priority int default 0,                    -- higher first; dashboard can bump
  status text default 'queued',              -- queued | used | killed
  added_by text default 'claude',            -- claude | user
  created_at timestamptz default now()
);

create table if not exists costs (
  id bigserial primary key,
  at timestamptz default now(),
  step text not null,                        -- ideate | script | qa | engage | optimize | review | niche
  channel text,
  content_id text,
  model text,
  input_tokens int,
  cache_read_tokens int,
  output_tokens int,
  usd real
);

create table if not exists settings (
  key text primary key,
  value jsonb not null
);

insert into settings (key, value) values
  ('pipeline_paused', 'false'),
  ('long_videos_per_run', '1'),
  ('shorts_per_long', '4'),
  ('youtube_quota_units_per_day', '10000'),
  ('auto_reply', '{"youtube": true, "instagram": true, "facebook": true}'),
  ('auto_like', '{"facebook": true}'),
  ('max_replies_per_day', '40'),
  ('reply_tone_notes', '"Warm, direct, ask a follow-up question. Never argue."'),
  ('monthly_budget_usd', '95'),
  ('publish_privacy', '"private"'),
  ('niche_keywords', '["AI jobs", "layoffs automation", "future of work", "data breach", "cybersecurity scam", "AI company earnings", "remote work policy", "ransomware", "wages AI", "tech regulation"]'),
  ('tts_voice', '"en-US-AndrewMultilingualNeural"')
on conflict (key) do nothing;

create table if not exists runs (
  id bigserial primary key,
  started_at timestamptz default now(),
  finished_at timestamptz,
  workflow text,
  channel text,
  status text,
  log text
);

-- Row level security: dashboard uses the service role key server-side, so RLS stays simple.
alter table content enable row level security;
alter table publications enable row level security;
alter table metrics enable row level security;
alter table comments enable row level security;
alter table topic_queue enable row level security;
alter table costs enable row level security;
alter table settings enable row level security;
alter table runs enable row level security;

create table if not exists articles (
  id text primary key,
  content_id text references content(id),
  channel text,
  slug text unique,
  title text,
  excerpt text,
  body_md text,
  meta_title text,
  meta_description text,
  primary_keyword text,
  faqs jsonb,
  entities jsonb,
  quick_answer text,
  takeaways jsonb,
  youtube_id text,
  published_at timestamptz,
  created_at timestamptz default now()
);

alter table articles enable row level security;

create table if not exists quota_log (day text primary key, units int not null default 0);
alter table quota_log enable row level security;
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
