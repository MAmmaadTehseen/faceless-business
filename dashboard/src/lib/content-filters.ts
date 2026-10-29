import type { ContentItem } from "./content-data";
import { category } from "./categories";
export type Filters = Record<string, string | undefined>;
export const sorts = {
  newest: "Newest",
  oldest: "Oldest",
  views: "Most views",
  likes: "Most likes",
  comments: "Most comments",
  watch: "Best watch %",
  lowest: "Lowest views",
};
export function formatKind(c: { kind: string; parent_id: string | null }) {
  return c.kind === "long" ? "long" : c.parent_id ? "short" : "daily";
}
export function metric(c: ContentItem, key: string): number {
  const ms = c.publications.map((p) => p.metric).filter((m) => m != null);
  if (key === "watch") {
    const valid = ms.filter((m) => m.ctr != null && m.views > 0);
    const weight = valid.reduce((n, m) => n + m.views, 0);
    return weight
      ? valid.reduce((n, m) => n + m.ctr! * m.views, 0) / weight
      : -1;
  }
  return ms.reduce(
    (n, m) =>
      n +
      (key === "likes" ? m.likes : key === "comments" ? m.comments : m.views),
    0,
  );
}
export function filterContent(
  items: ContentItem[],
  sp: Filters,
  defaultSort = "newest",
  useDate = true,
) {
  const days = Number(sp.days);
  const query = (sp.q ?? "").trim().toLowerCase();
  return items
    .filter((c) => {
      const pubs = c.publications.filter(
        (p) => !sp.platform || p.platform === sp.platform,
      );
      const status = sp.status;
      const matches =
        !status ||
        status === "all" ||
        (status === "scheduled"
          ? pubs.some(
              (p) =>
                p.status === "scheduled" ||
                p.privacy === "scheduled" ||
                (!!p.publish_at && Date.parse(p.publish_at) > Date.now()),
            )
          : status === "live"
            ? pubs.some(
                (p) =>
                  ["live", "published"].includes(p.status) &&
                  p.privacy === "public" &&
                  (!p.publish_at || Date.parse(p.publish_at) <= Date.now()),
              )
            : ["private", "public"].includes(status)
              ? pubs.some((p) => p.privacy === status)
              : c.status === status || pubs.some((p) => p.status === status));
      return (
        (!query || `${c.title} ${c.topic}`.toLowerCase().includes(query)) &&
        (!sp.channel || sp.channel === "all" || sp.channel === c.channel) &&
        (!sp.kind ||
          (sp.kind === "short"
            ? c.kind === "short"
            : formatKind(c) === sp.kind) ||
          (sp.kind === "derived" && formatKind(c) === "short")) &&
        (!sp.category || category(c) === sp.category) &&
        (!sp.platform || pubs.length > 0) &&
        matches &&
        (!useDate ||
          ![7, 28, 90].includes(days) ||
          Date.parse(c.created_at) >= Date.now() - days * 86400000)
      );
    })
    .sort((a, b) => {
      const s = sp.sort ?? defaultSort;
      return s === "newest" || s === "oldest"
        ? (Date.parse(a.created_at) - Date.parse(b.created_at)) *
            (s === "oldest" ? 1 : -1)
        : (metric(b, s) - metric(a, s)) * (s === "lowest" ? -1 : 1) ||
            a.id.localeCompare(b.id);
    });
}
