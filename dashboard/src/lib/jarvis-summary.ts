import { createHash, timingSafeEqual } from "node:crypto";

export function authorized(header: string | null, token: string | undefined): boolean {
  if (!token || !header?.startsWith("Bearer ")) return false;
  const digest = (v: string) => createHash("sha256").update(v).digest();
  return timingSafeEqual(digest(header.slice(7)), digest(token));
}

type Row = Record<string, any>;
export function summarize(data: Record<string, Row[]>, window: "1h" | "24h", now = new Date()) {
  const since = now.getTime() - (window === "1h" ? 1 : 24) * 3600000;
  const inWindow = (at: string) => Date.parse(at) >= since && Date.parse(at) <= now.getTime();
  const content = new Map(data.content.map(c => [c.id, c]));
  const recent = data.publications.filter(p => p.status === "live" && inWindow(p.published_at));
  const uploads: Record<string, Record<string, number>> = {};
  for (const p of recent) {
    const channel = content.get(p.content_id)?.channel ?? "unknown";
    uploads[channel] ??= {};
    uploads[channel][p.platform] = (uploads[channel][p.platform] ?? 0) + 1;
  }
  const delta = { views: 0, likes: 0, comments: 0 };
  const totals = new Map<string, number>();
  const latestMetrics: unknown[] = [];
  for (const p of data.publications) {
    const samples = data.metrics.filter(m => m.publication_id === p.id && Date.parse(m.captured_at) <= now.getTime()).sort((a,b) => Date.parse(a.captured_at)-Date.parse(b.captured_at));
    const latest = samples.at(-1);
    if (!latest) continue;
    latestMetrics.push([p.id, latest.views, latest.likes, latest.comments]);
    totals.set(p.content_id, (totals.get(p.content_id) ?? 0) + Number(latest.views ?? 0));
    if (!inWindow(latest.captured_at)) continue;
    const baseline = samples.filter(m => Date.parse(m.captured_at) < since).at(-1);
    // Existing videos with no baseline have unknown growth, not lifetime growth.
    if (!baseline && !inWindow(p.published_at)) continue;
    for (const k of ["views", "likes", "comments"] as const) delta[k] += Math.max(0, Number(latest[k] ?? 0) - Number(baseline?.[k] ?? 0));
  }
  const tomorrow = new Date(now.getTime()+86400000).toISOString().slice(0,10);
  const result = {
    window, uploads, uploadCount: recent.length,
    failures: data.publications.filter(p => p.status === "failed" && inWindow(p.status_changed_at)).length,
    queued: data.publications.filter(p => p.status === "queued").length,
    delta,
    spend: { monthUsd: data.costs.filter(c => c.at?.slice(0,7) === now.toISOString().slice(0,7)).reduce((n,c) => n+Number(c.usd ?? 0),0), budgetUsd: Number(data.settings.find(s => s.key === "monthly_budget_usd")?.value ?? 100) },
    pendingComments: data.comments.length,
    runningJobs: data.runs.length,
    recentUploads: recent.slice().sort((a,b) => String(b.published_at).localeCompare(String(a.published_at))).slice(0,20).map(p => ({ publicationId: p.id, contentId: p.content_id, channel: content.get(p.content_id)?.channel ?? "unknown", platform: p.platform })),
    topVideo: [...totals].sort((a,b) => b[1]-a[1]).slice(0,1).map(([contentId, views]) => ({ contentId, views }))[0] ?? null,
    tomorrowSchedule: data.publications.filter(p => ["live","queued"].includes(p.status) && p.publish_at?.slice(0,10) === tomorrow).map(p => ({ channel: content.get(p.content_id)?.channel ?? "unknown", platform: p.platform, at: p.publish_at })),
  };
  // Stable over idle hours; the moving window itself must not cause notifications.
  const state = { publications: data.publications.map(p => [p.id,p.status,p.status_changed_at,p.publish_at]).sort(), metrics: latestMetrics.sort(), spend: result.spend, pendingComments: data.comments.map(c => c.id).sort(), runningJobs: data.runs.map(r => r.id).sort() };
  return { ...result, lastEventId: createHash("sha256").update(JSON.stringify(state)).digest("hex") };
}
