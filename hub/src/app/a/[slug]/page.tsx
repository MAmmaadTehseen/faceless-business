import Link from 'next/link';
import { notFound } from 'next/navigation';
import Markdown from 'react-markdown';
import { article } from '@/lib/articles';
import { getChannel } from '@/lib/channels';
export const revalidate = 600;
// Articles are generated on first request, including slugs published after deployment.
export function generateStaticParams() { return []; }
export async function generateMetadata({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug); return {title:a?.title, description:a?.excerpt};
}
export default async function ArticlePage({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug); if (!a) notFound();
  const c = getChannel(a.channel);
  return <article className="reading"><header className="article-header"><Link className="eyebrow" style={{color:c?.color}} href={`/c/${a.channel}`}>{c?.name}</Link><h1>{a.title}</h1><p>{a.excerpt}</p><time dateTime={a.published_at}>{new Date(a.published_at).toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}</time></header>
    <div className="prose">{a.body_md.split('{{YOUTUBE}}').map((part,i) => <div key={i}>{i > 0 && (a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id) ? <iframe className="video" src={`https://www.youtube-nocookie.com/embed/${a.youtube_id}`} title={`Watch: ${a.title}`} loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/> : <p className="empty">The accompanying video will be available here soon.</p>)}<Markdown>{part}</Markdown></div>)}</div>
    <aside className="card"><h2>Keep exploring {c?.name}</h2><Link href={`/c/${a.channel}`}>All channel stories →</Link><nav className="socials" aria-label="Channel links">{c?.links.map(l => <a href={l.url} key={l.label}>{l.label} ↗</a>)}</nav></aside>
  </article>;
}
