import type { MetadataRoute } from 'next';
import { articles } from '@/lib/articles';
import { channels } from '@/lib/channels';
import { absolute } from '@/lib/seo';
export const revalidate = 600;
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  return [...['/', '/about', '/privacy', ...channels.map(c => `/c/${c.key}`)].map(path => ({url: absolute(path)})),
    ...(await articles()).map(a => ({url: absolute(`/a/${a.slug}`), lastModified: a.updated_at || a.published_at}))];
}
