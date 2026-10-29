-- Persist owner replies; automatic replies remain null.
alter table comments add column if not exists reply_text text;
