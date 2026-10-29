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
    getOverview(channel),
    getContent(channel, true, sp.days),
    isOwner(),
  ]);
  const configured = !!process.env.GITHUB_TOKEN;
  return (
    <div className="space-y-6">
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
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ["Uploads this week", ov.publishedWeek],
          ["Queued uploads", ov.queuedUploads.length],
          ["Pending replies", ov.pending.length],
          ["Month spend", fmtUsd(ov.costs.mtd)],
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
      {(ov.paused ||
        ov.failedRun ||
        ov.failedPubs.length > 0 ||
        ov.failedContent.length > 0 ||
        ov.costs.pct >= 80) && (
        <Section title="Needs attention">
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
        </Section>
      )}
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
      <Section title="Channels">
        <div className="divide-y divide-border">
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
          <Link className="btn" href="/content">
            All content
          </Link>
        }
      >
        <ContentFilters sp={sp} channel={channel} path="/" />
        <ContentList items={filterContent(items, sp)} limit={12} />
      </Section>
    </div>
  );
}
