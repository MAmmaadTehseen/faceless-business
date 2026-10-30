import "server-only";
import { db } from "./supabase";
import { getContent } from "./content-data";
import { ChannelFilter } from "./channels";
import { category } from "./categories";
import { formatKind } from "./content-filters";
import { Metric } from "./types";
export type Totals = {
  views: number;
  likes: number;
  comments: number;
  watch: number | null;
};
export async function getAnalytics(
  channel: ChannelFilter,
  days: number,
  allTime = false,
  platform = "",
) {
  const items = (await getContent(channel, false)).map(c => ({ ...c, publications: c.publications.filter(p => !platform || p.platform === platform) })).filter(c => !platform || c.publications.length > 0);
  const pubs = items.flatMap((c) =>
    c.publications.map((p) => ({
      ...p,
      channel: c.channel,
      kind: c.kind,
      format: formatKind(c),
      category: category(c),
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
  if (allTime)
    days = Math.max(
      1,
      Math.ceil(
        (Date.now() -
          Math.min(
            Date.now(),
            ...snapshots.map((m) => Date.parse(m.captured_at)),
          )) /
          86400000,
      ) + 1,
    );
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
  const groups = (
    names: string[],
    field: "channel" | "format" | "category" | "platform",
  ) =>
    names.map((name) => {
      const selected = pubs.filter((p) => p[field] === name);
      const count = items.filter((c) =>
        field === "platform"
          ? c.publications.some((p) => p.platform === name)
          : field === "format"
            ? formatKind(c) === name
            : field === "category"
              ? category(c) === name
              : c.channel === name,
      ).length;
      return {
        name,
        count,
        ...sum(selected, start, end),
        previous: sum(selected, previous, start),
        daily: Array.from(
          { length: days },
          (_, i) =>
            sum(selected, start + i * 86400000, start + (i + 1) * 86400000)
              .views,
        ),
      };
    });
  const videos = items.map((c) => ({
    ...c,
    ...sum(
      pubs.filter((p) => p.content_id === c.id),
      start,
      end,
    ),
    daily: Array.from(
      { length: days },
      (_, i) =>
        sum(
          pubs.filter((p) => p.content_id === c.id),
          start + i * 86400000,
          start + (i + 1) * 86400000,
        ).views,
    ),
    previous: sum(
      pubs.filter((p) => p.content_id === c.id),
      previous,
      start,
    ),
  }));
  const daily = Array.from({ length: days }, (_, i) => {
    const from = start + i * 86400000;
    return {
      date: new Date(from).toISOString().slice(0, 10),
      views: sum(pubs, from, from + 86400000).views,
    };
  });
  return {
    periodDays: days,
    start,
    end,
    total: sum(pubs, start, end),
    previous: sum(pubs, previous, start),
    daily,
    channels: groups(["futurework", "tradewinds", "escapevelocity"], "channel"),
    formats: groups(["long", "short", "daily"], "format"),
    categories: groups([...new Set(items.map(category))].sort(), "category"),
    platforms: groups(platform ? [platform] : ["youtube", "instagram", "facebook"], "platform"),
    videos,
  };
}
