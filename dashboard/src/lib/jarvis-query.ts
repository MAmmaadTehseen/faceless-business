// Pure parts of GET /api/jarvis/query: parameter validation and aggregation over fixed rows.
// The database reads live in jarvis-data.ts so this file stays testable without I/O.

export const PLATFORMS = ["youtube", "instagram", "facebook", "tiktok"] as const;
export const GROUP_BY = ["channel", "platform", "content", "none"] as const;
export type GroupBy = (typeof GROUP_BY)[number];

export type JarvisQuery = {
  from: Date;
  to: Date;
  by: GroupBy;
  channel: string | null;
  platform: string | null;
  top: number;
};

const HOUR = 3600000;
const MAX_SPAN = 90 * 24 * HOUR;
const KNOWN = new Set(["hours", "from", "to", "by", "channel", "platform", "top"]);
// Full ISO 8601 date-time with an explicit zone, so "2026-11-24" or "yesterday" cannot be misread.
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})$/;
const DECIMAL = /^\d+(\.\d+)?$/;

export function parseQuery(params: URLSearchParams, channels: readonly string[], now = new Date()): { query: JarvisQuery } | { error: string } {
  for (const key of new Set(params.keys())) {
    if (!KNOWN.has(key)) return { error: `unknown parameter: ${key}` };
    if (params.getAll(key).length > 1) return { error: `repeated parameter: ${key}` };
  }
  const get = (k: string) => params.get(k);
  let from: Date, to: Date;
  if (get("hours") !== null) {
    if (get("from") !== null || get("to") !== null) return { error: "use either hours or from/to" };
    const raw = get("hours")!;
    const hours = DECIMAL.test(raw) ? Number(raw) : NaN;
    if (!(hours >= 0.25 && hours <= 2160)) return { error: "hours must be a number from 0.25 to 2160" };
    to = now;
    from = new Date(now.getTime() - hours * HOUR);
  } else if (get("from") !== null) {
    const time = (v: string) => (ISO.test(v) && !Number.isNaN(Date.parse(v)) ? new Date(Date.parse(v)) : null);
    const f = time(get("from")!);
    if (!f) return { error: "from must be an ISO timestamp with a time zone" };
    const t = get("to") === null ? now : time(get("to")!);
    if (!t) return { error: "to must be an ISO timestamp with a time zone" };
    if (f.getTime() >= t.getTime()) return { error: "from must be before to" };
    if (t.getTime() - f.getTime() > MAX_SPAN) return { error: "window may span at most 90 days" };
    from = f;
    to = t;
  } else if (get("to") !== null) {
    return { error: "to needs from" };
  } else {
    return { error: "window required: hours, or from (and optional to)" };
  }
  const by = get("by") ?? "channel";
  if (!(GROUP_BY as readonly string[]).includes(by)) return { error: "by must be channel, platform, content or none" };
  const channel = get("channel");
  if (channel !== null && !channels.includes(channel)) return { error: "unknown channel" };
  const platform = get("platform");
  if (platform !== null && !(PLATFORMS as readonly string[]).includes(platform)) return { error: "platform must be youtube, instagram, facebook or tiktok" };
  const rawTop = get("top") ?? "5";
  const top = /^\d{1,2}$/.test(rawTop) ? Number(rawTop) : NaN;
  if (!(top >= 1 && top <= 20)) return { error: "top must be an integer from 1 to 20" };
  return { query: { from, to, by: by as GroupBy, channel, platform, top } };
}

export type PubRow = {
  id: number;
  content_id: string;
  platform: string;
  status: string;
  published_at: string | null;
  publish_at: string | null;
  status_changed_at: string | null;
  channel: string;
  title: string | null;
};
export type SnapRow = { id: number; publication_id: number; captured_at: string; views: number | null; likes: number | null; comments: number | null };
export type Snapshot = { queued: number; pendingComments: number; runningJobs: number; monthSpendUsd: number; budgetUsd: number };
export type QueryRows = {
  /** live publications published before `to` (superset of the window's uploads). */
  live: PubRow[];
  failed: PubRow[];
  /** publications with publish_at in the window that are not failed or killed. */
  scheduled: PubRow[];
  /** metric_snapshots_at(live ids, [from, to]). */
  snapshots: SnapRow[];
  costs: { usd: number | null }[];
  snapshot: Snapshot;
};

