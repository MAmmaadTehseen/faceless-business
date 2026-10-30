import StoryImage from './StoryImage';
import Link from 'next/link';
import { Article } from '@/lib/articles';
import { getChannel } from '@/lib/channels';
export const readTime = (a: Article) => `${Math.max(1, Math.ceil(a.body_md.split(/\s+/).length / 220))} min read`;
export const dateLabel = (value:string) => new Date(value).toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric',timeZone:'UTC'});
export function ArticleCard({a, lead = false}: {a:Article; lead?:boolean}) {
  const c = getChannel(a.channel);
  const image = a.resolved_image || {sources:[`/a/${encodeURIComponent(a.slug)}/opengraph-image`, '/artwork/futurework.svg']};
  return <article data-channel={a.channel} className={`story-card${lead ? ' lead-card' : ''}`} style={{borderTopColor:c?.color,'--label-accent':c?.color} as React.CSSProperties}>
    <Link className="card-image" href={`/a/${a.slug}`} tabIndex={-1} aria-hidden="true"><StoryImage sources={image.sources} priority={lead}/></Link>
    <div className="card-copy"><Link className="eyebrow channel-label" style={{'--label-accent':c?.color} as React.CSSProperties} href={`/c/${a.channel}`}>{c?.name}</Link><h3><Link href={`/a/${a.slug}`}>{a.title}</Link></h3><p className="card-dek">{a.excerpt}</p><div className="story-meta"><time dateTime={a.published_at}>{dateLabel(a.published_at)}</time><span> · {readTime(a)}</span></div></div>
  </article>;
}
export default function Articles({ items }: { items: Article[] }) {
  if (!items.length) return <p className="empty">The next story is taking shape. New perspectives will appear here as they are published.</p>;
  return <div className="article-grid">{items.map(a => <ArticleCard key={a.id} a={a}/>)}</div>;
}
