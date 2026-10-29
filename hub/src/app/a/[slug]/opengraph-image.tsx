import { notFound } from 'next/navigation';
import { article } from '@/lib/articles';
import { getChannel } from '@/lib/channels';
import { ogImage } from '@/lib/og';
export const alt = 'Plainsight Media article';
export const size = {width:1200,height:630};
export const contentType = 'image/png';
export const revalidate = 600;
export default async function Image({params}: {params: Promise<{slug:string}>}) {
  const a = await article((await params).slug); if (!a) notFound();
  const c = getChannel(a.channel); return ogImage(a.title, c?.name, c?.color);
}
