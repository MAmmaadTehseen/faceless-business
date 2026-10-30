import { HubAnalytics } from "@/components/HubAnalytics";
import { SeriesReport } from "@/components/SeriesReport";
import { getAnalytics } from "@/lib/analytics";
import { getHubAnalytics } from "@/lib/hub-analytics";
import { ContentFilters } from "@/components/ContentFilters";
import { filterContent } from "@/lib/content-filters";
import { parseChannelFilter } from "@/lib/channels";
import Link from "next/link";
import { getOverview } from "@/lib/data";
import { getContent } from "@/lib/content-data";
import { getChannelFilter } from "@/lib/channel-filter";
import { isOwner } from "@/lib/role";
import { CHANNELS } from "@/lib/channels";
import { fmtDate, fmtUsd } from "@/lib/format";
import { ContentList } from "@/components/ContentList";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { ActionButton } from "@/components/ActionButton";
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await searchParams;
  const channel = sp.channel
    ? parseChannelFilter(sp.channel)
    : await getChannelFilter();
  const [ov, items, owner] = await Promise.all([
    getOverview(channel, sp.platform),
    getContent(channel, true, sp.days),
    isOwner(),
  ]);
  const analytics = await getAnalytics(channel, 7, false, sp.platform);
  const attention =
    Number(ov.paused) +
    Number(!!ov.failedRun) +
    ov.failedPubs.length +
    ov.failedContent.length +
    Number(ov.costs.pct >= 80);
  const hub = !sp.platform || sp.platform === "hub" ? await getHubAnalytics(channel, 7) : null;
  const configured = !!process.env.GITHUB_TOKEN;
  if (sp.platform === "hub") return <div className="space-y-5"><PageHeader title="Overview" blurb="Hub activity over the last 7 days." /><HubAnalytics data={hub} /></div>;
  return (
    <div className="space-y-6 home-stack">
      <div className="mobile-today">
        <h1 className="text-xl font-semibold mb-4">Today</h1>
        <div className="grid grid-cols-2 gap-3">
          {[
            ["Views · 7d", analytics.total.views.toLocaleString()],
            ["Likes · 7d", analytics.total.likes.toLocaleString()],
            ["Pending replies", ov.pending.length],
            [
              "Month / budget",
              `${fmtUsd(ov.costs.mtd)} / ${fmtUsd(ov.costs.budget)}`,
            ],
          ].map(([label, value]) => (
            <div className="card" key={label}>
              <p className="text-sm text-muted">{label}</p>
              <p className="stat-value mt-2">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="home-title">
        <PageHeader
          title="Overview"
          action={
            owner && (
              <div className="flex gap-2">
                <ActionButton
                  action="sync"
                  label="Sync now"
                  configured={configured}
                />
                <ActionButton
                  action="engage"
                  label="Reply now"
                  configured={configured}
                />
              </div>
            )
          }
        />
      </div>
      <div className="desktop-home-stats grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ["Views · 7d", analytics.total.views],
          ["Likes · 7d", analytics.total.likes],
          ["Comments · 7d", analytics.total.comments],
          [sp.platform === "instagram" || sp.platform === "facebook" ? "Reels · 7d" : "Uploads · 7d", ov.publishedWeek],
          ["Posts / day · 7d", (ov.publishedWeek / 7).toFixed(1)],
          ["Queued uploads", ov.queuedUploads.length],
          ["Pending replies", ov.pending.length],
          ["Month spend", fmtUsd(ov.costs.mtd)],
          ...(hub && hub.total.views > 0
            ? [
                ["Hub views · 7d", hub.total.views],
                ["Hub YouTube click-throughs · 7d", hub.total.youtube],
              ]
            : []),
        ].map(([label, value]) => (
          <div className="card" key={label}>
            <div className="text-xs text-muted">{label}</div>
            <div className="stat-value text-right mt-2">{value}</div>
            {label === "Queued uploads" && (
              <p className="text-xs text-muted mt-2">
                Waiting for upload quota · {ov.queue.count} topics ready
              </p>
            )}
          </div>
        ))}
      </div>
      <Section title="Views over the last 7 days">
        <SeriesReport
          name="overview-channels"
          dates={analytics.daily.map((d) => d.date)}
          columns={[{ key: "views", label: "Views", share: true }]}
          rows={analytics.channels.map((c) => ({
            id: c.name,
            title: CHANNELS.find((m) => m.key === c.name)?.short ?? c.name,
            daily: c.daily,
            values: { views: c.views },
          }))}
        />
      </Section>
      {
        <details className="card attention">
          <summary className="cursor-pointer min-h-11 flex items-center">
            Needs attention{" "}
            <span
              className={`badge ${attention ? "badge-alert" : "badge-ok"} ml-2`}
            >
              {attention}
            </span>
          </summary>
          <div className="space-y-2 pt-3">
            {!attention && (
              <p className="text-muted">Everything looks clear.</p>
            )}
            {ov.paused && <p className="text-warn-fg">Pipeline paused</p>}
            {ov.failedRun && (
              <Link href="/costs" className="text-alert-fg">
                Latest run failed · View log
              </Link>
            )}
            {ov.failedPubs.map((p) => (
              <p key={p.id} className="text-alert-fg">
                {p.title}: {p.platform} upload failed
              </p>
            ))}
            {ov.failedContent.map((c) => (
              <p key={c.id} className="text-alert-fg">
                {c.title}: production or QA failed
              </p>
            ))}
            {ov.costs.pct >= 80 && (
              <p className="text-warn-fg">
                Budget {ov.costs.pct.toFixed(0)}% used
              </p>
            )}
          </div>
        </details>
      }
      <div className="home-pipeline">
        <Section title="Pipeline queue">
          {!ov.queuedUploads.length && (
            <p className="text-sm text-muted">
              No queued uploads. Uploads awaiting quota will appear here.
            </p>
          )}
          {ov.queuedUploads.map((p) => (
            <p key={p.id} className="text-sm text-muted">
              {p.title} · {p.platform} · Queued
              {p.error ? ` (last attempt: ${p.error.slice(0, 120)})` : ""}
            </p>
          ))}
        </Section>
      </div>
      <Section title="Channels">
        <div className="home-channels divide-y divide-border">
          {CHANNELS.filter((c) => channel === "all" || channel === c.key).map(
            (c) => {
              const h = ov.health.find((h) => h.key === c.key);
              return (
                <div
                  key={c.key}
                  className="flex flex-wrap items-center gap-3 py-3"
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: c.brand.fg }}
                  />
                  <div className="min-w-0 flex-1">
                    <b>{c.name}</b>
                    <div className="text-xs text-muted">
                      {c.schedule} ·{" "}
                      {h?.lastContentAt
                        ? fmtDate(h.lastContentAt)
                        : "No content yet"}
                    </div>
                  </div>
                  {h?.level === "alert" && (
                    <span className="badge badge-alert">Failed</span>
                  )}
                  {h?.level === "warn" && (
                    <span className="badge badge-warn">Check channel</span>
                  )}
                  <span className="text-xs tabular-nums">
                    {h?.queued ?? 0} queued
                  </span>
                  {owner && (
                    <div className="flex flex-wrap gap-2">
                      <ActionButton
                        action="produce"
                        label="Produce now"
                        channel={c.key}
                        configured={configured}
                      />
                      <ActionButton
                        action="shorts"
                        label="Daily Short now"
                        channel={c.key}
                        configured={configured}
                      />
                    </div>
                  )}
                </div>
              );
            },
          )}
        </div>
      </Section>
      <Section
        title="Recent content"
        action={
          <Link className="btn" href={`/content?${new URLSearchParams({ channel, ...(sp.platform ? { platform: sp.platform } : {}) })}`}>
            All content
          </Link>
        }
      >
        <ContentFilters sp={sp} channel={channel} path="/" />
        <ContentList
          items={filterContent(items, sp)}
          sort={sp.sort ?? "newest"}
          limit={12}
        />
      </Section>
    </div>
  );
}
