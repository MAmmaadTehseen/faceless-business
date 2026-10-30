import Link from 'next/link';
import { pageMetadata, absolute } from '@/lib/seo';
import { notFound } from 'next/navigation';
import { channels, getChannel } from '@/lib/channels';
import { articles } from '@/lib/articles';
import Articles from '@/components/Articles';
export const revalidate = 600;
export function generateStaticParams() { return channels.map(c => ({channel:c.key})); }
export async function generateMetadata({params}: {params: Promise<{channel:string}>}) {
  const c = getChannel((await params).channel); if (!c) notFound();
  const meta = pageMetadata(c.name, c.tagline, `/c/${c.key}`);
  return {...meta, alternates: {...meta.alternates, types: {'application/rss+xml': absolute(`/c/${c.key}/feed.xml`)}}};
}
export default async function Channel({params, searchParams}: {params: Promise<{channel:string}>; searchParams: Promise<{page?:string}>}) {
  const c = getChannel((await params).channel); if (!c) notFound();
  const all = await articles(c.key);
  const raw = Number((await searchParams).page || 1);
  const page = Number.isSafeInteger(raw) && raw > 0 ? raw : 1;
  const pages = Math.max(1, Math.ceil(all.length / 12));
  if (page > pages) notFound();
  return <div className="channel-page" data-hub="" data-channel={c.key}><section className="channel-header" style={{borderTopColor:c.color}}><p className="eyebrow channel-label" style={{'--label-accent':c.color} as React.CSSProperties}>A PLAINSIGHT MEDIA CHANNEL</p><h1>{c.name}</h1><p>{c.tagline}</p><nav className="socials" aria-label="Channel links"><a href={`https://www.youtube.com/@${c.handle}?sub_confirmation=1`}>Subscribe on YouTube ↗</a><a href={`/c/${c.key}/feed.xml`}>RSS feed ↗</a></nav></section><section aria-label="Stories"><Articles items={all.slice((page-1)*12,page*12)}/></section>{pages > 1 && <nav className="archive-pagination" aria-label="Archive pages">{page > 1 && <Link rel="prev" href={`/c/${c.key}?page=${page-1}`}>← Newer stories</Link>}<span>Page {page} of {pages}</span>{page < pages && <Link rel="next" href={`/c/${c.key}?page=${page+1}`}>Older stories →</Link>}</nav>}</div>;
}
