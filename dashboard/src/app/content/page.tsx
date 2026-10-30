import { getAnalytics } from "@/lib/analytics";
import { getContent } from "@/lib/content-data";
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
  const items = filterContent(await getContent(channel, true, sp.days), sp);
  const analytics = await getAnalytics(
    channel,
    [7, 28, 90].includes(Number(sp.days)) ? Number(sp.days) : 28,
    sp.days === "all",
  );
  return (
    <div className="space-y-5">
      <PageHeader title="Content" count={items.length} />
      <ContentFilters sp={sp} channel={channel} path="/content" />
      <Section title="Videos">
        <p className="text-xs text-muted mb-4">
          Table metrics are latest cumulative totals. Chart shows daily view
          growth for the selected period (28 days by default), in UTC.
        </p>
        <ContentList
          items={items}
          sort={sp.sort ?? "newest"}
          dates={analytics.daily.map((d) => d.date)}
          daily={Object.fromEntries(
            analytics.videos.map((v) => [v.id, v.daily]),
          )}
        />
      </Section>
    </div>
  );
}
