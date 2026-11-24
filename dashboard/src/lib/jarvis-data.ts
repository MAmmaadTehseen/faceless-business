import "server-only";
import { db } from "./supabase";
import { latestMetrics } from "./content-data";
import type { JarvisQuery, PubRow, QueryRows, SnapRow, Snapshot } from "./jarvis-query";

// Database reads for /api/jarvis/query and /api/jarvis/summary. Every read is filtered in SQL
// (time ranges, in-lists, migration 017's RPCs) so no request pages a whole metrics table.

const PAGE = 1000; // PostgREST's response cap
type Q = any; // eslint-disable-line @typescript-eslint/no-explicit-any -- supabase-js builder generics are not worth spelling out here

/** Every row of a filtered select: the first page carries the count, the rest load in parallel. */
async function readAll<T>(table: string, columns: string, filter: (q: Q) => Q = (q) => q, order = "id"): Promise<T[]> {
  const page = (offset: number, count?: "exact") =>
    filter(db().from(table).select(columns, count ? { count } : undefined)).order(order).range(offset, offset + PAGE - 1);
  const first = await page(0, "exact");
  if (first.error) throw first.error;
  const rows = [...((first.data ?? []) as T[])];
  const total = first.count ?? rows.length;
  const rest = await Promise.all(Array.from({ length: Math.max(0, Math.ceil(total / PAGE) - 1) }, async (_, i) => {
    const { data, error } = await page((i + 1) * PAGE);
    if (error) throw error;
    return (data ?? []) as T[];
  }));
  return rows.concat(...rest);
}

async function count(table: string, filter: (q: Q) => Q): Promise<number> {
  const { count: n, error } = await filter(db().from(table).select("id", { count: "exact", head: true }));
  if (error) throw error;
  return n ?? 0;
}

const chunks = <T>(xs: T[], size: number) => Array.from({ length: Math.ceil(xs.length / size) }, (_, i) => xs.slice(i * size, i * size + size));
const SNAP_COLS = "id,publication_id,captured_at,views,likes,comments";

/**
 * The snapshot in force at each time, per publication (migration 017's metric_snapshots_at).
 * Without migration 017 it falls back to reading the chunk's snapshots up to the last time.
 */
export async function snapshotsAt(ids: number[], times: string[]): Promise<SnapRow[]> {
  const size = Math.max(1, Math.floor(PAGE / Math.max(1, times.length))); // one response per chunk
  const parts = await Promise.all(chunks(ids, Math.min(200, size)).map(async (chunk) => {
    const { data, error } = await db().rpc("metric_snapshots_at", { p_ids: chunk, p_times: times });
    if (!error) return (data ?? []) as SnapRow[];
    if (error.code !== "PGRST202") throw error;
    console.warn("metric_snapshots_at missing (migration 017 not applied); reading snapshots directly");
    const last = times.reduce((a, b) => (Date.parse(a) > Date.parse(b) ? a : b));
    return readAll<SnapRow>("metrics", SNAP_COLS, (q) => q.in("publication_id", chunk).lte("captured_at", last));
  }));
  return parts.flat();
}

const monthStart = (now: Date) => now.toISOString().slice(0, 7) + "-01T00:00:00Z";

async function budgetUsd(): Promise<number> {
  const { data, error } = await db().from("settings").select("key,value").eq("key", "monthly_budget_usd").maybeSingle();
  if (error) throw error;
  return Number(data?.value ?? 100);
}

async function snapshot(now: Date): Promise<Snapshot> {
  const [queued, pendingComments, runningJobs, month, budget] = await Promise.all([
    count("publications", (q) => q.eq("status", "queued")),
    count("comments", (q) => q.in("reply_status", ["new", "drafted"])),
    count("runs", (q) => q.eq("status", "running")),
    readAll<{ usd: number | null }>("costs", "id,usd", (q) => q.gte("at", monthStart(now))),
    budgetUsd(),
  ]);
  return { queued, pendingComments, runningJobs, monthSpendUsd: month.reduce((n, c) => n + Number(c.usd ?? 0), 0), budgetUsd: budget };
}

type Embedded = Omit<PubRow, "channel" | "title"> & { content: { channel: string; title: string | null } | null };
const PUB_COLS = "id,content_id,platform,status,published_at,publish_at,status_changed_at,content!inner(channel,title)";

export async function loadQueryRows(q: JarvisQuery, now = new Date()): Promise<QueryRows> {
  const from = q.from.toISOString(), to = q.to.toISOString();
  const pubs = (filter: (x: Q) => Q) => readAll<Embedded>("publications", PUB_COLS, (x) => {
    let y = filter(x);
    if (q.channel) y = y.eq("content.channel", q.channel);
    if (q.platform) y = y.eq("platform", q.platform);
    return y;
  }).then((rows) => rows.map(({ content, ...p }) => ({ ...p, channel: content?.channel ?? "unknown", title: content?.title ?? null })));
  const [live, failed, scheduled, costs, snap] = await Promise.all([
    pubs((x) => x.eq("status", "live").lt("published_at", to)),
    pubs((x) => x.eq("status", "failed").gte("status_changed_at", from).lte("status_changed_at", to)),
    pubs((x) => x.gte("publish_at", from).lte("publish_at", to).not("status", "in", "(failed,killed)")),
    readAll<{ usd: number | null }>("costs", "id,usd", (x) => {
      const y = x.gte("at", from).lte("at", to);
      return q.channel ? y.eq("channel", q.channel) : y;
    }),
    snapshot(now),
  ]);
  const snapshots = live.length ? await snapshotsAt(live.map((p) => p.id), [from, to]) : [];
  return { live, failed, scheduled, snapshots, costs, snapshot: snap };
}

/**
 * The tables summarize() reads, with metrics cut to what it uses: each publication's newest
 * snapshot, plus the baseline at the window start for those captured inside the window.
 */
export async function loadSummaryRows(window: "1h" | "24h", now = new Date()) {
  const since = new Date(now.getTime() - (window === "1h" ? 1 : 24) * 3600000);
  const [content, publications, costs, budget, comments, runs] = await Promise.all([
    readAll<Record<string, unknown>>("content", "id,channel"),
    readAll<Record<string, unknown> & { id: number }>("publications", "id,content_id,platform,status,published_at,publish_at,status_changed_at"),
    readAll<Record<string, unknown>>("costs", "id,at,usd", (q) => q.gte("at", monthStart(now))),
    budgetUsd(),
    readAll<Record<string, unknown>>("comments", "id", (q) => q.in("reply_status", ["new", "drafted"])),
    readAll<Record<string, unknown>>("runs", "id", (q) => q.eq("status", "running")),
  ]);
  const latest = publications.length ? await latestMetrics(publications.map((p) => p.id)) : [];
  const fresh = latest.filter((m) => Date.parse(m.captured_at) >= since.getTime()).map((m) => m.publication_id);
  // The snapshot in force just before the window: RPC rows at exactly `since` are dropped by summarize's strict check.
  const baseline = fresh.length ? await snapshotsAt(fresh, [new Date(since.getTime() - 1).toISOString()]) : [];
  const seen = new Set(latest.map((m) => m.id));
  return {
    content, publications, costs, comments, runs,
    settings: [{ key: "monthly_budget_usd", value: budget }],
    metrics: [...latest, ...baseline.filter((m) => !seen.has(m.id))] as Record<string, unknown>[],
  };
}
