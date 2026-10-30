import 'server-only';
import { db } from './supabase';
import type { Content, Publication, Metric, Comment, Cost, Run } from './types';
export type VideoContent = Content & {
    qa_notes?: string | null;
    media_url?: string | null;
};
export type VideoRun = Run & {
    url?: string;
    github_url?: string;
    content_id?: string;
    stages?: {
        stage: string;
        at: string;
    }[];
};
async function rows<T>(table: string, field: string, ids: (string | number)[], order?: string) {
    if (!ids.length)
        return [] as T[];
    const result: T[] = [];
    for (let offset = 0;; offset += 500) {
        let q = db().from(table).select('*').in(field, ids).range(offset, offset + 499);
        if (order)
            q = q.order(order, { ascending: true }).order('id', { ascending: true });
        const { data, error } = await q;
        if (error)
            throw error;
        result.push(...(data ?? []) as T[]);
        if ((data ?? []).length < 500)
            break;
    }
    return result;
}
export async function videoContent(id: string) {
    const { data, error } = await db().from('content').select('*').eq('id', id).maybeSingle();
    if (error)
        throw error;
    return data as VideoContent | null;
}
export async function videoShorts(id: string) {
    const { data, error } = await db().from('content').select('*').eq('parent_id', id).order('id');
    if (error)
        throw error;
    // Older retained Shorts may only carry the conventional id suffix.
    const { data: legacy, error: le } = await db().from('content').select('*').like('id', `${id.replace(/[\\%_]/g, '\\$&')}-short-%`).is('parent_id', null);
    if (le)
        throw le;
    return [...new Map([...(data ?? []), ...(legacy ?? [])].map(c => [c.id, c])).values()].sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true })) as VideoContent[];
}
export async function videoDetail(long: VideoContent, shorts: VideoContent[]) {
    const ids = [long.id, ...shorts.map(s => s.id)];
    const pubs = await rows<Publication>('publications', 'content_id', ids);
    const [metrics, costs, articles, commentResult, runResult] = await Promise.all([
        rows<Metric>('metrics', 'publication_id', pubs.map(p => p.id), 'captured_at'),
        rows<Cost>('costs', 'content_id', ids),
        rows<{
            slug: string;
            content_id: string;
        }>('articles', 'content_id', [long.id]),
        pubs.length ? db().from('comments').select('*').in('publication_id', pubs.map(p => p.id)).order('posted_at', { ascending: false, nullsFirst: false }).order('id', { ascending: false }).limit(10) : Promise.resolve({ data: [], error: null }),
        db().from('runs').select('*').eq('channel', long.channel).like('log', `%${long.id.replace(/[\\%_]/g, '\\$&')}%`).order('started_at', { ascending: false }).limit(100),
    ]);
    if (commentResult.error)
        throw commentResult.error;
    if (runResult.error)
        throw runResult.error;
    // A channel/time match alone cannot identify the run for a video.
    const runs = ((runResult.data ?? []) as VideoRun[]).filter(r => {
        try {
            return r.content_id === long.id || JSON.stringify(JSON.parse(r.log ?? '{}')).includes(`"${long.id}"`);
        }
        catch {
            return false;
        }
    });
    const enrichedRuns = runs.map(run => {
        try {
            const log = JSON.parse(run.log ?? '{}');
            const result = log.results?.find((r: {
                content_id?: string;
            }) => r.content_id === long.id);
            const stages = run.stages ?? result?.stages ?? log.stages;
            const timeline = Array.isArray(stages) ? stages.filter((s: {
                stage?: unknown;
                at?: unknown;
            }) => typeof s?.stage === 'string' && typeof s?.at === 'string') : undefined;
            return { ...run, url: run.url ?? result?.url ?? log.url, github_url: run.github_url ?? result?.github_url ?? log.github_url, stages: timeline } as VideoRun;
        }
        catch {
            return run;
        }
    });
    return { pubs, metrics, costs, articles, comments: (commentResult.data ?? []) as Comment[], runs: enrichedRuns };
}
export function publicationStatus(p: Publication) {
    if (['failed', 'queued'].includes(p.status))
        return p.status;
    if (p.status === 'scheduled' || p.privacy === 'scheduled' || (p.publish_at && Date.parse(p.publish_at) > Date.now()))
        return 'scheduled';
    if (p.privacy === 'private')
        return 'private';
    return ['published', 'live'].includes(p.status) ? 'live' : p.status;
}
