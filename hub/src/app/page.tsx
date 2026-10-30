import Link from 'next/link';
import { channels } from '@/lib/channels';
import { articles } from '@/lib/articles';
import Articles, { ArticleCard } from '@/components/Articles';
import { pageMetadata, organizationJsonLd, websiteJsonLd } from '@/lib/seo';
export const revalidate = 600;
const homeTitle = 'Plainsight Media: Work, Power and Space, Explained';
export const metadata = {...pageMetadata(homeTitle, 'Understand how AI, global power and space science shape your world. Clear explanations, evidence and fresh perspectives from Plainsight Media.', '/'), title: {absolute: homeTitle}};
export default async function Home() {
  const stories = await articles();
  return <><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify([organizationJsonLd(), websiteJsonLd()]).replace(/</g, '\\u003c')}}/>
    <section className="masthead"><p className="eyebrow">THE PLAINSIGHT PERSPECTIVE</p><h1>A clearer view of<br/>what comes next.</h1><p>Independent perspectives on work, global power and the frontier of science.</p></section>
    {stories.length > 0 && <section className="lead-grid" aria-label="Latest stories"><ArticleCard a={stories[0]} lead/><div className="secondary-stories">{stories.slice(1,3).map(a => <ArticleCard key={a.id} a={a}/>)}</div></section>}
    {channels.map(c => <section className="channel-row" key={c.key}><div className="section-heading"><h2><Link href={`/c/${c.key}`}>{c.name}</Link></h2><Link className="more-link" href={`/c/${c.key}`}>More from {c.name} <span aria-hidden="true">→</span></Link></div><Articles items={stories.filter(a => a.channel === c.key).slice(0,3)}/></section>)}</>;
}
