-- Structured SEO fields for Plainsight Media articles.
alter table articles add column if not exists meta_title text;
alter table articles add column if not exists meta_description text;
alter table articles add column if not exists primary_keyword text;
alter table articles add column if not exists faqs jsonb;
alter table articles add column if not exists entities jsonb;
alter table articles add column if not exists quick_answer text;
alter table articles add column if not exists takeaways jsonb;
