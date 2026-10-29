import { articles } from '@/lib/articles';
import { absolute } from '@/lib/seo';
import { getChannel } from '@/lib/channels';
const xml = (s: string) => s.replace(/[<>&"']/g, c => ({'<':'&lt;', '>':'&gt;', '&':'&amp;', '"':'&quot;', "'":'&apos;'}[c]!));
export async function feed(channel?: string) {
  const items = await articles(channel);
  const title = channel ? getChannel(channel)!.name : 'Plainsight Media';
  const path = channel ? `/c/${channel}` : '/';
  const self = absolute(channel ? `/c/${channel}/feed.xml` : '/feed.xml');
  const body = `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>${xml(title)}</title><link>${xml(absolute(path))}</link><description>${xml(getChannel(channel || '')?.tagline || 'Clear perspectives on work, global power and science.')}</description><language>en</language><atom:link href="${xml(self)}" rel="self" type="application/rss+xml"/>${items.map(a => `<item><title>${xml(a.title)}</title><link>${xml(absolute(`/a/${a.slug}`))}</link><guid isPermaLink="true">${xml(absolute(`/a/${a.slug}`))}</guid><description>${xml(a.excerpt)}</description><pubDate>${new Date(a.published_at).toUTCString()}</pubDate></item>`).join('')}</channel></rss>`;
  return new Response(body, {headers: {'Content-Type':'application/rss+xml; charset=utf-8', 'Cache-Control':'public, s-maxage=600, stale-while-revalidate=60'}});
}
