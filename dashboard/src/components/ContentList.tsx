"use client";
import { useState } from "react";
import { RebuildButton } from "./RebuildButton";
import { recoveryAction } from "@/lib/recovery";
import { RetryButton } from "./RetryButton";
import { useSearchParams } from "next/navigation";
import { contentHref } from "@/lib/content-link";
import { SeriesReport } from "./SeriesReport";
import { metric } from "@/lib/content-filters";
import { category } from "@/lib/categories";
import type { ContentItem } from "@/lib/content-data";
import { channelMeta } from "@/lib/channels";
import { fmtDate, fmtCount } from "@/lib/format";
export function views(c: ContentItem) {
  return c.publications.reduce((n, p) => n + (p.metric?.views ?? 0), 0);
}
export function ContentList({
  items,
  owner = false,
  allItems,
  initialChartVisible = true,
  limit = Infinity,
  dates = [],
  daily = {},
  sort = "newest",
}: {
  items: ContentItem[];
  owner?: boolean;
  allItems?: ContentItem[];
  initialChartVisible?: boolean;
  limit?: number;
  sort?: string;
  dates?: string[];
  daily?: Record<string, number[]>;
}) {
  const params = useSearchParams();
  const scoped = !!params.get("platform") && params.get("platform") !== "all";
  function status(c: ContentItem) {
    if (!scoped && c.status === "killed") return "killed";
    if ((!scoped && (c.status === "failed" || c.qa_status === "failed")) || c.publications.some(p => p.status === "failed")) return "failed";
    if (c.publications.some(p => p.status === "queued")) return "queued";
    if (c.publications.some(p => p.status === "scheduled" || p.privacy === "scheduled" || (p.publish_at && Date.parse(p.publish_at) > Date.now()))) return "scheduled";
    if (c.publications.some(p => ["published","live"].includes(p.status) && p.privacy === "public")) return "live";
    if (c.publications.some(p => p.privacy === "private")) return "private";
    return scoped ? c.publications[0]?.status ?? "No publication" : c.status;
  }
  const [visible,setVisible] = useState(20);
  const shown = items.slice(0, limit);
  const analyticsReport = dates.length > 0 && initialChartVisible;
  const report = (<SeriesReport
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
      initialChartVisible={initialChartVisible}
      columns={[
        { key: "views", label: "Views", share: true },
        { key: "likes", label: "Likes", share: true },
        { key: "comments", label: "Comments", share: true },
        ...(!params.get("platform") || ["all","youtube"].includes(params.get("platform")!) ? [{ key: "watch", label: "Watch %", format: "percent" as const }] : []),
        { key: "published", label: "Created (UTC)", format: "date", detailOnly:true },
      ]}
      rows={shown.map((c) => ({
        id: c.id,
        actions: owner ? <span className="flex gap-2">{recoveryAction(c, c.publications) !== "retry" ? <RebuildButton id={c.id}/> : c.publications.filter(p => ["failed", "queued"].includes(p.status)).map(p => <RetryButton key={p.id} publications={[p]} label={`Retry ${p.platform}`}/>)}</span> : undefined,
        title: c.title,
        status: status(c),
        subtitle: `${channelMeta(c.channel)?.short ?? c.channel} · ${fmtDate(c.created_at)} · ${category(c)} · QA ${c.qa_status}`,
        links: (allItems?.find(item => item.id === c.id) ?? c).publications
          .filter((p) => p.url)
          .map((p) => ({
            label: `${p.platform} · ${p.privacy ?? p.status} · ${fmtCount(p.metric?.views ?? 0)} views · ${fmtCount(p.metric?.likes ?? 0)} likes · ${fmtCount(p.metric?.comments ?? 0)} comments`,
            title: `${p.metric?.views ?? 0} views · ${p.metric?.likes ?? 0} likes · ${p.metric?.comments ?? 0} comments`,
            href: p.url!,
          })),
        href:
          contentHref(c, params.toString()),
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
    />);
  return (
    <><div className={`mobile-content-list ${analyticsReport ? "mobile-content-hidden" : ""}`}>{!shown.length && <div className="py-6"><p className="text-muted">No videos match this view.</p><a className="btn mt-3" href="/content">Clear filters</a></div>}{shown.slice(0,visible).map(c=><a key={c.id} className="mobile-content-row" href={contentHref(c,params.toString())}>{/^https?:\/\//.test(c.thumbnail_path ?? "") ? <img src={c.thumbnail_path!} alt=""/> : <span className="content-thumbnail-empty" aria-hidden>▶</span>}<span className="mobile-content-copy"><strong>{c.title}</strong><span><span className="status-chip">{status(c)}</span><span title={String(views(c))}>{fmtCount(views(c))} views</span></span></span></a>)}{shown.length>visible && <button className="btn w-full" onClick={()=>setVisible(n=>n+20)}>Load more</button>}</div><div className={`desktop-content-list ${analyticsReport ? "analytics-report" : ""}`}>{report}</div>{!analyticsReport && <details className="mobile-content-tools"><summary>Trends and export</summary>{report}</details>}</>
  );
}
