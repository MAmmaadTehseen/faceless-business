import "server-only";
import { db } from "./supabase";
import { CHANNELS, ChannelFilter, ChannelKey } from "./channels";
import { Comment, Content, DEFAULT_SETTINGS, Publication, Run, Settings, TopicQueueRow } from "./types";

export async function getSettings(): Promise<Settings> {
  const { data, error } = await db().from("settings").select("key,value");
  if (error) throw error;
  const s: Record<string, unknown> = { ...DEFAULT_SETTINGS };
  for (const row of data ?? []) s[row.key] = row.value;
  return s as Settings;
}

export async function getLatestRun(): Promise<Run | null> {
  const { data } = await db()
    .from("runs")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  return (data as Run) ?? null;
}

// Shared by the layout banner. Never throws so a missing DB only degrades the banner.
export async function getBannerState() {
  try {
    const [settings, run] = await Promise.all([getSettings(), getLatestRun()]);
    return { paused: !!settings.pipeline_paused, failedRun: run?.status === "failed" ? run : null };
  } catch {
    return { paused: false, failedRun: null };
  }
}

/* ---------- Overview helpers (home page) ---------- */

const LIVE = ["published", "live"];
const PENDING_REPLY = ["new", "drafted"];

/** Swallow a failing query so one broken table only blanks its tile. */
async function safe<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch { return fallback; }
}

export type PendingComment = Comment & { channel: string | null; videoTitle: string };

/** Comments awaiting a reply, resolved to their channel and video title (optionally filtered). */
export async function getPendingComments(channel: ChannelFilter, limit = 200): Promise<PendingComment[]> {
  const { data, error } = await db().from("comments").select("*").in("reply_status", PENDING_REPLY)
    .order("posted_at", { ascending: false, nullsFirst: false }).limit(channel === "all" ? limit : limit * 3);
  if (error) throw error;
  const comments = (data ?? []) as Comment[];
  const pubIds = [...new Set(comments.map((c) => c.publication_id).filter((x): x is number => x != null))];
  const info = new Map<number, { title: string; channel: string | null }>();
  if (pubIds.length) {
    const { data: pubs } = await db().from("publications").select("id,content_id,content(title,channel)").in("id", pubIds);
    type C = { title: string; channel: string | null };
    for (const p of pubs ?? []) {
      const content = p.content as unknown as C | C[] | null;
      const row = Array.isArray(content) ? content[0] : content;
      info.set(p.id, { title: row?.title ?? p.content_id, channel: row?.channel ?? null });
    }
  }
  const out = comments.map((c) => ({
    ...c,
    channel: c.publication_id != null ? info.get(c.publication_id)?.channel ?? null : null,
    videoTitle: c.publication_id != null ? info.get(c.publication_id)?.title ?? "" : "",
  }));
  return (channel === "all" ? out : out.filter((c) => c.channel === channel)).slice(0, limit);
}

/** Count of publications that went live in the last `days` days. */
export async function getPublishedCount(channel: ChannelFilter, days = 7): Promise<number> {
  const since = new Date(Date.now() - days * 86400_000).toISOString();
  let q = db().from("publications").select("id,content!inner(channel)", { count: "exact", head: true })
    .in("status", LIVE).gte("published_at", since);
  if (channel !== "all") q = q.eq("content.channel", channel);
  const { count, error } = await q;
  if (error) throw error;
  return count ?? 0;
}

export async function getQueue(channel: ChannelFilter, limit = 5): Promise<{ count: number; top: TopicQueueRow[] }> {
  let q = db().from("topic_queue").select("*", { count: "exact" }).eq("status", "queued")
    .order("priority", { ascending: false }).order("created_at", { ascending: true }).limit(limit);
  if (channel !== "all") q = q.eq("channel", channel);
  const { data, count, error } = await q;
  if (error) throw error;
  return { count: count ?? 0, top: (data ?? []) as TopicQueueRow[] };
}

export type CostSummary = { mtd: number; projected: number; budget: number; pct: number; daysElapsed: number; daysInMonth: number };

export async function getCostSummary(channel: ChannelFilter): Promise<CostSummary> {
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const daysElapsed = now.getDate();
  let q = db().from("costs").select("usd").gte("at", monthStart.toISOString()).limit(5000);
  if (channel !== "all") q = q.eq("channel", channel);
  const [settings, { data, error }] = await Promise.all([getSettings().catch(() => null), q]);
  if (error) throw error;
  const mtd = (data ?? []).reduce((a, c) => a + (c.usd ?? 0), 0);
  const projected = daysElapsed > 0 ? (mtd / daysElapsed) * daysInMonth : 0;
  const budget = settings?.monthly_budget_usd ?? 0;
  const pct = budget > 0 ? Math.min(100, (mtd / budget) * 100) : 0;
  return { mtd, projected, budget, pct, daysElapsed, daysInMonth };
}

