import 'server-only';
import { createClient } from '@supabase/supabase-js';

export type Article = {
  id: string; content_id: string; channel: string; slug: string; title: string;
  meta_title: string | null; meta_description: string | null; primary_keyword: string | null;
  faqs: {question: string; answer: string}[] | null; entities: string[] | null;
  quick_answer: string | null; takeaways: string[] | null;
  excerpt: string; body_md: string; youtube_id: string | null; published_at: string;
};
function db() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { fetch: (input, init) => fetch(input, { ...init, next: { revalidate: 600 } }) },
  });
}
export async function articles(channel?: string): Promise<Article[]> {
  const client = db();
  if (!client) return [];
  let query = client.from('articles').select('*').not('published_at', 'is', null)
    .lte('published_at', new Date().toISOString()).order('published_at', { ascending: false });
  if (channel) query = query.eq('channel', channel);
  const { data, error } = await query;
  if (error) throw new Error('Unable to load articles');
  return data as Article[];
}
export async function article(slug: string): Promise<Article | null> {
  const client = db();
  if (!client) return null;
  const { data, error } = await client.from('articles').select('*').eq('slug', slug)
    .not('published_at', 'is', null).lte('published_at', new Date().toISOString()).maybeSingle();
  if (error) throw new Error('Unable to load article');
  return data as Article | null;
}
