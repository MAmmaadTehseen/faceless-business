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
  return (
    <div className="space-y-5">
      <PageHeader title="Content" count={items.length} />
      <ContentFilters sp={sp} channel={channel} path="/content" />
      <Section title="Videos">
        <ContentList items={items} groupByDay />
      </Section>
    </div>
  );
}
