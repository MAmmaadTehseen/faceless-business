import "server-only";
import { filterPublications } from "./scope";
import { db } from "./supabase";
import { getContent } from "./content-data";
import { ChannelFilter } from "./channels";
import { category } from "./categories";
import { formatKind } from "./content-filters";
import { Metric } from "./types";
import { cached } from "./cache";
export type Totals = {
  views: number;
  likes: number;
  comments: number;
  watch: number | null;
};
export const getAnalytics = cached("analytics", loadAnalytics);
async function loadAnalytics(
  channel: ChannelFilter,
  days: number,
  allTime = false,
  platform = "",
  endAt?: number,
) {
  platform = platform === "all" ? "" : platform;
  const items = (await getContent(channel, false)).map(c => ({ ...c, publications: filterPublications(c.publications, platform) })).filter(c => !platform || c.publications.length > 0);
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
  // Only the two compared periods matter (plus a day so the snapshot at the window start exists).
  const since = allTime ? null : new Date((endAt ?? Date.now()) - (2 * days + 1) * 86400000).toISOString();
  // One paged reader per chunk of ids, all chunks in parallel (PostgREST caps each response at 1,000 rows).
  const chunks = Array.from({ length: Math.ceil(ids.length / 200) }, (_, i) => ids.slice(i * 200, i * 200 + 200));
  const parts = await Promise.all(chunks.map(async (chunk) => {
    const rows: Metric[] = [];
    for (let offset = 0; ; offset += 1000) {
      let q = db()
        .from("metrics")
        .select("id,publication_id,captured_at,views,likes,comments,ctr")
        .in("publication_id", chunk);
      if (since) q = q.gte("captured_at", since);
      const { data, error } = await q
        .order("captured_at", { ascending: true })
        .order("id", { ascending: true })
        .range(offset, offset + 999);
      if (error) throw error;
      rows.push(...((data ?? []) as Metric[]));
      if ((data ?? []).length < 1000) break;
    }
    return rows;
  }));
  for (const rows of parts) snapshots.push(...rows);
  snapshots.sort((a, b) => a.captured_at.localeCompare(b.captured_at) || a.id - b.id);
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
  const end = endAt ?? Date.now(),
    start = end - days * 86400000,
    previous = start - days * 86400000;
  // Snapshot times parsed once; at() binary-searches the last snapshot at or before `time`.
  const times = new Map<number, number[]>();
  for (const [id, rows] of byPub) times.set(id, rows.map((m) => Date.parse(m.captured_at)));
  function at(id: number, time: number) {
    const rows = byPub.get(id), ts = times.get(id);
    if (!rows || !ts) return undefined;
    let lo = 0, hi = ts.length - 1, found = -1;
    while (lo <= hi) { const mid = (lo + hi) >> 1; if (ts[mid] <= time) { found = mid; lo = mid + 1; } else hi = mid - 1; }
    return found < 0 ? undefined : rows[found];
  }
  const pubsByContent = new Map<string, typeof pubs>();
  for (const p of pubs) pubsByContent.set(p.content_id, [...(pubsByContent.get(p.content_id) ?? []), p]);
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
      if (p.platform === "youtube" && b?.ctr != null && v > 0) {
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
          { length: Math.max(1, Math.ceil(days)) },
          (_, i) =>
            sum(selected, start + i * 86400000, start + (i + 1) * 86400000)
              .views,
        ),
      };
    });
  const videos = items.map((c) => { const own = pubsByContent.get(c.id) ?? []; return {
    ...c,
    ...sum(
      own,
      start,
      end,
    ),
    daily: Array.from(
      { length: Math.max(1, Math.ceil(days)) },
      (_, i) =>
        sum(
          own,
          start + i * 86400000,
          start + (i + 1) * 86400000,
        ).views,
    ),
    previous: sum(
      own,
      previous,
      start,
    ),
  }; });
  const daily = Array.from({ length: Math.max(1, Math.ceil(days)) }, (_, i) => {
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
    channels: groups(["futurework", "tradewinds", "escapevelocity", "tentongues", "filmreview"], "channel"),
    formats: groups(["long", "short", "daily"], "format"),
    categories: groups([...new Set(items.map(category))].sort(), "category"),
    platforms: groups(platform ? [platform] : ["youtube", "instagram", "facebook"], "platform"),
    videos,
  };
}
