import type { Content } from './types';
export function shortNumber(c: Pick<Content, 'id'>, fallback = 1) {
    return Number(c.id.match(/-short-(\d+)$/)?.[1] ?? fallback);
}
export function contentHref(c: Pick<Content, 'id' | 'parent_id'>, query = '') {
    const suffix = c.id.match(/^(.*)-short-(\d+)$/);
    if (c.parent_id && !suffix)
        return `/content/${encodeURIComponent(c.id)}${query ? `?from=${encodeURIComponent(query)}` : ""}`;
    const parent = c.parent_id || suffix?.[1];
    return `/content/${encodeURIComponent(parent || c.id)}${query ? `?from=${encodeURIComponent(query)}` : ''}${parent ? `#short-${shortNumber(c)}` : ''}`;
}
export function contentBack(from?: string) {
    const query = new URLSearchParams(from ?? '');
    return `/content${query.size ? `?${query}` : ''}`;
}