export type ChannelHealth = {
  key: ChannelKey;
  lastRun: Run | null;
  lastContentAt: string | null;
  queued: number;
  /** ok = last run fine, warn = no run yet or stale content, alert = last run failed */
  level: "ok" | "warn" | "alert";
};

export async function getChannelHealth(): Promise<ChannelHealth[]> {
  const [runsRes, contentRes, queueRes] = await Promise.all([
    db().from("runs").select("*").order("started_at", { ascending: false }).limit(60),
    db().from("content").select("channel,created_at").order("created_at", { ascending: false }).limit(90),
    db().from("topic_queue").select("channel").eq("status", "queued").limit(1000),
  ]);
  const runs = (runsRes.data ?? []) as Run[];
  const content = (contentRes.data ?? []) as { channel: string; created_at: string }[];
  const queued = (queueRes.data ?? []) as { channel: string }[];
  const staleMs = 5 * 86400_000;
  return CHANNELS.map((c) => {
    const lastRun = runs.find((r) => r.channel === c.key) ?? null;
    const lastContentAt = content.find((x) => x.channel === c.key)?.created_at ?? null;
    const n = queued.filter((x) => x.channel === c.key).length;
    const stale = !lastContentAt || Date.now() - new Date(lastContentAt).getTime() > staleMs;
    const level: ChannelHealth["level"] = lastRun?.status === "failed" ? "alert" : !lastRun || stale ? "warn" : "ok";
    return { key: c.key, lastRun, lastContentAt, queued: n, level };
  });
}

export type FailedPublication = Publication & { channel: string | null; title: string };

/** Recent publications that errored, with their content title. */
export async function getFailedPublications(channel: ChannelFilter, limit = 10): Promise<FailedPublication[]> {
  let q = db().from("publications").select("*,content!inner(title,channel)")
    .or("status.eq.failed,error.not.is.null").not("status", "in", "(published,live)")
    .order("id", { ascending: false }).limit(limit);
  if (channel !== "all") q = q.eq("content.channel", channel);
  const { data, error } = await q;
  if (error) throw error;
  type C = { title: string; channel: string | null };
  return (data ?? []).map((p) => {
    const content = p.content as unknown as C | C[] | null;
    const row = Array.isArray(content) ? content[0] : content;
    const { content: _c, ...rest } = p as Publication & { content: unknown };
    void _c;
    return { ...(rest as Publication), channel: row?.channel ?? null, title: row?.title ?? rest.content_id };
  });
}

/** Content rows whose pipeline or QA failed. Killed rows are deliberate (see AGENTS.md) and skipped. */
export async function getFailedContent(channel: ChannelFilter, limit = 10): Promise<Content[]> {
  let q = db().from("content").select("id,channel,kind,parent_id,topic,title,qa_status,status,claude_cost_usd,created_at")
    .or("status.eq.failed,qa_status.eq.failed").neq("status", "killed")
    .order("created_at", { ascending: false }).limit(limit);
  if (channel !== "all") q = q.eq("channel", channel);
  const { data, error } = await q;
  if (error) throw error;
  return (data ?? []) as Content[];
}

/** Everything the home page needs, each query isolated so one failure does not blank the page. */
export async function getOverview(channel: ChannelFilter) {
  const [publishedWeek, queue, pending, costs, health, failedPubs, failedContent, banner] = await Promise.all([
    safe(getPublishedCount(channel), 0),
    safe(getQueue(channel), { count: 0, top: [] as TopicQueueRow[] }),
    safe(getPendingComments(channel, 50), [] as PendingComment[]),
    safe(getCostSummary(channel), { mtd: 0, projected: 0, budget: 0, pct: 0, daysElapsed: 1, daysInMonth: 30 } as CostSummary),
    safe(getChannelHealth(), [] as ChannelHealth[]),
    safe(getFailedPublications(channel), [] as FailedPublication[]),
    safe(getFailedContent(channel), [] as Content[]),
    getBannerState(),
  ]);
  return { publishedWeek, queue, pending, costs, health, failedPubs, failedContent, ...banner };
}
