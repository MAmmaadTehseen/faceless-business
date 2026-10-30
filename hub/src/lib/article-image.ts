import 'server-only';
import { cache } from 'react';
import { unstable_cache } from 'next/cache';
import type { Article } from './articles';

// Only public media URLs and YouTube hosts may be probed; never fetch arbitrary row URLs.
export function imageCandidates(a: Article) {
  const candidates: string[] = [];
  const media = process.env.SUPABASE_URL;
  if (a.thumbnail_path && media) {
    const base = `${media.replace(/\/$/, '')}/storage/v1/object/public/media/`;
    const url = a.thumbnail_path.startsWith(base) ? a.thumbnail_path :
      !a.thumbnail_path.includes('://') && !a.thumbnail_path.includes('..') ? base + a.thumbnail_path.replace(/^\//, '') : '';
    if (url) candidates.push(url);
  }
  if (a.youtube_id && /^[\w-]{11}$/.test(a.youtube_id)) {
    candidates.push(`https://i.ytimg.com/vi/${a.youtube_id}/maxresdefault.jpg`, `https://i.ytimg.com/vi/${a.youtube_id}/hqdefault.jpg`);
  }
  return [...candidates, `/a/${encodeURIComponent(a.slug)}/opengraph-image`, `/artwork/${['futurework','tradewinds','escapevelocity'].includes(a.channel) ? a.channel : 'futurework'}.svg`];
}
const persistedAvailability = unstable_cache(async (url: string) => {
  try {
    const response = await fetch(url, {method:'HEAD', signal:AbortSignal.timeout(2000), next:{revalidate:600}});
    return response.ok && !!response.headers.get('content-type')?.startsWith('image/');
  } catch { return false; }
}, ['article-image-availability-v1'], {revalidate:600});
// Also coalesce probes within a server worker. Development hard refreshes bypass
// Next's data cache; they must not turn every card render into a network roundtrip.
const probes = new Map<string,{expires:number;value:Promise<boolean>}>();
function available(url:string) {
  const existing=probes.get(url);
  if(existing && existing.expires>Date.now()) return existing.value;
  const value=persistedAvailability(url);
  probes.set(url,{expires:Date.now()+600_000,value});
  if(probes.size>512) probes.delete(probes.keys().next().value!);
  return value;
}
export const articleImage = cache(async (a: Article) => {
  const sources = imageCandidates(a);
  for (let i=0; i<sources.length; i++) {
    if (!sources[i].startsWith('https://')) return {sources:sources.slice(i), real:false};
    if (await available(sources[i])) return {sources:sources.slice(i), real:true};
  }
  return {sources:sources.slice(-1), real:false};
});

// Resolve before returning page markup: async card children would otherwise stream
// into empty grid tracks and move already-painted stories/footer (CLS).
export async function withArticleImages(items: Article[]) {
  return Promise.all(items.map(async a=>({...a,resolved_image:await articleImage(a)})));
}
