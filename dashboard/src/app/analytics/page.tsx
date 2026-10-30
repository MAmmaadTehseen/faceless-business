import { SeriesReport, type ReportColumn } from "@/components/SeriesReport";
import { getHubAnalytics } from "@/lib/hub-analytics";
import { HubAnalytics, HubChannels } from "@/components/HubAnalytics";
import { ReplaceLink as Link } from "@/components/ReplaceLink";
import { getAnalytics, Totals } from "@/lib/analytics";
import { getChannelFilter } from "@/lib/channel-filter";
import { channelMeta, parseChannelFilter } from "@/lib/channels";
import { fmtNum } from "@/lib/format";
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
      className={`text-xs ${d < 0 ? "text-alert-fg" : d > 0 ? "text-ok-fg" : "text-muted"}`}
    >
      {d > 0 ? "+" : ""}
      {pp ? d.toFixed(1) + " pp" : fmtNum(d)} vs previous
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
}: {
  rows: Group[];
  dates: string[];
  format?: boolean;
  engagement?: boolean;
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
        { key: "watch", label: "Watch %", format: "percent" },
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
  const sp = await searchParams;
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
  const days = [1, 7, 28, 30, 90].includes(Number(sp.days)) ? Number(sp.days) : 28;
  const hub =
    (tab === "hub" || tab === "channels") && (!sp.platform || sp.platform === "hub")
      ? await getHubAnalytics(channel, days, sp.days === "all")
      : null;
  const a = await getAnalytics(channel, days, sp.days === "all", sp.platform);
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
      <PageHeader
        title="Analytics"
        action={
          <div className="flex flex-wrap gap-2 analytics-periods">
            {["1", "7", "28", "30", "90", "all"].map((d) => {
              const q = new URLSearchParams(sp);
              q.set("days", d);
              return (
                <Link
                  key={d}
                  className={`btn ${(sp.days ?? "28") === d ? "btn-primary" : ""}`}
                  href={`?${q}`}
                >
                  {d === "1" ? "Last 24 hours" : d === "all" ? "All time" : `${d} days`}
                </Link>
              );
            })}
          </div>
        }
      />
      {tab !== "hub" && <div className="flex flex-wrap gap-3 text-sm text-muted"><span>Reels: {a.videos.filter(v => v.kind === "short" && v.publications.some(p => ["instagram", "facebook"].includes(p.platform) && p.published_at && Date.parse(p.published_at) >= a.start && Date.parse(p.published_at) <= a.end)).length}</span><span>Posting cadence: {(a.videos.flatMap(v => v.publications).filter(p => p.published_at && (Date.parse(p.published_at) >= a.start && Date.parse(p.published_at) <= a.end)).length / a.periodDays).toFixed(1)} posts/day</span><span>Followers / subscribers: unavailable in stored metrics</span></div>}
      {tab !== "hub" && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {(
              [
                ["Views", "views"],
                ["Likes", "likes"],
                ["Comments", "comments"],
                ["Subscribers gained", "subscribers"],
                ["Average watch %", "watch"],
              ] as const
            ).map(([title, key]) => {
              const v = key === "subscribers" ? null : a.total[key];
              const old = key === "subscribers" ? null : a.previous[key];
              return (
                <div className="card" key={key}>
                  <p className="text-xs text-muted">{title}</p>
                  <p className="stat-value mt-2 text-right">
                    {v == null
                      ? "—"
                      : key === "watch"
                        ? `${v.toFixed(1)}%`
                        : fmtNum(v)}
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
          <p className="text-xs text-muted">
            Growth between cumulative snapshots; first observations include
            prior activity. Watch % is view-weighted from latest snapshots, not
            period retention. Subscriber gains are not stored. Filters below
            apply to top videos; breakdowns use the selected channel and period.
          </p>
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
      <div>
        <h2 className="text-lg font-semibold">
          {tab[0].toUpperCase() + tab.slice(1)}
        </h2>
        <p className="text-sm text-muted mt-1">{explanations[tab]}</p>
      </div>
      {tab === "hub" && <HubAnalytics data={hub} />}
      {tab === "channels" && <HubChannels data={hub} />}
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
            <Table dates={a.daily.map((d) => d.date)} rows={a.platforms} />
          </Section>
        </>
      )}
      {tab === "channels" && (
        <Section title="By channel">
          <Table dates={a.daily.map((d) => d.date)} rows={a.channels} sparks />
        </Section>
      )}
      {tab === "formats" && (
        <Section title="By format">
          <Table dates={a.daily.map((d) => d.date)} rows={a.formats} format />
        </Section>
      )}
      {tab === "categories" && (
        <Section title="By category">
          <Table dates={a.daily.map((d) => d.date)} rows={a.categories} />
        </Section>
      )}
      {tab === "engagement" && (
        <>
          <Section title="By channel">
            <Table
              dates={a.daily.map((d) => d.date)}
              rows={a.channels}
              engagement
            />
          </Section>
          <Section title="By format">
            <Table
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
    </div>
  );
}
