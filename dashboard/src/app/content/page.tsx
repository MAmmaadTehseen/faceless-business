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
  const items = filterContent(await getPlatformContent(channel, sp.days, sp.platform), sp);
  const analytics = await getAnalytics(
    channel,
    [1, 7, 28, 30, 90].includes(Number(sp.days)) ? Number(sp.days) : 28,
    sp.days === "all",
    sp.platform,
  );
  return (
    <div className="space-y-5">
      <PageHeader title="Content" count={items.length} />
      <ContentFilters sp={sp} channel={channel} path="/content" />
      <Section title="Videos">
        <p className="text-xs text-muted mb-4">
          Table metrics are latest cumulative totals. Chart shows daily view
          growth for the selected period (28 days by default), in UTC. Hub article views use the selected period; likes and comments are not collected for Hub.
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
