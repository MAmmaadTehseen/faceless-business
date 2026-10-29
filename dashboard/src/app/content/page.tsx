import { getContent } from "@/lib/content-data";
import { getChannelFilter } from "@/lib/channel-filter";
import { CHANNELS, parseChannelFilter } from "@/lib/channels";
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
  let items = await getContent(channel);
  items = items.filter(
    (c) =>
      (!sp.kind || c.kind === sp.kind) &&
      (!sp.platform ||
        c.publications.some((p) => p.platform === sp.platform)) &&
      (!sp.status ||
        (sp.status === "private"
          ? c.publications.some((p) => p.privacy === "private")
          : c.status === sp.status ||
            c.publications.some((p) => p.status === sp.status))),
  );
  return (
    <div className="space-y-5">
      <PageHeader title="Content" />
      <form className="flex gap-2 overflow-x-auto pb-2">
        <select name="channel" aria-label="Channel" defaultValue={channel}>
          <option value="all">All channels</option>
          {CHANNELS.map((c) => (
            <option key={c.key} value={c.key}>
              {c.short}
            </option>
          ))}
        </select>
        {[
          { name: "kind", label: "Types", values: ["long", "short"] },
          {
            name: "platform",
            label: "Platforms",
            values: ["youtube", "instagram", "facebook"],
          },
          {
            name: "status",
            label: "Statuses",
            values: ["queued", "failed", "private"],
          },
        ].map((f) => (
          <select
            key={f.name}
            aria-label={f.label}
            name={f.name}
            defaultValue={sp[f.name] ?? ""}
          >
            <option value="">All {f.label.toLowerCase()}</option>
            {f.values.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        ))}
        <button className="btn">Apply</button>
      </form>
      <Section title="Videos">
        <ContentList items={items} />
      </Section>
    </div>
  );
}
