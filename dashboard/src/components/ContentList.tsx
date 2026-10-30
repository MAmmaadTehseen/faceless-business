"use client";
import { SeriesReport } from "./SeriesReport";
import { metric } from "@/lib/content-filters";
import { category } from "@/lib/categories";
import type { ContentItem } from "@/lib/content-data";
import { channelMeta } from "@/lib/channels";
import { fmtDate } from "@/lib/format";
export function views(c: ContentItem) {
  return c.publications.reduce((n, p) => n + (p.metric?.views ?? 0), 0);
}
export function ContentList({
  items,
  limit = Infinity,
  dates = [],
  daily = {},
  sort = "newest",
}: {
  items: ContentItem[];
  limit?: number;
  sort?: string;
  dates?: string[];
  daily?: Record<string, number[]>;
}) {
  const shown = items.slice(0, limit);
  return (
    <SeriesReport
      key={sort}
      name="content"
      initialSort={
        sort === "newest" || sort === "oldest"
          ? "published"
          : sort === "lowest"
            ? "views"
            : sort
      }
      initialDescending={sort !== "oldest" && sort !== "lowest"}
      dates={dates}
      chart={dates.length > 0}
      columns={[
        { key: "views", label: "Views", share: true },
        { key: "likes", label: "Likes", share: true },
        { key: "comments", label: "Comments", share: true },
        { key: "watch", label: "Watch %", format: "percent" },
        { key: "published", label: "Created (UTC)", format: "date" },
      ]}
      rows={shown.map((c) => ({
        id: c.id,
        title: c.title,
        status:
          c.status === "failed" ||
          c.qa_status === "failed" ||
          c.publications.some((p) => p.status === "failed")
            ? "failed"
            : c.publications.some((p) => p.status === "queued")
              ? "queued"
              : c.publications.some(
                    (p) =>
                      p.status === "scheduled" ||
                      p.privacy === "scheduled" ||
                      (p.publish_at && Date.parse(p.publish_at) > Date.now()),
                  )
                ? "scheduled"
                : c.status,
        subtitle: `${channelMeta(c.channel)?.short ?? c.channel} · ${fmtDate(c.created_at)} · ${category(c)} · QA ${c.qa_status}`,
        links: c.publications
          .filter((p) => p.url)
          .map((p) => ({
            label: `${p.platform} · ${p.privacy ?? p.status}`,
            href: p.url!,
          })),
        href:
          c.publications.find((p) => p.url)?.url ??
          `/content?q=${encodeURIComponent(c.title)}`,
        thumbnail: /^https?:\/\//.test(c.thumbnail_path ?? "")
          ? c.thumbnail_path
          : null,
        duration: (c as ContentItem & { duration_sec?: number }).duration_sec,
        daily: daily[c.id],
        values: {
          published: Date.parse(c.created_at),
          views: views(c),
          likes: metric(c, "likes"),
          comments: metric(c, "comments"),
          watch: metric(c, "watch") < 0 ? null : metric(c, "watch"),
        },
      }))}
    />
  );
}
