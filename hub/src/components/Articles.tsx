import Image from 'next/image';
import Link from 'next/link';
import { Article } from '@/lib/articles';
import { getChannel } from '@/lib/channels';
export default function Articles({ items }: { items: Article[] }) {
  if (!items.length) return <p className="empty">The next story is taking shape. Articles will appear here as new videos are published.</p>;
  return <div className="article-grid">{items.map(a => <article className="card" key={a.id}>
    <Link className="eyebrow" style={{color: getChannel(a.channel)?.color}} href={`/c/${a.channel}`}>{getChannel(a.channel)?.name}</Link>
    {a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id) && <Link href={`/a/${a.slug}`}><Image className="thumbnail" src={`https://i.ytimg.com/vi/${a.youtube_id}/hqdefault.jpg`} alt="" width={480} height={360} sizes="(max-width: 800px) 100vw, 360px"/></Link>}
    <h3><Link href={`/a/${a.slug}`}>{a.title}</Link></h3>
    <p>{a.excerpt}</p><time dateTime={a.published_at}>{new Date(a.published_at).toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}</time>
  </article>)}</div>;
}
