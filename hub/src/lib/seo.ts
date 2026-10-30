import type { Metadata } from 'next';
export const siteURL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://hub.ammaad.online').replace(/\/+$/, '');
export const absolute = (path: string) => `${siteURL}${path === '/' ? '' : path}`;
export function pageMetadata(title: string, description: string, path: string, image = '/opengraph-image'): Metadata {
  const url = absolute(path);
  return {title, description, alternates: {canonical: url, languages: {en: url}, types: {'application/rss+xml': absolute('/feed.xml')}},
    openGraph: {type: 'website', siteName: 'Plainsight Media', locale: 'en_US', title, description, url, images: [{url: absolute(image), width: 1200, height: 630, alt: title}]},
    twitter: {card: 'summary_large_image', title, description, images: [absolute(image)]}};
}

export function organizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Plainsight Media',
    url: absolute('/'),
    logo: absolute('/icon-512.png'),
  };
}

export function websiteJsonLd() {
  return {'@context': 'https://schema.org', '@type': 'WebSite', name: 'Plainsight Media', alternateName: 'Plainsight', url: `${siteURL}/`};
}
