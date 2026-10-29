import "server-only";
import { db } from "./supabase";
import { getContent } from "./content-data";
import { ChannelFilter } from "./channels";
import { Metric } from "./types";
export type Totals = {
  views: number;
  likes: number;
  comments: number;
  watch: number | null;
};
export async function getAnalytics(channel: ChannelFilter, days: number) {
  const items = await getContent(channel, false);
  const pubs = items.flatMap((c) =>
    c.publications.map((p) => ({
      ...p,
      channel: c.channel,
      kind: c.kind,
      title: c.title,
    })),
  );
  const ids = pubs.map((p) => p.id);
  const snapshots: Metric[] = [];
  if (ids.length) {
    for (let offset = 0; ; offset += 1000) {
      const { data, error } = await db()
        .from("metrics")
        .select("*")
        .in("publication_id", ids)
        .order("captured_at", { ascending: true })
        .order("id", { ascending: true })
        .range(offset, offset + 999);
      if (error) throw error;
      snapshots.push(...((data ?? []) as Metric[]));
      if ((data ?? []).length < 1000) break;
    }
  }
  const byPub = new Map<number, Metric[]>();
  for (const m of snapshots) {
    const rows = byPub.get(m.publication_id) ?? [];
    rows.push(m);
    byPub.set(m.publication_id, rows);
  }
  const end = Date.now(),
    start = end - days * 86400000,
    previous = start - days * 86400000;
  function at(id: number, time: number) {
    const rows = byPub.get(id) ?? [];
    for (let i = rows.length - 1; i >= 0; i--)
      if (Date.parse(rows[i].captured_at) <= time) return rows[i];
    return undefined;
  }
  function sum(selected: typeof pubs, from: number, to: number): Totals {
    let views = 0,
      likes = 0,
      comments = 0,
      watchTotal = 0,
      weight = 0;
    for (const p of selected) {
      const a = at(p.id, from),
        b = at(p.id, to);
      const v = Math.max(0, (b?.views ?? 0) - (a?.views ?? 0));
      views += v;
      likes += Math.max(0, (b?.likes ?? 0) - (a?.likes ?? 0));
      comments += Math.max(0, (b?.comments ?? 0) - (a?.comments ?? 0));
      if (b?.ctr != null && v > 0) {
        watchTotal += b.ctr * v;
        weight += v;
      }
    }
    return {
      views,
      likes,
      comments,
      watch: weight ? watchTotal / weight : null,
    };
  }
  const daily = Array.from({ length: days }, (_, i) => {
    const from = start + i * 86400000;
    return {
      date: new Date(from).toISOString().slice(0, 10),
      views: sum(pubs, from, from + 86400000).views,
    };
  });
  const platform = [
    {
      name: "YouTube long",
      ps: pubs.filter((p) => p.platform === "youtube" && p.kind === "long"),
    },
    {
      name: "YouTube Shorts",
      ps: pubs.filter((p) => p.platform === "youtube" && p.kind === "short"),
    },
    ...["instagram", "facebook"].map((platform) => ({
      name: platform[0].toUpperCase() + platform.slice(1),
      ps: pubs.filter((p) => p.platform === platform),
    })),
  ].map((g) => ({ name: g.name, ...sum(g.ps, start, end) }));
  return {
    total: sum(pubs, start, end),
    previous: sum(pubs, previous, start),
    platform,
    daily,
    channels: ["futurework", "tradewinds", "escapevelocity"].map((key) => ({
      name: key,
      ...sum(
        pubs.filter((p) => p.channel === key),
        start,
        end,
      ),
    })),
    top: items
      .map((c) => ({
        id: c.id,
        title: c.title,
        publications: c.publications,
        ...sum(
          pubs.filter((p) => p.content_id === c.id),
          start,
          end,
        ),
      }))
      .sort((a, b) => b.views - a.views)
      .slice(0, 10),
  };
}
