-- Faceless business schema. Run once in Supabase SQL editor (or used by the SQLite fallback with minor type coercion).

create table if not exists content (
  id text primary key,                       -- slug: 2026-10-27-ai-agents-2027
  channel text not null default 'futurework',
  placeholder boolean default false,
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
  youtube_id text,
  published_at timestamptz,
  created_at timestamptz default now()
);

alter table articles enable row level security;

create table if not exists quota_log (day text primary key, units int not null default 0);
alter table quota_log enable row level security;
