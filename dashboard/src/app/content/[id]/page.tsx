import { getScope } from "@/lib/server-scope";
import { scopeHref } from "@/lib/scope";
import { VideoTabs } from "@/components/VideoTabs";
import { RebuildButton } from "@/components/RebuildButton";
import { recoveryAction } from "@/lib/recovery";
import { RetryButton } from "@/components/RetryButton";
import { notFound, redirect } from 'next/navigation';
import { contentBack, shortNumber } from '@/lib/content-link';
import { videoContent, videoShorts, videoDetail, publicationStatus, type VideoContent } from '@/lib/video-detail';
import { channelMeta } from '@/lib/channels';
import { fmtDate, fmtCount, fmtUsd } from '@/lib/format';
import type { Publication, Metric } from '@/lib/types';
import { Countdown } from '@/components/Countdown';
import { SeriesReport } from '@/components/SeriesReport';
import { ShortDisclosure } from '@/components/ShortDisclosure';
import { InboxItem } from '@/components/InboxItem';
import { isOwner } from '@/lib/role';
function Status({ value }: {
    value: string;
}) {
    return <span className={`status-chip ${value === 'failed' ? 'badge-alert' : /queued|scheduled/.test(value) ? 'badge-warn' : ''}`}>{value}</span>;
}
function thumbnail(c: VideoContent, pubs: Publication[]) {
    if (/^https?:\/\//.test(c.thumbnail_path ?? ''))
        return c.thumbnail_path!;
    const yt = pubs.find(p => p.platform === 'youtube' && p.platform_id);
    return yt ? `https://i.ytimg.com/vi/${encodeURIComponent(yt.platform_id!)}/hqdefault.jpg` : null;
}
function Preview({ c, pubs }: {
    c: VideoContent;
    pubs: Publication[];
}) {
    const src = thumbnail(c, pubs);
    if (!src && /^https?:\/\//.test(c.media_url ?? ''))
        return <video className={c.kind === 'short' ? 'short-preview' : 'long-preview'} src={c.media_url!} muted playsInline preload="metadata" aria-label="Video preview"/>;
    return src ? <img className={c.kind === 'short' ? 'short-preview' : 'long-preview'} src={src} alt=""/> : <div className={c.kind === 'short' ? 'short-preview preview-empty' : 'long-preview preview-empty'}>Preview unavailable</div>;
}
function uploadError(raw: string | null | undefined) {
    const error = (raw ?? '').toLowerCase();
    if (/media_not_recoverable|not found|missing.*file/.test(error)) return 'The saved video file is unavailable. Rebuild this upload to restore it.';
    if (/quota|uploadlimitexceeded|daily.*limit/.test(error)) return 'The platform’s daily upload limit was reached. Try again when capacity is available.';
    if (/timeout|timed out|network/.test(error)) return 'The connection timed out before the upload finished. Retry to send it again.';
    if (/token|unauthorized|credential/.test(error)) return 'The platform connection needs attention. Review the account connection before retrying.';
    return 'The platform could not finish this upload. Open Details for its response, then retry.';
}
function PlatformRow({ p, m, short = false, owner = false }: {
    p: Publication;
    m?: Metric;
    short?: boolean;
    owner?: boolean;
}) {
    const name = p.platform === 'youtube' ? `YouTube${short ? ' Short' : ''}` : `${p.platform === 'instagram' ? 'Instagram' : p.platform === 'facebook' ? 'Facebook' : p.platform}${short ? ' Reel' : ''}`;
    const at = p.publish_at || p.published_at;
    return <div className="video-platform"><div className="platform-identity"><span>{name}</span><span><Status value={publicationStatus(p)}/></span>{p.url && <a className="btn" href={p.url} target="_blank" rel="noreferrer">Open ↗</a>}</div><div className="platform-measures"><span>{at ? fmtDate(at) : 'Time not set'}</span>{m ? <span title={`${m.views} views · ${m.likes} likes · ${m.comments} comments`}>{fmtCount(m.views)} views · {fmtCount(m.likes)} likes · {fmtCount(m.comments)} comments</span> : <span>No data yet for this upload.</span>}</div>{p.status === "failed" && <div className="upload-error"><p>{uploadError(p.error)}</p>{p.error && <details><summary>Details</summary><p>{p.error}</p></details>}{owner && <RetryButton publications={[p]}/>}</div>}</div>;
}
export default async function VideoPage({ params, searchParams }: {
    params: Promise<{
        id: string;
    }>;
    searchParams: Promise<{
        from?: string;
    }>;
}) {
    const { id } = await params;
    const sp = await searchParams;
    const { from } = sp;
    const scope = await getScope(sp);
    const c = await videoContent(id);
    if (!c)
        notFound();
    const parent = c.parent_id || c.id.match(/^(.*)-short-\d+$/)?.[1];
    if (parent) {
        const siblings = await videoShorts(parent);
        const index = siblings.findIndex(s => s.id === id);
        redirect(scopeHref(`/content/${encodeURIComponent(parent)}${from ? `?from=${encodeURIComponent(from)}` : ''}#short-${shortNumber(c, index + 1)}`, scope));
    }
    const shorts = await videoShorts(id);
    const [data, owner] = await Promise.all([videoDetail(c, shorts), isOwner()]);
    const latest = new Map<number, Metric>();
    for (const m of data.metrics)
        latest.set(m.publication_id, m);
    const pubs = data.pubs.filter(p => p.content_id === id).sort((a,b) => Number(b.platform === scope.platform) - Number(a.platform === scope.platform));
    const yt = pubs.find(p => p.platform === 'youtube');
    const primary = (scope.platform !== "all" ? pubs.find(p => p.platform === scope.platform) : yt) ?? (scope.platform === "all" ? pubs[0] : undefined);
    const history = primary ? data.metrics.filter(m => m.publication_id === primary.id) : [];
    const current = primary ? latest.get(primary.id) : undefined;
    const cutoff = Date.now() - 7 * 86400000;
    const baseline = history.filter(m => Date.parse(m.captured_at) <= cutoff).at(-1);
    const dayMap = new Map<string, Metric>();
    for (const m of history)
        dayMap.set(m.captured_at.slice(0, 10), m);
    const points = [...dayMap.values()];
    const meta = channelMeta(c.channel);
    const at = primary?.publish_at || primary?.published_at;
    const run = data.runs[0];
    const runUrl = [run?.github_url, run?.url].find(url => url && /^https:\/\/github\.com\/[^/]+\/[^/]+\/actions\/runs\/\d+/.test(url));
    const stat = (key: 'views' | 'likes' | 'comments' | 'ctr') => current?.[key] == null ? 'No data yet' : key === 'ctr' ? `${current.ctr!.toFixed(1)}%` : <span title={String(current[key])}>{fmtCount(current[key])}</span>;
    const delta = (key: 'views' | 'likes' | 'comments' | 'ctr') => {
        if (!current || !baseline || current[key] == null || baseline[key] == null || Date.parse(current.captured_at) < Date.now() - 86400000 || cutoff - Date.parse(baseline.captured_at) > 86400000)
            return 'No seven-day comparison yet';
        const n = current[key]! - baseline[key]!;
        return <span title={key === 'ctr' ? undefined : String(n)}>{`${n >= 0 ? '+' : ''}${key === 'ctr' ? n.toFixed(1) + ' pp' : fmtCount(n)} over 7 days`}</span>;
    };
    return <div className="video-detail space-y-8">
    <a className="btn" href={scopeHref(contentBack(from), scope)}>← Back to Content</a>
    <header className="video-header"><Preview c={c} pubs={pubs}/><div><h1>{c.title}</h1><div className="flex flex-wrap items-center gap-3 mt-3"><span className="flex items-center gap-2"><i className="series-dot" style={{ background: meta?.brand.fg ?? 'var(--muted)' }}/>{meta?.name ?? c.channel}</span><Status value={primary ? publicationStatus(primary) : c.status}/></div>{at && <p className="text-muted mt-3">{primary && publicationStatus(primary) === 'scheduled' ? 'Scheduled' : 'Published'} {fmtDate(at)}{Date.parse(at) > Date.now() && <> · <Countdown at={at}/></>}</p>}<div className="flex flex-wrap gap-2 mt-4">{yt?.url && <a className="btn" href={yt.url} target="_blank" rel="noreferrer">YouTube ↗</a>}{data.articles.map(a => <a key={a.slug} className="btn" href={`${(process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.ammaad.online').replace(/\/$/, '')}/a/${encodeURIComponent(a.slug)}`} target="_blank" rel="noreferrer">Hub article ↗</a>)}{runUrl && <a className="btn" href={runUrl} target="_blank" rel="noreferrer">GitHub run ↗</a>}</div></div></header>
    <VideoTabs title={c.title} overview={<>     <section aria-label="Long video performance"><div className="hero"><p className="hero-label">Long video · {primary?.platform ?? scope.platform} views</p><p className={current ? 'hero-value' : 'text-muted'}>{stat('views')}</p><p className="text-xs text-muted mt-2">{delta('views')}</p></div><div className="supporting-stats">{(['likes', 'comments', 'ctr'] as const).filter(key => key !== 'ctr' || primary?.platform === 'youtube').map(key => <div key={key}><p>{key === 'ctr' ? 'Average view percentage' : key === 'likes' ? 'Likes' : 'Comments'}</p><strong>{stat(key)}</strong><p>{delta(key)}</p></div>)}</div>{points.length ? <SeriesReport chartOnly name="Views over time" dates={points.map(m => m.captured_at.slice(0, 10))} columns={[{ key: 'views', label: 'Views' }]} rows={[{ id: c.id, title: `Cumulative ${primary?.platform ?? scope.platform} views`, daily: points.map(m => m.views), values: { views: current?.views ?? null } }]}/> : <p className="text-muted">No data yet for this video’s views over time.</p>}</section>
    {owner && (recoveryAction(c, data.pubs) !== "retry" ? <RebuildButton id={c.id}/> : <RetryButton publications={data.pubs} label="Retry all failed"/>)}
    <section><h2>Platforms</h2>{scope.platform !== "all" && <p className="text-xs text-muted">{scope.platform} is selected; all uploads are shown below.</p>}{pubs.length ? pubs.map(p => <PlatformRow key={p.id} owner={owner} p={p} m={latest.get(p.id)}/>) : <p className="text-muted">No uploads yet for this video.</p>}</section>
 </>} shorts={<>     <section><h2>Shorts</h2><div className="space-y-3">{shorts.map((s, i) => { const uploads = data.pubs.filter(p => p.content_id === s.id); const ms = uploads.flatMap(p => latest.has(p.id) ? [latest.get(p.id)!] : []); return <ShortDisclosure key={s.id} id={`short-${shortNumber(s, i + 1)}`} summary={<><Preview c={s} pubs={uploads}/><span className="short-copy"><span className="text-xs text-muted">Short {shortNumber(s, i + 1)}</span><span className="font-semibold">{s.title}</span><span title={ms.length ? `${ms.reduce((n, m) => n + m.views, 0)} views · ${ms.reduce((n, m) => n + m.likes, 0)} likes · ${ms.reduce((n, m) => n + m.comments, 0)} comments` : undefined} className="text-xs text-muted">{ms.length ? `${fmtCount(ms.reduce((n, m) => n + m.views, 0))} views · ${fmtCount(ms.reduce((n, m) => n + m.likes, 0))} likes · ${fmtCount(ms.reduce((n, m) => n + m.comments, 0))} comments across platforms${ms.length < uploads.length ? ' (partial data)' : ''}` : 'No data yet for this Short.'}</span><span className="short-statuses">{uploads.map(p => <span key={p.id} className="flex items-center gap-2 text-xs text-muted">{p.platform}<Status value={publicationStatus(p)}/></span>)}</span></span><span aria-hidden className="short-chevron">⌄</span></>}>{uploads.length ? uploads.map(p => <PlatformRow key={p.id} owner={owner} p={p} short m={latest.get(p.id)}/>) : <p>No uploads yet for this Short.</p>}</ShortDisclosure>; })}{!shorts.length && <p className="text-muted">No Shorts yet for this video.</p>}</div></section>
 </>} comments={<>     <section><div className="flex flex-wrap items-center justify-between gap-3"><h2>Comments</h2><a className="btn" href={scopeHref(`/inbox?video=${encodeURIComponent(id)}&tab=all`, scope)}>View in Inbox →</a></div>{data.comments.length ? data.comments.map(comment => { const pub = data.pubs.find(p => p.id === comment.publication_id); return <InboxItem key={comment.id} comment={comment} owner={owner} videoTitle={[c, ...shorts].find(s => s.id === pub?.content_id)?.title ?? c.title} url={pub?.url ?? undefined} contentId={pub?.content_id}/>; }) : <p className="text-muted">No comments yet for this video and its Shorts.</p>}</section>
 </>} details={<>     <details className="video-details"><summary>Details</summary><dl><dt>Content id</dt><dd>{c.id}</dd><dt>Topic</dt><dd>{c.topic}</dd><dt>Video, Shorts and article cost</dt><dd>{data.costs.length ? fmtUsd(data.costs.reduce((n, r) => n + (r.usd ?? 0), 0)) : 'No cost records yet.'}</dd></dl>{[c, ...shorts].filter(s => s.qa_notes).map(s => <div key={s.id}><h3>QA · {s.title}</h3><p className="whitespace-pre-wrap">{s.qa_notes}</p></div>)}{data.pubs.filter(p => p.error && p.status === 'failed').map(p => <div key={p.id}><h3>{p.platform} · {p.content_id}</h3><p className="whitespace-pre-wrap text-alert-fg">{p.error}</p></div>)}{data.runs.map(r => <div key={r.id}><h3>{r.workflow ?? 'Production'} · {r.status}</h3><p className="text-muted">Started {fmtDate(r.started_at)}{r.finished_at && ` · Finished ${fmtDate(r.finished_at)}`}</p>{r.stages?.length ? <ol>{r.stages.map((s, i) => <li key={i}>{s.stage} · {fmtDate(s.at)}</li>)}</ol> : <p className="text-muted">No stage timeline was recorded for this run.</p>}</div>)}</details> </>}/>

  </div>;
}
