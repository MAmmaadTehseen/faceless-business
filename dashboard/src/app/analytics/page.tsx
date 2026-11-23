import { DonutCard } from "@/components/Donut";
import { parseRange } from "@/lib/range";
import { scopedSearch } from "@/lib/server-scope";
import { AutoFilters } from "@/components/AutoFilters";
import { SeriesReport, type ReportColumn } from "@/components/SeriesReport";
import { getHubAnalytics } from "@/lib/hub-analytics";
import { HubAnalytics, HubChannels } from "@/components/HubAnalytics";
import { ReplaceLink as Link } from "@/components/ReplaceLink";
import { getAnalytics, Totals } from "@/lib/analytics";
import { getChannelFilter } from "@/lib/channel-filter";
import { CHANNELS, accentCss, channelMeta, parseChannelFilter } from "@/lib/channels";
import { fmtCount } from "@/lib/format";
import { filterContent } from "@/lib/content-filters";
import { ContentFilters } from "@/components/ContentFilters";
import { ContentList } from "@/components/ContentList";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
const names: Record<string, string> = {
  long: "Long",
  short: "Shorts from videos",
  daily: "Daily Shorts",
};
const label = (n: string) => channelMeta(n)?.short ?? names[n] ?? n;
function Delta({
  value,
  old,
  pp = false,
}: {
  value: number;
  old: number;
  pp?: boolean;
}) {
  const d = value - old;
  return (
    <span
      title={pp ? undefined : String(d)}
      className={`text-xs ${d < 0 ? "text-muted" : d > 0 ? "text-muted" : "text-muted"}`}
    >
      {d > 0 ? "+" : ""}
      {pp ? d.toFixed(1) + " pp" : fmtCount(d)} vs previous
    </span>
  );
}
type Group = Totals & {
  name: string;
  count: number;
  previous: Totals;
  daily: number[];
};
function Table({
  rows,
  dates,
  format = false,
  engagement = false,
  watch = true,
}: {
  rows: Group[];
  dates: string[];
  format?: boolean;
  engagement?: boolean;
  watch?: boolean;
  sparks?: boolean;
}) {
  const columns: ReportColumn[] = engagement
    ? [
        { key: "views", label: "Views", share: true },
        { key: "likeRate", label: "Likes / views", format: "percent" },
        { key: "commentRate", label: "Comments / views", format: "percent" },
      ]
    : [
        { key: "views", label: "Views", share: true },
        { key: "count", label: "Items", share: true },
        ...(format ? [{ key: "average", label: "Avg views / item" }] : []),
        ...(watch ? [{ key: "watch", label: "Watch %", format: "percent" as const }] : []),
      ];
  return (
    <SeriesReport
      name="views-by-source"
      dates={dates}
      columns={columns}
      rows={rows.map((r) => ({
        id: r.name,
        title: label(r.name),
        daily: r.daily,
        values: {
          views: r.views,
          count: r.count,
          watch: r.watch,
          average: r.count ? r.views / r.count : null,
          likeRate: r.views ? (100 * r.likes) / r.views : null,
          commentRate: r.views ? (100 * r.comments) / r.views : null,
        },
      }))}
    />
  );
}
export default async function Analytics({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await scopedSearch(await searchParams);
  const channel = sp.channel
    ? parseChannelFilter(sp.channel)
    : await getChannelFilter();
  const tabs = [
    "hub",
    "overview",
    "platforms",
    "channels",
    "formats",
    "categories",
    "engagement",
  ];
  const tab = sp.platform === "hub" ? "hub" : tabs.includes(sp.tab) ? sp.tab : "overview";
  // All-time uses the full stored history, rounded up to whole days.
  const range = parseRange(sp);
  const days = range.days;
  const hub =
    (tab === "hub" || tab === "channels") && (!sp.platform || sp.platform === "hub")
      ? await getHubAnalytics(channel, Math.max(1, Math.round(days)), range.allTime)
      : null;
  const a = await getAnalytics(channel, days, range.allTime, sp.platform, range.end);
  const periodItems = a.videos.map((c) => ({
    ...c,
    publications: c.publications.map((p, i) => ({
      ...p,
      metric:
        i === 0
          ? {
              id: 0,
              publication_id: p.id,
              captured_at: "",
              views: c.views,
              likes: c.likes,
              comments: c.comments,
              shares: 0,
              ctr: c.watch,
              avg_view_duration_sec: null,
              impressions: null,
            }
          : null,
    })),
  }));
  const top = filterContent(periodItems, sp, "views", false).slice(0, 10);
  const ranked = a.videos
    .filter((v) => v.views > 0)
    .map((v) => ({ ...v, rate: (100 * (v.likes + v.comments)) / v.views }))
    .sort((a, b) => b.rate - a.rate);
  const explanations: Record<string, string> = {
    hub: "First-party, cookie-free site activity for the selected channel and period.",
    overview: "Daily view growth and your strongest videos for this period.",
    platforms:
      "Compare platform growth and each platform’s contribution per day.",
    channels: "Compare channel performance and daily view trends.",
    formats:
      "Compare long videos, Shorts from videos and daily standalone Shorts.",
    categories:
      "Views and content counts, categorised from tags, topic and title at read time.",
    engagement:
      "Likes and comments as a share of views; rankings exclude videos with zero views.",
  };
  return (
    <div className="space-y-6">
      <div><h1 className="cr-h1">Analytics</h1><p className="cr-sub">{range.label} · {channel === "all" ? "all channels" : channelMeta(channel)?.short} · {sp.platform ? sp.platform : "all platforms"}</p></div>
      {tab !== "hub" && <div className="cr-two">
        <DonutCard label="Views by channel" size={136} center={fmtCount(a.total.views)} sub="views" slices={CHANNELS.filter(c => channel === "all" || c.key === channel).map(c => ({ label: c.short, value: a.channels.find(x => x.name === c.key)?.views ?? 0, color: accentCss(c) }))} />
        <div className="grid gap-4">
          <DonutCard label="Views by platform" size={112} slices={a.platforms.map((p, i) => ({ label: p.name === "youtube" ? "YouTube" : p.name === "instagram" ? "Instagram" : p.name === "facebook" ? "Facebook" : p.name, value: p.views, color: ["var(--accent)", "var(--warn)", "var(--muted)"][i] ?? "var(--ok)" }))} />
          <DonutCard label="Views by format" size={112} slices={a.formats.map((f, i) => ({ label: f.name === "long" ? "Long videos" : f.name === "short" ? "Shorts from videos" : "Daily Shorts", value: f.views, color: ["var(--fg)", "var(--accent)", "var(--muted)"][i] }))} />
        </div>
      </div>}
      {tab !== "hub" && (
        <>
          <div className="analytics-stats grid grid-cols-2 lg:grid-cols-4 gap-3">
            {(
              [
                ["Views", "views"],
                ["Likes", "likes"],
                ["Comments", "comments"],
                ["Average watch %", "watch"],
              ] as const
            ).filter(([,key]) => key !== "watch" || !sp.platform || sp.platform === "youtube").map(([title, key]) => {
              const v = a.total[key];
              const old = a.previous[key];
              return (
                <div className="card" key={key}>
                  <p className="text-xs text-muted">{title}</p>
                  <p title={key === "watch" || v == null ? undefined : String(v)} className={`${key === "views" ? "hero-value" : "stat-value"} mt-2 text-right`}>
                    {v == null
                      ? "—"
                      : key === "watch"
                        ? `${v.toFixed(1)}%`
                        : fmtCount(v)}
                  </p>
                  {v != null && old != null && sp.days !== "all" && (
                    <div className="text-right mt-2">
                      <Delta value={v} old={old} pp={key === "watch"} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

        </>
      )}
      <nav
        className="flex gap-1 overflow-x-auto"
        aria-label="Analytics sections"
      >
        {tabs.map((t) => {
          const q = new URLSearchParams(sp);
          q.set("tab", t);
          return (
            <Link
              key={t}
              href={`?${q}`}
              aria-current={t === tab ? "page" : undefined}
              className={`btn ${t === tab ? "btn-primary" : ""}`}
            >
              {t[0].toUpperCase() + t.slice(1)}
            </Link>
          );
        })}
      </nav>

      {tab !== "hub" && sp.platform && sp.platform !== "youtube" && sp.platform !== "hub" && <p className="text-xs text-muted">Watch percentage is available for YouTube only.</p>}
      {tab === "hub" && (sp.platform && sp.platform !== "hub" ? <p className="text-muted">Hub analytics do not apply to the selected platform.</p> : <HubAnalytics data={hub} />)}
      {tab !== "hub" && tab !== "overview" && <ContentFilters sp={sp} channel={channel} path="/analytics" defaultSort="views" analytics />}
      {tab === "overview" && (
        <>
          <ContentFilters
            sp={sp}
            channel={channel}
            path="/analytics"
            defaultSort="views"
            analytics
          />
          <Section title="Top videos">
            <ContentList
              sort={sp.sort ?? "views"}
              items={top}
              dates={a.daily.map((d) => d.date)}
              daily={Object.fromEntries(a.videos.map((v) => [v.id, v.daily]))}
            />
          </Section>
        </>
      )}
      {tab === "platforms" && (
        <>
          <Section title="By platform">
            <Table watch={!sp.platform || sp.platform === "youtube"} dates={a.daily.map((d) => d.date)} rows={a.platforms} />
          </Section>
        </>
      )}
      {tab === "channels" && (
        <Section title="By channel">
          <Table watch={!sp.platform || sp.platform === "youtube"} dates={a.daily.map((d) => d.date)} rows={a.channels} sparks />
        </Section>
      )}
      {tab === "formats" && (
        <Section title="By format">
          <Table watch={!sp.platform || sp.platform === "youtube"} dates={a.daily.map((d) => d.date)} rows={a.formats} format />
        </Section>
      )}
      {tab === "categories" && (
        <Section title="By category">
          <Table watch={!sp.platform || sp.platform === "youtube"} dates={a.daily.map((d) => d.date)} rows={a.categories} />
        </Section>
      )}
      {tab === "engagement" && (
        <>
          <Section title="By channel">
            <Table watch={!sp.platform || sp.platform === "youtube"}
              dates={a.daily.map((d) => d.date)}
              rows={a.channels}
              engagement
            />
          </Section>
          <Section title="By format">
            <Table watch={!sp.platform || sp.platform === "youtube"}
              dates={a.daily.map((d) => d.date)}
              rows={a.formats}
              engagement
            />
          </Section>
          {[
            ["Best 5", ranked.slice(0, 5)],
            ["Worst 5", [...ranked].reverse().slice(0, 5)],
          ].map(([title, rows]) => (
            <Section key={title as string} title={title as string}>
              <SeriesReport
                name={String(title).toLowerCase().replace(" ", "-")}
                chart={false}
                columns={[
                  { key: "rate", label: "Engagement", format: "percent" },
                  { key: "views", label: "Views", share: true },
                ]}
                rows={(rows as typeof ranked).map((v) => ({
                  id: v.id,
                  title: v.title,
                  href:
                    v.publications.find((p) => p.url)?.url ??
                    `/content?q=${encodeURIComponent(v.title)}`,
                  values: { rate: v.rate, views: v.views },
                }))}
              />
            </Section>
          ))}
        </>
      )}
      {tab === "channels" && hub && <details><summary className="text-sm text-muted">Hub channel details</summary><HubChannels data={hub} /></details>}
      {tab !== "hub" && (<details className="text-xs text-muted"><summary>Metric definitions</summary><p>
            Growth between cumulative snapshots; first observations include
            prior activity. Watch % is view-weighted from latest snapshots, not
            period retention. Subscriber gains are not stored. Filters below
            apply to top videos; breakdowns use the selected channel and period.
          </p></details>)}
    </div>
  );
}
