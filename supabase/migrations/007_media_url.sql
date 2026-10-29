-- Public mp4 URL per Short so Reels can be posted from any runner once the YouTube copy goes public.
alter table content add column if not exists media_url text;
