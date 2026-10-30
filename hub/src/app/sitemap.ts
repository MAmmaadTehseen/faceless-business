import type { MetadataRoute } from 'next';
import { articles } from '@/lib/articles';
import { channels } from '@/lib/channels';
import { absolute } from '@/lib/seo';
export const revalidate = 600;
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const all = await articles();
  const latest = all.map(a => a.updated_at || a.published_at).sort().at(-1) || '2026-10-30T00:00:00Z';
  return [...['/', '/about', '/privacy', ...channels.map(c => `/c/${c.key}`)].map(path => ({url: absolute(path), lastModified: latest})),
    ...all.map(a => ({url: absolute(`/a/${a.slug}`), lastModified: a.updated_at || a.published_at, images: [absolute(`/a/${a.slug}/opengraph-image`)]}))];
}
