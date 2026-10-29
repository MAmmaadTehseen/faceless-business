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