const KEYS = ["views", "likes", "comments"] as const;
type Gain = Record<(typeof KEYS)[number], number>;
const ms = (v: string | null | undefined) => (v ? Date.parse(v) : NaN);
const money = (n: number) => Math.round(n * 10000) / 10000;

/** Last snapshot captured at or before t, per publication. */
export function snapshotAt(rows: SnapRow[], t: number): Map<number, SnapRow> {
  const at = new Map<number, SnapRow>();
  for (const m of rows) {
    const c = ms(m.captured_at);
    if (!(c <= t)) continue;
    const prev = at.get(m.publication_id);
    if (!prev || c > ms(prev.captured_at) || (c === ms(prev.captured_at) && m.id > prev.id)) at.set(m.publication_id, m);
  }
  return at;
}

export function aggregate(q: JarvisQuery, rows: QueryRows, now = new Date()) {
  const from = q.from.getTime(), to = q.to.getTime();
  const inWindow = (v: string | null) => ms(v) >= from && ms(v) <= to;
  // The loader already filters in SQL; repeating it here keeps the result right for any input.
  const keep = (p: PubRow) => (!q.channel || p.channel === q.channel) && (!q.platform || p.platform === q.platform);
  const key = (p: PubRow) => (q.by === "channel" ? p.channel : q.by === "platform" ? p.platform : p.content_id);

  const live = rows.live.filter((p) => keep(p) && p.status === "live" && ms(p.published_at) < to);
  const uploaded = live.filter((p) => inWindow(p.published_at));
  const failed = rows.failed.filter((p) => keep(p) && p.status === "failed" && inWindow(p.status_changed_at));
  // YouTube uploads are "live" but private until publish_at, so a future slot still counts as scheduled.
  const scheduled = rows.scheduled.filter((p) => keep(p) && inWindow(p.publish_at) && !["failed", "killed"].includes(p.status)
    && (p.status !== "live" || ms(p.publish_at) > now.getTime()));

  const uploadGroups = new Map<string, { key: string; live: number; failed: number }>();
  const bump = (p: PubRow, field: "live" | "failed") => {
    const g = uploadGroups.get(key(p)) ?? { key: key(p), live: 0, failed: 0 };
    g[field]++;
    uploadGroups.set(g.key, g);
  };
  if (q.by !== "none") {
    uploaded.forEach((p) => bump(p, "live"));
    failed.forEach((p) => bump(p, "failed"));
  }

  const atFrom = snapshotAt(rows.snapshots, from), atTo = snapshotAt(rows.snapshots, to);
  const total: Gain = { views: 0, likes: 0, comments: 0 };
  const audienceGroups = new Map<string, { key: string } & Gain>();
  const perPub: { p: PubRow; views: number }[] = [];
  for (const p of live) {
    const end = atTo.get(p.id);
    if (!end) continue;
    const start = atFrom.get(p.id);
    const gain = {} as Gain;
    for (const k of KEYS) gain[k] = Math.max(0, Number(end[k] ?? 0) - Number(start?.[k] ?? 0));
    if (!gain.views && !gain.likes && !gain.comments) continue;
    for (const k of KEYS) total[k] += gain[k];
    perPub.push({ p, views: gain.views });
    if (q.by === "none") continue;
    const g = audienceGroups.get(key(p)) ?? { key: key(p), views: 0, likes: 0, comments: 0 };
    for (const k of KEYS) g[k] += gain[k];
    audienceGroups.set(g.key, g);
  }

  return {
    from: q.from.toISOString(),
    to: q.to.toISOString(),
    by: q.by,
    uploads: {
      live: uploaded.length,
      failed: failed.length,
      scheduled: scheduled.length,
      groups: [...uploadGroups.values()].sort((a, b) => b.live - a.live || b.failed - a.failed || a.key.localeCompare(b.key)),
    },
    audience: {
      ...total,
      groups: [...audienceGroups.values()].sort((a, b) => b.views - a.views || b.likes - a.likes || a.key.localeCompare(b.key)),
    },
    top: perPub
      .filter((x) => x.views > 0)
      .sort((a, b) => b.views - a.views || a.p.id - b.p.id)
      .slice(0, q.top)
      .map(({ p, views }) => ({ contentId: p.content_id, channel: p.channel, title: p.title ?? null, platform: p.platform, views })),
    spend: { usd: money(rows.costs.reduce((n, c) => n + Number(c.usd ?? 0), 0)) },
    snapshot: { ...rows.snapshot, monthSpendUsd: money(rows.snapshot.monthSpendUsd) },
  };
}
