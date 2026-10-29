"use client";
import { Fragment } from "react";
import { metric } from "@/lib/content-filters";
import { category } from "@/lib/categories";
import { RelativeTime } from "./RelativeTime";
import type { ContentItem } from "@/lib/content-data";
import { channelMeta } from "@/lib/channels";
import { PlatformIcon } from "./PlatformIcon";
import { fmtDate, fmtNum } from "@/lib/format";
export function views(c: ContentItem) {
  return c.publications.reduce((n, p) => n + (p.metric?.views ?? 0), 0);
}
function Row({ c, compact = false }: { c: ContentItem; compact?: boolean }) {
  const m = channelMeta(c.channel);
  const ps = c.publications;
  const scheduled = ps.find(
    (p) =>
      p.status === "scheduled" ||
      p.privacy === "scheduled" ||
      (p.publish_at && Date.parse(p.publish_at) > Date.now()),
  );
  const abnormal =
    c.status === "failed" ||
    c.qa_status === "failed" ||
    ps.some((p) => p.status === "failed")
      ? "failed"
      : c.status === "queued" || ps.some((p) => p.status === "queued")
        ? "queued"
        : scheduled
          ? scheduled.publish_at
            ? `scheduled for ${fmtDate(scheduled.publish_at)}`
            : "scheduled"
          : !["published", "live", "rendered"].includes(c.status)
            ? c.status
            : "";
  return (
    <div className="content-row">
      {!compact &&
        (/^https?:\/\//.test(c.thumbnail_path ?? "") ? (
          <img className="content-thumb" src={c.thumbnail_path!} alt="" />
        ) : (
          <div
            className="content-thumb grid place-items-center"
            style={{ background: m?.brand.bg, color: m?.brand.fg }}
          >
            ▶
          </div>
        ))}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            title={m?.name}
            style={{ background: m?.brand.fg }}
          />
          <span className="font-medium break-words">{c.title}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
          <RelativeTime value={c.created_at} />
          <span className="badge">{category(c)}</span>
          {["youtube", "instagram", "facebook"].map((platform) => {
            const p = ps.find((p) => p.platform === platform);
            return (
              <PlatformIcon
                key={platform}
                platform={platform}
                url={p?.url}
                active={!!p?.url && ["published", "live"].includes(p.status)}
                locked={
                  !!p &&
                  (p.privacy !== "public" ||
                    (!!p.publish_at && Date.parse(p.publish_at) > Date.now()))
                }
              />
            );
          })}
          {abnormal && (
            <span
              className={`badge ${abnormal === "failed" ? "badge-alert" : abnormal.startsWith("scheduled") ? "badge-accent" : ""}`}
            >
              {abnormal === "queued" && (
                <svg
                  aria-hidden
                  width="12"
                  height="12"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                >
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 4v4l3 2" />
                </svg>
              )}
              {abnormal}
            </span>
          )}
        </div>
      </div>
      <div className="metric-chips">
        {(["views", "likes", "comments", "ctr"] as const).map((k) => {
          const available = ps.filter((p) => p.metric?.[k] != null);
          const value = available.reduce((n, p) => n + (p.metric?.[k] ?? 0), 0);
          return (
            <span
              key={k}
              title={ps
                .map((p) => `${p.platform}: ${p.metric?.[k] ?? "—"}`)
                .join("\n")}
              className="text-right tabular-nums font-mono text-xs"
            >
              <b>
                {k === "ctr"
                  ? available.length
                    ? metric(c, "watch") >= 0
                      ? `${metric(c, "watch").toFixed(1)}%`
                      : "—"
                    : "—"
                  : fmtNum(value)}
              </b>
              <span className="ml-1 text-muted">
                {k === "ctr" ? "watch" : k}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
export function ContentList({
  items,
  limit = Infinity,
  groupByDay = false,
}: {
  items: ContentItem[];
  limit?: number;
  groupByDay?: boolean;
}) {
  const shown = items.slice(0, limit);
  const groups = new Map<string, ContentItem[]>();
  for (const c of shown) {
    const day = groupByDay ? c.created_at.slice(0, 10) : "";
    groups.set(day, [...(groups.get(day) ?? []), c]);
  }
  return (
    <div>
      {!shown.length && (
        <p className="text-sm text-muted">
          No matching content. Clear filters or widen the date range.
        </p>
      )}
      {[...groups].map(([day, rows]) => (
        <Fragment key={day}>
          {day && <h3 className="day-header">{day} UTC</h3>}
          {rows.map((c) => (
            <div
              key={c.id}
              className="border-b border-border py-3 last:border-0"
            >
              <Row c={c} />
            </div>
          ))}
        </Fragment>
      ))}
    </div>
  );
}
