import Link from 'next/link';
import { notFound } from 'next/navigation';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Articles from '@/components/Articles';
import Video from '@/components/Video';
import { absolute, pageMetadata } from '@/lib/seo';
import { article, articles } from '@/lib/articles';
import { getChannel } from '@/lib/channels';
export const revalidate = 600;
// Articles are generated on first request, including slugs published after deployment.
export function generateStaticParams() { return []; }
export async function generateMetadata({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug);
  if (!a) return {};
  const title = a.meta_title || a.title;
  const description = a.meta_description || a.excerpt;
  const meta = pageMetadata(title, a.summary_for_og || description, `/a/${a.slug}`, `/a/${a.slug}/opengraph-image`);
  return {...meta, description, openGraph: {...meta.openGraph, type: 'article', publishedTime: a.published_at,
    modifiedTime: a.updated_at || a.published_at, authors: [getChannel(a.channel)?.name || 'Plainsight Media']}};
}
export default async function ArticlePage({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug); if (!a) notFound();
  const c = getChannel(a.channel);
  const siblings = await articles(a.channel);
  const index = siblings.findIndex(item => item.slug === a.slug);
  const previous = index >= 0 ? siblings[index + 1] : undefined;
  const next = index > 0 ? siblings[index - 1] : undefined;
  const related = siblings.filter(item => item.slug !== a.slug).slice(0, 3);
  const structuredData = [
    {'@context': 'https://schema.org', '@type': 'Article', headline: a.title,
      description: a.meta_description || a.excerpt, datePublished: a.published_at,
      dateModified: a.updated_at || a.published_at,
      image: absolute(`/a/${a.slug}/opengraph-image`),
      publisher: {'@type': 'Organization', name: 'Plainsight Media', url: absolute('/')},
      mainEntityOfPage: absolute(`/a/${a.slug}`),
      author: {'@type': 'Organization', name: c?.name || 'Plainsight Media',
        url: c ? `https://www.youtube.com/@${c.handle}` : absolute('/')}},
    {'@context':'https://schema.org', '@type':'BreadcrumbList', itemListElement: [
      {'@type':'ListItem', position:1, name:'Home', item:absolute('/')},
      {'@type':'ListItem', position:2, name:c?.name || a.channel, item:absolute(`/c/${a.channel}`)},
      {'@type':'ListItem', position:3, name:a.title, item:absolute(`/a/${a.slug}`)},
    ]},
    ...(a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id) ? [{'@context':'https://schema.org', '@type':'VideoObject',
      name:a.title, description:a.meta_description || a.excerpt, thumbnailUrl:`https://i.ytimg.com/vi/${a.youtube_id}/hqdefault.jpg`,
      uploadDate:a.published_at, embedUrl:`https://www.youtube-nocookie.com/embed/${a.youtube_id}`}]: []),
    ...(a.faqs?.length ? [{'@context': 'https://schema.org', '@type': 'FAQPage',
      mainEntity: a.faqs.map(f => ({'@type': 'Question', name: f.question,
        acceptedAnswer: {'@type': 'Answer', text: f.answer}}))}] : []),
  ];
  return <article className="reading" data-hub="" data-slug={a.slug} data-channel={a.channel}><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(structuredData).replace(/</g, '\\u003c')}}/><header className="article-header"><Link className="eyebrow" style={{color:c?.color}} href={`/c/${a.channel}`}>{c?.name}</Link><h1>{a.title}</h1><p>{a.excerpt}</p><time dateTime={a.published_at}>{new Date(a.published_at).toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})}</time></header>
    <div className="prose">{(a.faqs?.length ? a.body_md.split('## Frequently asked questions')[0] : a.body_md).split('{{YOUTUBE}}').map((part,i) => <div key={i}>{i > 0 && (a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id) ? <Video id={a.youtube_id} title={a.title}/> : <p className="empty">The accompanying video will be available here soon.</p>)}<Markdown remarkPlugins={[remarkGfm]} components={{blockquote: ({children}) => <blockquote className="evidence-box">{children}</blockquote>}}>{part}</Markdown></div>)}</div>
    {Boolean(a.faqs?.length) && <section className="prose faq" aria-labelledby="faqs"><h2 id="faqs">Frequently asked questions</h2>{a.faqs?.map(f => <div key={f.question}><h3>{f.question}</h3><p>{f.answer}</p></div>)}</section>}
    <nav className="article-pagination" aria-label="Previous and next articles">{previous && <Link rel="prev" href={`/a/${previous.slug}`}>← Previous: {previous.title}</Link>}{next && <Link rel="next" href={`/a/${next.slug}`}>Next: {next.title} →</Link>}</nav>
    <section aria-labelledby="related"><h2 id="related">Related articles</h2><Articles items={related}/></section>
    <aside className="card"><h2>Keep exploring {c?.name}</h2><Link href={`/c/${a.channel}`}>All channel stories →</Link><nav className="socials" aria-label="Channel links">{c?.links.map(l => <a href={l.url} key={l.label}>{l.label} ↗</a>)}</nav></aside>
  </article>;
}
