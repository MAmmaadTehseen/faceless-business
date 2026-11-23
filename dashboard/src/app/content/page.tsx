import { scopedSearch } from "@/lib/server-scope";
import { isOwner } from "@/lib/role";
import { RetryButton } from "@/components/RetryButton";
import { getAnalytics } from "@/lib/analytics";
import { getPlatformContent } from "@/lib/content-data";
import { getChannelFilter } from "@/lib/channel-filter";
import { parseChannelFilter } from "@/lib/channels";
import { filterContent } from "@/lib/content-filters";
import { ContentFilters } from "@/components/ContentFilters";
import { ContentList } from "@/components/ContentList";
import Link from "@/components/ScopeLink";
import { fmtCount } from "@/lib/format";
import { parseRange } from "@/lib/range";

const PAGE = 30;

export default async function ContentPage({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const sp = await scopedSearch(await searchParams);
  const owner = await isOwner();
  const channel = sp.channel ? parseChannelFilter(sp.channel) : await getChannelFilter();
  const range = parseRange(sp);
  // The header range filters by creation date (filterContent) and drives the trend chart.
  const [allItems, analytics] = await Promise.all([
    getPlatformContent(channel, undefined, sp.platform),
    getAnalytics(channel, Math.max(1, range.days), range.allTime, sp.platform, range.end),
  ]);
  const items = filterContent(allItems, sp);
  const pages = Math.max(1, Math.ceil(items.length / PAGE));
  const page = Math.min(pages, Math.max(1, Number(sp.page) || 1));
  const slice = items.slice((page - 1) * PAGE, page * PAGE);
  const ids = new Set(slice.map(c => c.id));
  const problems = items.filter(c => c.publications.some(p => p.status === "failed") || (!sp.platform && c.qa_status === "failed")).length;
  const pageHref = (n: number) => { const q = new URLSearchParams(sp); q.set("page", String(n)); return `/content?${q}`; };
  return <div>
    <h1 className="cr-h1">Content</h1>
    <p className="cr-sub">{fmtCount(items.length)} videos in this view · {problems ? <Link className="cr-link" href="/content?status=failed">{problems} need attention</Link> : "none need attention"}</p>
    <section className="cr-sec" style={{ marginTop: 14 }}>
      <ContentFilters sp={sp} channel={channel} path="/content" />
      {owner && ["failed", "queued"].includes(sp.status) && <RetryButton publications={items.flatMap(c => c.publications)} label="Retry all failed" />}
      <ContentList owner={owner} items={slice} allItems={allItems.filter(c => ids.has(c.id))} dates={analytics.daily.map(d => d.date)} initialChartVisible={false} sort={sp.sort ?? "newest"}
        daily={Object.fromEntries(analytics.videos.filter(v => ids.has(v.id)).map(v => [v.id, v.daily]))} />
      {pages > 1 && <nav className="cr-pager" aria-label="Pages">
        {page > 1 ? <Link className="btn" href={pageHref(page - 1)}>← Newer</Link> : <span />}
        <span className="cr-sub mono">{page} / {pages}</span>
        {page < pages ? <Link className="btn" href={pageHref(page + 1)}>Older →</Link> : <span />}
      </nav>}
      <details className="text-xs text-muted"><summary>Metric definitions</summary><p>Table metrics are latest cumulative totals. The chart shows daily view growth for the header&apos;s date range, in UTC. Hub article views use the selected period; likes and comments are not collected for Hub.</p></details>
    </section>
  </div>;
}
