import Link from "next/link";
import { getAnalytics, Totals } from "@/lib/analytics";
import { getChannelFilter } from "@/lib/channel-filter";
import { channelMeta, parseChannelFilter } from "@/lib/channels";
import { fmtNum } from "@/lib/format";
import { filterContent } from "@/lib/content-filters";
import { ContentFilters } from "@/components/ContentFilters";
import { ContentList } from "@/components/ContentList";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { PlatformIcon } from "@/components/PlatformIcon";
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
function Spark({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  return (
    <svg
      viewBox="0 0 160 36"
      role="img"
      aria-label="Daily views sparkline"
      className="w-32 h-9"
    >
      <polyline
        points={values
          .map(
            (v, i) =>
              `${(i * 160) / Math.max(1, values.length - 1)},${34 - (v / max) * 32}`,
          )
          .join(" ")}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
      />
    </svg>
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
  format = false,
  engagement = false,
  sparks = false,
}: {
  rows: Group[];
  format?: boolean;
  engagement?: boolean;
  sparks?: boolean;
}) {
  const headings = engagement
    ? ["Views", "Likes / views", "Comments / views"]
    : ["Views", "Items", ...(format ? ["Avg views / item"] : []), "Watch %"];
  return (
    <>
      {!rows.length && (
        <p className="text-sm text-muted">
          No metrics yet. Sync published content to populate this breakdown.
        </p>
      )}
      <table className="responsive-table w-full text-sm">
        <thead>
          <tr>
            <th className="text-left py-2">Source</th>
            {headings.map((h) => (
              <th key={h} className="text-right py-2">
                {h}
              </th>
            ))}
            {sparks && <th>Trend</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const vals = engagement
              ? [
                  fmtNum(r.views),
                  r.views ? `${((100 * r.likes) / r.views).toFixed(2)}%` : "—",
                  r.views
                    ? `${((100 * r.comments) / r.views).toFixed(2)}%`
                    : "—",
                ]
              : [
                  fmtNum(r.views),
                  fmtNum(r.count),
                  ...(format
                    ? [r.count ? fmtNum(Math.round(r.views / r.count)) : "—"]
                    : []),
                  r.watch == null ? "—" : `${r.watch.toFixed(1)}%`,
                ];
            return (
              <tr key={r.name} className="border-t border-border">
                <td className="py-3">
                  <span className="flex items-center gap-2">
                    {["youtube", "instagram", "facebook"].includes(r.name) && (
                      <PlatformIcon platform={r.name} />
                    )}{" "}
                    {label(r.name)}
                  </span>
                </td>
                {vals.map((v, i) => (
                  <td
                    data-label={headings[i]}
                    className="py-3 text-right"
                    key={i}
                  >
                    {v}
                    {i === 0 && (
                      <div>
                        <Delta value={r.views} old={r.previous.views} />
                      </div>
                    )}
                    {engagement &&
                      i > 0 &&
                      r.views > 0 &&
                      r.previous.views > 0 && (
                        <div>
                          <Delta
                            pp
                            value={
                              (100 * (i === 1 ? r.likes : r.comments)) / r.views
                            }
                            old={
                              (100 *
                                (i === 1
                                  ? r.previous.likes
                                  : r.previous.comments)) /
                              r.previous.views
                            }
                          />
                        </div>
                      )}
                  </td>
                ))}
                {sparks && (
                  <td data-label="Daily views">
                    <Spark values={r.daily} />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
function Chart({
  series,
  dates,
  stacked = false,
}: {
  series: { name: string; daily: number[] }[];
  dates: string[];
  stacked?: boolean;
}) {
  const colors = ["#7fb0ff", "#6ee7b7", "#fcd34d"];
  const max = Math.max(
    1,
    ...dates.map((_, i) =>
      stacked
        ? series.reduce((n, s) => n + (s.daily[i] ?? 0), 0)
        : Math.max(...series.map((s) => s.daily[i] ?? 0)),
    ),
  );
  return (
    <>
      <div className="flex flex-wrap gap-4 text-xs text-muted">
        {series.map((s, i) => (
          <span key={s.name} style={{ color: colors[i % 3] }}>
            {label(s.name)}
          </span>
        ))}
      </div>
      <svg
        role="img"
        aria-label={
          stacked ? "Stacked daily platform views" : "Daily view growth"
        }
        viewBox="0 0 1000 230"
        className="w-full"
      >
        <text x="8" y="18" fill="var(--muted)" fontSize="14">
          {fmtNum(max)}
        </text>
        <line x1="40" y1="190" x2="960" y2="190" stroke="var(--border)" />
        {stacked
          ? dates.map((date, i) => {
              let base = 0;
              return series.map((s, j) => {
                const v = s.daily[i] ?? 0;
                const y = 190 - ((base + v) / max) * 155;
                base += v;
                return (
                  <rect
                    key={`${date}-${j}`}
                    x={40 + (i * 920) / dates.length}
                    y={y}
                    width={Math.max(1, 920 / dates.length - 2)}
                    height={(v / max) * 155}
                    fill={colors[j % 3]}
                  >
                    <title>{`${date}: ${label(s.name)} · ${fmtNum(v)} views`}</title>
                  </rect>
                );
              });
            })
          : series.map((s, j) => (
              <polyline
                key={s.name}
                points={s.daily
                  .map(
                    (v, i) =>
                      `${40 + (i * 920) / Math.max(1, dates.length - 1)},${190 - (v / max) * 155}`,
                  )
                  .join(" ")}
                fill="none"
                stroke={colors[j % 3]}
                strokeWidth="3"
              />
            ))}
        <text x="40" y="220" fill="var(--muted)" fontSize="14">
          {dates[0]}
        </text>
        <text
          x="960"
          y="220"
          textAnchor="end"
          fill="var(--muted)"
          fontSize="14"
        >
          {dates.at(-1)}
        </text>
      </svg>
    </>
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
    "overview",
    "platforms",
    "channels",
    "formats",
    "categories",
    "engagement",
  ];
  const tab = tabs.includes(sp.tab) ? sp.tab : "overview";
  // All-time uses the full stored history, rounded up to whole days.
  const days = [7, 28, 90].includes(Number(sp.days)) ? Number(sp.days) : 28;
  const a = await getAnalytics(channel, days, sp.days === "all");
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
          <div className="flex gap-2">
            {["7", "28", "90", "all"].map((d) => {
              const q = new URLSearchParams(sp);
              q.set("days", d);
              return (
                <Link
                  key={d}
                  className={`btn ${(sp.days ?? "28") === d ? "btn-primary" : ""}`}
                  href={`?${q}`}
                >
                  {d === "all" ? "All time" : `${d} days`}
                </Link>
              );
            })}
          </div>
        }
      />
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
        Growth between cumulative snapshots; first observations include prior
        activity. Watch % is view-weighted from latest snapshots, not period
        retention. Subscriber gains are not stored. Filters below apply to top
        videos; breakdowns use the selected channel and period.
      </p>
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
      {tab === "overview" && (
        <>
          <Section title="Views per day">
            <Chart
              dates={a.daily.map((d) => d.date)}
              series={[{ name: "Views", daily: a.daily.map((d) => d.views) }]}
            />
          </Section>
          <ContentFilters
            sp={sp}
            channel={channel}
            path="/analytics"
            defaultSort="views"
            analytics
          />
          <Section title="Top videos">
            <ContentList items={top} />
          </Section>
        </>
      )}
      {tab === "platforms" && (
        <>
          <Section title="By platform">
            <Table rows={a.platforms} />
          </Section>
          <Section title="Views per day">
            <Chart
              dates={a.daily.map((d) => d.date)}
              series={a.platforms}
              stacked
            />
          </Section>
        </>
      )}
      {tab === "channels" && (
        <Section title="By channel">
          <Table rows={a.channels} sparks />
        </Section>
      )}
      {tab === "formats" && (
        <Section title="By format">
          <Table rows={a.formats} format />
        </Section>
      )}
      {tab === "categories" && (
        <Section title="By category">
          <Table rows={a.categories} />
        </Section>
      )}
      {tab === "engagement" && (
        <>
          <Section title="By channel">
            <Table rows={a.channels} engagement />
          </Section>
          <Section title="By format">
            <Table rows={a.formats} engagement />
          </Section>
          {[
            ["Best 5", ranked.slice(0, 5)],
            ["Worst 5", [...ranked].reverse().slice(0, 5)],
          ].map(([title, rows]) => (
            <Section key={title as string} title={title as string}>
              {(rows as typeof ranked).length === 0 && (
                <p className="text-sm text-muted">
                  No viewed videos yet. Sync metrics to compare engagement.
                </p>
              )}
              {(rows as typeof ranked).map((v) => (
                <div
                  key={v.id}
                  className="flex justify-between gap-3 border-b border-border py-2 text-sm"
                >
                  <span>{v.title}</span>
                  <span className="tabular-nums whitespace-nowrap">
                    {v.rate.toFixed(2)}%
                  </span>
                </div>
              ))}
            </Section>
          ))}
        </>
      )}
    </div>
  );
}
