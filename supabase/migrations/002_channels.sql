-- Run once in the Supabase SQL editor (multi-channel support).
alter table content add column if not exists channel text not null default 'futurework';
alter table topic_queue add column if not exists channel text not null default 'futurework';
alter table costs add column if not exists channel text;
alter table runs add column if not exists channel text;
create index if not exists content_channel_idx on content(channel);
