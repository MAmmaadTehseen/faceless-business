import Link from 'next/link';
import { notFound } from 'next/navigation';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { article } from '@/lib/articles';
import { getChannel } from '@/lib/channels';
export const revalidate = 600;
// Articles are generated on first request, including slugs published after deployment.
export function generateStaticParams() { return []; }
export async function generateMetadata({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug);
  if (!a) return {};
  const title = a.meta_title || a.title;
  const description = a.meta_description || a.excerpt;
  return {title: {absolute: title}, description, openGraph: {
    type: 'article', title, description, url: `/a/${a.slug}`,
    publishedTime: a.published_at, authors: [getChannel(a.channel)?.name || 'Plainsight Media'],
  }};
}
export default async function ArticlePage({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug); if (!a) notFound();
  const c = getChannel(a.channel);
  const structuredData = [
    {'@context': 'https://schema.org', '@type': 'Article', headline: a.title,
      description: a.meta_description || a.excerpt, datePublished: a.published_at,
      mainEntityOfPage: `https://hub.ammaad.online/a/${a.slug}`,
      author: {'@type': 'Organization', name: c?.name || 'Plainsight Media',
        url: c ? `https://www.youtube.com/@${c.handle}` : 'https://hub.ammaad.online'}},
    ...(a.faqs?.length ? [{'@context': 'https://schema.org', '@type': 'FAQPage',
      mainEntity: a.faqs.map(f => ({'@type': 'Question', name: f.question,
        acceptedAnswer: {'@type': 'Answer', text: f.answer}}))}] : []),
  ];
  return <article className="reading"><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(structuredData).replace(/</g, '\\u003c')}}/><header className="article-header"><Link className="eyebrow" style={{color:c?.color}} href={`/c/${a.channel}`}>{c?.name}</Link><h1>{a.title}</h1><p>{a.excerpt}</p><time dateTime={a.published_at}>{new Date(a.published_at).toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}</time></header>
    <div className="prose">{(a.faqs?.length ? a.body_md.split('## Frequently asked questions')[0] : a.body_md).split('{{YOUTUBE}}').map((part,i) => <div key={i}>{i > 0 && (a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id) ? <iframe className="video" src={`https://www.youtube-nocookie.com/embed/${a.youtube_id}`} title={`Watch: ${a.title}`} loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/> : <p className="empty">The accompanying video will be available here soon.</p>)}<Markdown remarkPlugins={[remarkGfm]} components={{blockquote: ({children}) => <blockquote className="evidence-box">{children}</blockquote>}}>{part}</Markdown></div>)}</div>
    {Boolean(a.faqs?.length) && <section className="prose faq" aria-labelledby="faqs"><h2 id="faqs">Frequently asked questions</h2>{a.faqs?.map(f => <div key={f.question}><h3>{f.question}</h3><p>{f.answer}</p></div>)}</section>}
    <aside className="card"><h2>Keep exploring {c?.name}</h2><Link href={`/c/${a.channel}`}>All channel stories →</Link><nav className="socials" aria-label="Channel links">{c?.links.map(l => <a href={l.url} key={l.label}>{l.label} ↗</a>)}</nav></aside>
  </article>;
}
