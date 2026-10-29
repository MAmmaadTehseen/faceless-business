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
): Promise<ContentItem[]> {
  let q = db()
    .from("content")
    .select(
      "id,channel,kind,parent_id,topic,title,thumbnail_path,qa_status,status,claude_cost_usd,created_at",
    )
    .order("created_at", { ascending: false });
  if (channel !== "all") q = q.eq("channel", channel);
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
