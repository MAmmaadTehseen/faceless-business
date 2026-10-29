import Link from 'next/link';
import { channels } from '@/lib/channels';
import { articles } from '@/lib/articles';
import Articles from '@/components/Articles';
export const revalidate = 600;
import { pageMetadata } from '@/lib/seo';
export const metadata = pageMetadata('Stories', channels.map(c => c.tagline).join(' '), '/');
export default async function Home() {
  return <><section className="hero"><p className="eyebrow">WORK / POWER / POSSIBILITY</p><h1>The bigger picture.<br/><span>In plain sight.</span></h1><p>Three distinct perspectives on the forces shaping our lives. Explore the ideas behind our videos, one story at a time.</p></section>
    <nav className="channel-index" aria-label="Channel index">{channels.map(c => <Link key={c.key} href={`/c/${c.key}`}>{c.name}</Link>)}</nav><section aria-labelledby="channels"><h2 id="channels">Three channels. Wider horizons.</h2><div className="channel-grid">{channels.map(c => <article key={c.key} className="card channel" style={{borderTopColor:c.color}}><p className="eyebrow" style={{color:c.color}}> {c.key === 'futurework' ? '01 / WORK' : c.key === 'tradewinds' ? '02 / POWER' : '03 / FRONTIERS'}</p><h3><Link href={`/c/${c.key}`}>{c.name}</Link></h3><p>{c.tagline}</p><Link href={`/c/${c.key}`} style={{color:c.color}}>Explore channel →</Link></article>)}</div></section>
    <section><h2>Latest stories</h2><Articles items={await articles()}/></section></>;
}
