import { getAnalytics } from "@/lib/analytics";
import { getPlatformContent } from "@/lib/content-data";
import { getChannelFilter } from "@/lib/channel-filter";
import { parseChannelFilter } from "@/lib/channels";
import { filterContent } from "@/lib/content-filters";
import { ContentFilters } from "@/components/ContentFilters";
import { ContentList } from "@/components/ContentList";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
export default async function ContentPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await searchParams;
  const channel = sp.channel
    ? parseChannelFilter(sp.channel)
    : await getChannelFilter();
  const allItems = await getPlatformContent(channel, sp.days, sp.platform);
  const items = filterContent(allItems, sp);
  const analytics = await getAnalytics(
    channel,
    [1, 7, 28, 30, 90].includes(Number(sp.days)) ? Number(sp.days) : 28,
    sp.days === "all",
    sp.platform,
  );
  return (
    <div className="space-y-5">
      <PageHeader title="Content" />
      <div className="hero"><p className="hero-label">Videos in this view</p><p className="hero-value">{items.length}</p><p className="text-xs text-muted mt-2">{items.filter(c => c.publications.some(p => p.status === "failed") || c.qa_status === "failed").length} need attention</p></div>
      <ContentFilters sp={sp} channel={channel} path="/content" />
      <Section title="Videos">

        <ContentList
          items={items}
          allItems={allItems}
          dates={analytics.daily.map(d => d.date)}
          initialChartVisible={false}
          sort={sp.sort ?? "newest"}

          daily={Object.fromEntries(
            analytics.videos.map((v) => [v.id, v.daily]),
          )}
        />
        <details className="text-xs text-muted"><summary>Metric definitions</summary><p>
          Table metrics are latest cumulative totals. Chart shows daily view
          growth for the selected period (28 days by default), in UTC. Hub article views use the selected period; likes and comments are not collected for Hub.
        </p></details>
      </Section>
    </div>
  );
}
