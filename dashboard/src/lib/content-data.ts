import "server-only";
import { db } from "./supabase";
import { Content, Publication, Metric } from "./types";
import { ChannelFilter } from "./channels";
export type ContentItem = Content & {
  publications: (Publication & { metric: Metric | null })[];
};
export async function getContent(
  channel: ChannelFilter,
  includeMetrics = true,
  days?: string,
): Promise<ContentItem[]> {
  let q = db()
    .from("content")
    .select("*")
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
      .select("*")
      .in(
        "content_id",
        rows.slice(offset, offset + 100).map((c) => c.id),
      );
    if (pe) throw pe;
    publications.push(...((pubs ?? []) as Publication[]));
  }
  const latest = new Map<number, Metric>();
  if (includeMetrics && publications.length) {
    let offset = 0;
    for (;;) {
      const { data: ms, error: me } = await db()
        .from("metrics")
        .select("*")
        .in(
          "publication_id",
          publications.map((p) => p.id),
        )
        .order("captured_at", { ascending: false })
        .order("id", { ascending: false })
        .range(offset, offset + 999);
      if (me) throw me;
      for (const m of (ms ?? []) as Metric[])
        if (!latest.has(m.publication_id)) latest.set(m.publication_id, m);
      if ((ms ?? []).length < 1000 || latest.size === publications.length)
        break;
      offset += 1000;
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
  if (platform !== "hub") return items;
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
