import "server-only";
import { filterPublications } from "./scope";
import { db } from "./supabase";
import { Content, Publication, Metric } from "./types";
import { ChannelFilter } from "./channels";
import { cached } from "./cache";

const CONTENT_COLS = "id,channel,kind,parent_id,thumbnail_path,tags,topic,title,qa_status,status,claude_cost_usd,created_at";
const PUB_COLS = "id,content_id,platform,platform_id,url,privacy,status,publish_at,published_at,error";
const METRIC_COLS = "id,publication_id,captured_at,views,likes,comments,shares,ctr,avg_view_duration_sec,impressions";
export type ContentItem = Content & {
  publications: (Publication & { metric: Metric | null })[];
};
export const getContent = cached("content", loadContent);
async function loadContent(
  channel: ChannelFilter,
  includeMetrics = true,
  days?: string,
): Promise<ContentItem[]> {
  let q = db()
    .from("content")
    .select(CONTENT_COLS)
    .order("created_at", { ascending: false });
  if (channel !== "all") q = q.eq("channel", channel);
  if ([1, 7, 28, 30, 90].includes(Number(days)))
    q = q.gte(
      "created_at",
      new Date(Date.now() - Number(days) * 86400000).toISOString(),
    );
  const rows: Content[] = [];
  for (let offset = 0; ; offset += 500) {
    const { data, error } = await q.range(offset, offset + 499);
    if (error) throw error;
    rows.push(...((data ?? []) as Content[]));
    if ((data ?? []).length < 500) break;
  }
  if (!rows.length) return [];
  const publications: Publication[] = [];
  for (let offset = 0; offset < rows.length; offset += 100) {
    const { data: pubs, error: pe } = await db()
      .from("publications")
      .select(PUB_COLS)
      .in(
        "content_id",
        rows.slice(offset, offset + 100).map((c) => c.id),
      );
    if (pe) throw pe;
    publications.push(...((pubs ?? []) as Publication[]));
  }
  const latest = new Map<number, Metric>();
  if (includeMetrics && publications.length) {
    // Sync writes every live publication every 6 h, so the last 3 days cover almost all of them.
    const since = new Date(Date.now() - 3 * 86400000).toISOString();
    for (const window of [since, null]) {
      const ids = publications.map((p) => p.id).filter((id) => !latest.has(id));
      for (let i = 0; i < ids.length; i += 200) {
        for (let offset = 0; ; offset += 1000) {
          let q = db().from("metrics").select(METRIC_COLS).in("publication_id", ids.slice(i, i + 200));
          if (window) q = q.gte("captured_at", window);
          const { data: ms, error: me } = await q.order("captured_at", { ascending: false }).order("id", { ascending: false }).range(offset, offset + 999);
          if (me) throw me;
          for (const m of (ms ?? []) as Metric[])
            if (!latest.has(m.publication_id)) latest.set(m.publication_id, m);
          if ((ms ?? []).length < 1000) break;
        }
      }
    }
  }
  return rows.map((c) => ({
    ...c,
    publications: publications
      .filter((p) => p.content_id === c.id)
      .map((p) => ({ ...p, metric: latest.get(p.id) ?? null })),
  }));
}

/** Hub articles are publications in the articles table, rather than social uploads. */
export async function getPlatformContent(channel: ChannelFilter, days?: string, platform?: string): Promise<ContentItem[]> {
  const items = await getContent(channel, true, days);
  if (platform !== "hub") return items.map(c => ({...c, publications: filterPublications(c.publications, platform ?? "")})).filter(c => !platform || platform === "all" || c.publications.length > 0);
  let query = db().from("articles").select("id,content_id,slug,published_at").not("published_at", "is", null);
  if (channel !== "all") query = query.eq("channel", channel);
  const { data, error } = await query;
  if (error) throw error;
  const { getHubAnalytics } = await import("./hub-analytics");
  const analytics = await getHubAnalytics(channel, [1,7,28,30,90].includes(Number(days)) ? Number(days) : 28, days === "all");
  const base = (process.env.NEXT_PUBLIC_HUB_URL ?? "https://hub.ammaad.online").replace(/\/$/, "");
  return items.flatMap(c => {
    const articles = (data ?? []).filter(a => a.content_id === c.id);
    if (!articles.length) return [];
    return [{ ...c, publications: articles.map((a, i) => {
      const stat = analytics?.articles.find(r => r.slug === a.slug);
      return { id: -(i + 1), content_id: c.id, platform: "hub", platform_id: a.id, url: `${base}/a/${encodeURIComponent(a.slug)}`, privacy: "public", status: "published", published_at: a.published_at, error: null, metric: stat ? { id: 0, publication_id: -(i + 1), captured_at: new Date().toISOString(), views: stat.views, likes: 0, comments: 0, shares: 0, ctr: null, avg_view_duration_sec: null, impressions: null } : null };
    }) }];
  });
}
