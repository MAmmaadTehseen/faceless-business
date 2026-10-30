import { HubAnalytics as Data } from "@/lib/hub-analytics";
import { channelMeta } from "@/lib/channels";
import { Section } from "./Section";
import { SeriesReport } from "./SeriesReport";
export function HubChannels({ data }: { data: Data | null }) {
  return (
    <Section title="Hub by channel">
      {data ? (
        <SeriesReport
          name="hub-channels"
          chart={false}
          columns={[
            { key: "views", label: "Views", share: true },
            { key: "youtube", label: "YouTube clicks", share: true },
          ]}
          rows={data.channels.map((c) => ({
            id: c.channel,
            title: channelMeta(c.channel)?.name ?? c.channel,
            values: { views: c.views, youtube: c.youtube },
          }))}
        />
      ) : (
        <p className="text-muted">Hub analytics unavailable.</p>
      )}
    </Section>
  );
}
export function HubAnalytics({ data: a }: { data: Data | null }) {
  if (!a)
    return (
      <p className="text-muted">
        Hub analytics unavailable. Apply migration 008 and check database
        configuration.
      </p>
    );
  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {Object.entries({
          "Page views": a.total.views,
          "Unique visitors": a.total.uniques,
          Sessions: a.total.sessions,
          "Avg seconds / page": a.seconds,
          "Median scroll depth": `${a.scroll}%`,
          "Bounce-ish rate": `${a.bounce}%`,
        }).map(([k, v]) => (
          <div className="card" key={k}>
            <p className="text-xs text-muted">{k}</p>
            <p className="stat-value mt-2">{v}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted">
        Visitors reset daily. Sessions last until tab close or 30 minutes of
        inactivity. Time counts visible seconds. Bounce-ish means one pageview
        and under 10 seconds. YouTube clicks include embed focus interactions,
        not confirmed plays. CTR is YouTube clicks / page views.
      </p>
      <Section title="Daily hub views (UTC)">
        <SeriesReport
          name="hub-daily"
          dates={a.daily.map((d) => d.date)}
          columns={[{ key: "views", label: "Page views" }]}
          rows={[
            {
              id: "hub",
              title: "Page views",
              daily: a.daily.map((d) => d.views),
              values: { views: a.total.views },
            },
          ]}
        />
      </Section>
      <Section title="Top 10 articles">
        <SeriesReport
          name="hub-articles"
          chart={false}
          columns={[
            { key: "views", label: "Views", share: true },
            { key: "uniques", label: "Uniques" },
            { key: "seconds", label: "Avg seconds" },
            { key: "embeds", label: "Embed clicks" },
            { key: "ctr", label: "YouTube CTR", format: "percent" },
          ]}
          rows={a.articles.map((r) => ({
            id: r.slug,
            title: r.slug,
            href: `https://hub.ammaad.online/a/${encodeURIComponent(r.slug)}`,
            values: {
              views: r.views,
              uniques: r.uniques,
              seconds: r.seconds,
              embeds: r.embeds,
              ctr: r.views ? (100 * r.youtube) / r.views : null,
            },
          }))}
        />
      </Section>
      <div className="grid md:grid-cols-2 gap-4">
        {[
          ["referrers", "Referrers"],
          ["sources", "UTM sources"],
          ["countries", "Top 10 countries"],
          ["devices", "Device split"],
          ["outbound", "Clicks by target"],
        ].map(([kind, title]) => (
          <Section key={kind} title={title}>
            <SeriesReport
              name={`hub-${kind}`}
              chart={false}
              columns={[
                {
                  key: "value",
                  label: kind === "outbound" ? "Clicks" : "Views",
                  share: true,
                },
              ]}
              rows={a.dimensions
                .filter((d) => d.kind === kind)
                .map((d) => ({
                  id: d.name,
                  title: d.name,
                  values: { value: d.value },
                }))}
            />
          </Section>
        ))}
      </div>
    </>
  );
}
