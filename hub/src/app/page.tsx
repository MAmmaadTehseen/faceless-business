import Link from 'next/link';
import { withArticleImages } from '@/lib/article-image';
import { channels } from '@/lib/channels';
import { articles } from '@/lib/articles';
import Articles, { ArticleCard } from '@/components/Articles';
import { pageMetadata, organizationJsonLd, websiteJsonLd } from '@/lib/seo';
export const revalidate = 600;
const homeTitle = 'Plainsight Media: Work, Power and Space, Explained';
export const metadata = {...pageMetadata(homeTitle, 'Understand how AI, global power and space science shape your world. Clear explanations, evidence and fresh perspectives from Plainsight Media.', '/'), title: {absolute: homeTitle}};
export default async function Home() {
  const archive = await articles();
  const candidates = [...new Map([...archive.slice(0,12), ...channels.flatMap(c=>archive.filter(a=>a.channel===c.key).slice(0,3))].map(a=>[a.id,a])).values()];
  const stories = await withArticleImages(candidates);
  const recent = stories.slice(0,12);
  const lead = recent.find(a=>a.resolved_image?.real) || stories[0];
  const secondary = stories.filter(a=>a.id !== lead?.id).slice(0,2);
  return <><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify([organizationJsonLd(), websiteJsonLd()]).replace(/</g, '\\u003c')}}/>
    <section className="masthead"><p className="eyebrow">THE PLAINSIGHT PERSPECTIVE</p><h1><span className="headline-line"><span>A clearer view of</span></span><span className="headline-line"><span>what comes next.</span></span></h1><p>Independent perspectives on work, global power and the frontier of science.</p></section>
    {stories.length > 0 && <section className="lead-grid" aria-label="Latest stories"><ArticleCard a={lead} lead/><div className="secondary-stories">{secondary.map(a => <ArticleCard key={a.id} a={a}/>)}</div></section>}
    {channels.map((c,i) => <section className="channel-row" key={c.key} style={{'--section-accent':c.color} as React.CSSProperties}><div className="section-heading"><h2><span className="section-index" aria-hidden="true">{String(i+1).padStart(2,'0')}</span><Link href={`/c/${c.key}`}>{c.name}</Link></h2><Link className="more-link" href={`/c/${c.key}`}>More from {c.name} <span aria-hidden="true">→</span></Link></div><Articles items={stories.filter(a => a.channel === c.key).slice(0,3)}/></section>)}</>;
}
