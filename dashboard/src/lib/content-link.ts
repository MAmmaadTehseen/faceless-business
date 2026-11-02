import { parseScope, scopeHref } from "./scope";
import type { Content } from './types';
export function shortNumber(c: Pick<Content, 'id'>, fallback = 1) {
    return Number(c.id.match(/-short-(\d+)$/)?.[1] ?? fallback);
}
export function contentHref(c: Pick<Content, 'id' | 'parent_id'>, query = '') {
    const scope = parseScope(Object.fromEntries(new URLSearchParams(query)));
    const suffix = c.id.match(/^(.*)-short-(\d+)$/);
    if (c.parent_id && !suffix)
        return scopeHref(`/content/${encodeURIComponent(c.id)}${query ? `?from=${encodeURIComponent(query)}` : ""}`, scope);
    const parent = c.parent_id || suffix?.[1];
    return scopeHref(`/content/${encodeURIComponent(parent || c.id)}${query ? `?from=${encodeURIComponent(query)}` : ''}${parent ? `#short-${shortNumber(c)}` : ''}`, scope);
}
export function contentBack(from?: string) {
    const query = new URLSearchParams(from ?? '');
    return `/content${query.size ? `?${query}` : ''}`;
}
