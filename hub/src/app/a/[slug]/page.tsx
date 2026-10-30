import Link from 'next/link';
import Image from 'next/image';
import { ReadingProgress } from '@/components/ReadingTools';
import { notFound } from 'next/navigation';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Articles, {dateLabel, readTime} from '@/components/Articles';
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
  let body = a.faqs?.length ? a.body_md.split(/## Frequently asked questions/i)[0] : a.body_md;
  if (a.quick_answer) body = body.replace(/## Quick Answer[^\n]*\n[\s\S]*?(?=\n## |$)/i, '');
  if (a.takeaways?.length) body = body.replace(/## Key Takeaways[^\n]*\n[\s\S]*?(?=\n## |$)/i, '');
  const headingId = (text:string) => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const headings = [...body.matchAll(/^## (.+)$/gm)].map(m => ({text:m[1], id:headingId(m[1])}));
  return <article className="reading article-page" style={{'--channel-accent':c?.color} as React.CSSProperties} data-hub="" data-slug={a.slug} data-channel={a.channel}><ReadingProgress/><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(structuredData).replace(/</g, '\\u003c')}}/>
    <header className="article-header"><Link className="eyebrow channel-label" style={{'--label-accent':c?.color} as React.CSSProperties} href={`/c/${a.channel}`}>{c?.name}</Link><h1>{a.title}</h1><p className="article-dek">{a.excerpt}</p><div className="story-meta">Plainsight Media · {c?.name} · <time dateTime={a.published_at}>{dateLabel(a.published_at)}</time> · {readTime(a)}</div></header>
    <figure className="article-hero"><Image src={`/a/${a.slug}/opengraph-image`} alt={a.title} width={1200} height={675} sizes="(max-width: 720px) 100vw, 680px" priority/><figcaption>{c?.name} / Plainsight Media</figcaption></figure>
    {headings.length > 0 && <aside className="contents"><nav aria-label="In this story"><p className="eyebrow">IN THIS STORY</p>{a.quick_answer && <a href="#quick-answer">Quick answer</a>}{headings.map(h => <a key={h.id} href={`#${h.id}`}>{h.text}</a>)}{Boolean(a.faqs?.length) && <a href="#faqs">Questions & answers</a>}</nav></aside>}
    <div className="article-body prose">
      {a.quick_answer && <section className="summary-box" aria-labelledby="quick-answer"><h2 id="quick-answer">Quick answer</h2><p>{a.quick_answer}</p></section>}
      {Boolean(a.takeaways?.length) && <section className="takeaways"><h2>Key takeaways</h2><ul>{a.takeaways?.map(t => <li key={t}>{t}</li>)}</ul></section>}
      {body.split('{{YOUTUBE}}').map((part,i) => <div key={i}>{i > 0 && (a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id) ? <Video id={a.youtube_id} title={a.title}/> : <p className="empty">The accompanying video will be available here soon.</p>)}<Markdown remarkPlugins={[remarkGfm]} components={{h2: ({children}) => <h2 id={headingId(String(children))}>{children}</h2>, blockquote: ({children}) => <blockquote className="evidence-box"><span className="eyebrow">THE EVIDENCE</span>{children}</blockquote>, img: ({src,alt}) => typeof src === 'string' ? <span className="prose-image"><Image src={src} alt={alt || ''} width={1200} height={675} sizes="(max-width: 720px) 100vw, 680px"/>{alt && <span className="caption">{alt}</span>}</span> : null}}>{part}</Markdown></div>)}
      {Boolean(a.faqs?.length) && <section className="faq" aria-labelledby="faqs"><h2 id="faqs">Frequently asked questions</h2>{a.faqs?.map(f => <details key={f.question}><summary>{f.question}</summary><p>{f.answer}</p></details>)}</section>}
    </div>
    <aside className="quiet-card"><p className="eyebrow">KEEP EXPLORING</p><h2>More perspectives from {c?.name}</h2><Link href={`/c/${a.channel}`}>Read the channel →</Link></aside>
    <nav className="article-pagination" aria-label="Previous and next articles">{previous && <Link rel="prev" href={`/a/${previous.slug}`}><span className="eyebrow">← PREVIOUS</span>{previous.title}</Link>}{next && <Link rel="next" href={`/a/${next.slug}`}><span className="eyebrow">NEXT →</span>{next.title}</Link>}</nav>
    {related.length > 0 && <section className="related" aria-labelledby="related"><h2 id="related">Related stories</h2><Articles items={related}/></section>}
  </article>;
}
