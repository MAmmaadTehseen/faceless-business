import Link from "next/link";
import { getAnalytics, Totals } from "@/lib/analytics";
import { getChannelFilter } from "@/lib/channel-filter";
import { channelMeta } from "@/lib/channels";
import { fmtNum } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { PlatformIcon } from "@/components/PlatformIcon";
function Table({ rows }: { rows: ({ name: string } & Totals)[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-muted">
            <th className="text-left py-2">Source</th>
            {["Views", "Likes", "Comments", "Watch %"].map((h) => (
              <th key={h} className="text-right pl-4 py-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t border-border">
              <td className="py-3">{channelMeta(r.name)?.short ?? r.name}</td>
              {[r.views, r.likes, r.comments].map((v, i) => (
                <td key={i} className="text-right py-3 pl-4">
                  {fmtNum(v)}
                </td>
              ))}
              <td className="text-right py-3 pl-4">
                {r.watch == null ? "—" : `${r.watch.toFixed(1)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export default async function Analytics({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const sp = await searchParams;
  const days = [7, 28, 90].includes(Number(sp.days)) ? Number(sp.days) : 28;
  const channel = await getChannelFilter();
  const a = await getAnalytics(channel, days);
  const max = Math.max(1, ...a.daily.map((d) => d.views));
  const points = a.daily
    .map(
      (d, i) => `${40 + (i * 920) / (days - 1)},${190 - (d.views / max) * 160}`,
    )
    .join(" ");
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        action={
          <div className="flex gap-2">
            {[7, 28, 90].map((d) => (
              <Link
                className={`btn ${days === d ? "btn-primary" : ""}`}
                key={d}
                href={`/analytics?days=${d}`}
              >
                {d} days
              </Link>
            ))}
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
        ).map(([label, key]) => {
          const value = key === "subscribers" ? null : a.total[key];
          const old = key === "subscribers" ? null : a.previous[key];
          const delta = value != null && old != null ? value - old : null;
          return (
            <div key={key} className="card">
              <p className="text-xs text-muted">{label}</p>
              <p className="stat-value mt-2 text-right">
                {value == null
                  ? "—"
                  : key === "watch"
                    ? `${value.toFixed(1)}%`
                    : fmtNum(value)}
              </p>
              {delta != null && delta !== 0 && (
                <p
                  className={`mt-2 text-xs text-right tabular-nums ${delta > 0 ? "text-ok-fg" : "text-alert-fg"}`}
                >
                  {delta > 0 ? "+" : ""}
                  {key === "watch"
                    ? delta.toFixed(1) + " pp"
                    : fmtNum(delta)}{" "}
                  vs previous
                </p>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted">
        Growth between cumulative snapshots; first observations include prior
        activity. Watch % is view-weighted from the latest snapshots, not period
        retention. Subscriber gains are not stored.
      </p>
      <Section title="Platforms">
        <Table rows={a.platform} />
      </Section>
      {channel === "all" && (
        <Section title="Channels">
          <Table rows={a.channels} />
        </Section>
      )}
      <Section title="Views per day">
        <svg
          role="img"
          aria-label="Daily view growth from metric snapshots"
          viewBox="0 0 1000 230"
          className="w-full"
        >
          <text x="0" y="25" fill="var(--muted)" fontSize="14">
            {fmtNum(max)}
          </text>
          <line x1="40" y1="190" x2="960" y2="190" stroke="var(--border)" />
          <polygon
            points={`40,190 ${points} 960,190`}
            fill="var(--accent-soft)"
          />
          <polyline
            points={points}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="3"
          />
          {a.daily.map((d, i) => (
            <circle
              key={d.date}
              cx={40 + (i * 920) / (days - 1)}
              cy={190 - (d.views / max) * 160}
              r="3"
              fill="var(--accent)"
            >
              <title>{`${d.date}: ${d.views} views`}</title>
            </circle>
          ))}
          <text x="40" y="220" fill="var(--muted)" fontSize="14">
            {a.daily[0]?.date}
          </text>
          <text
            x="960"
            y="220"
            textAnchor="end"
            fill="var(--muted)"
            fontSize="14"
          >
            {a.daily.at(-1)?.date}
          </text>
        </svg>
      </Section>
      <Section title="Top 10 videos">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted">
                <th className="text-left py-2">Video</th>
                <th className="text-right">Views</th>
                <th className="text-right pl-4">Likes</th>
                <th className="text-right pl-4">Comments</th>
              </tr>
            </thead>
            <tbody>
              {a.top.map((v) => (
                <tr key={v.id} className="border-t border-border">
                  <td className="py-3 pr-3">
                    <span>{v.title}</span>
                    <div className="flex gap-3 mt-2">
                      {v.publications.map((p) => (
                        <PlatformIcon
                          key={p.id}
                          platform={p.platform}
                          url={p.url}
                          locked={p.privacy !== "public"}
                        />
                      ))}
                    </div>
                  </td>
                  {[v.views, v.likes, v.comments].map((n, i) => (
                    <td key={i} className="text-right py-3 pl-4">
                      {fmtNum(n)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {!a.top.length && (
            <p className="text-sm text-muted">No metrics yet.</p>
          )}
        </div>
      </Section>
    </div>
  );
}
