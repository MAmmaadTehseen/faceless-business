import { notFound } from 'next/navigation';
import { channels, getChannel } from '@/lib/channels';
import { articles } from '@/lib/articles';
import Articles from '@/components/Articles';
export const revalidate = 600;
export function generateStaticParams() { return channels.map(c => ({channel:c.key})); }
export async function generateMetadata({params}: {params: Promise<{channel:string}>}) {
  const c = getChannel((await params).channel); return {title:c?.name, description:c?.tagline};
}
export default async function Channel({params}: {params: Promise<{channel:string}>}) {
  const c = getChannel((await params).channel); if (!c) notFound();
  return <><section className="hero"><p className="eyebrow" style={{color:c.color}}>A PLAINSIGHT MEDIA CHANNEL</p><h1 style={{color:c.color}}>{c.name}</h1><p>{c.tagline}</p><nav className="socials" aria-label="Channel social accounts">{c.links.map(l => <a href={l.url} key={l.label}>{l.label} ↗</a>)}</nav></section><section><h2>Stories from {c.name}</h2><Articles items={await articles(c.key)}/></section></>;
}
