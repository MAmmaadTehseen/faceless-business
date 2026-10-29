"use client";
import { useState } from "react";
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
  const abnormal =
    c.status === "failed" ||
    c.qa_status === "failed" ||
    ps.some((p) => p.status === "failed")
      ? "failed"
      : ps.some(
            (p) =>
              p.privacy === "scheduled" ||
              (p.publish_at && Date.parse(p.publish_at) > Date.now()),
          )
        ? `scheduled for ${fmtDate(ps.find((p) => p.publish_at)?.publish_at ?? null)}`
        : c.status === "queued" || ps.some((p) => p.status === "queued")
          ? "queued"
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
          <span>{fmtDate(c.created_at)}</span>
          {["youtube", "instagram", "facebook"].map((platform) => {
            const p = ps.find((p) => p.platform === platform);
            return (
              <PlatformIcon
                key={platform}
                platform={platform}
                url={p?.url}
                active={!!p?.url && ["published", "live"].includes(p.status)}
                locked={!!p && p.privacy !== "public"}
              />
            );
          })}
          {abnormal && (
            <span
              className={`badge ${abnormal === "failed" ? "badge-alert" : "badge-warn"}`}
            >
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
                    ? `${(value / available.length).toFixed(1)}%`
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
function Group({ c, kids }: { c: ContentItem; kids: ContentItem[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-border last:border-0 py-3">
      <Row c={c} />
      {kids.length > 0 && (
        <div className="mt-2 sm:ml-28">
          <button
            className="text-xs text-accent-fg"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? "▾" : "▸"} {kids.length} Shorts ·{" "}
            {fmtNum(kids.reduce((n, k) => n + views(k), 0))} views
          </button>
          {open && kids.map((k) => <Row key={k.id} c={k} compact />)}
        </div>
      )}
    </div>
  );
}
export function ContentList({
  items,
  limit = Number.POSITIVE_INFINITY,
}: {
  items: ContentItem[];
  limit?: number;
}) {
  const ids = new Set(items.map((c) => c.id));
  const roots = items.filter((c) => !c.parent_id || !ids.has(c.parent_id));
  return (
    <div>
      {!items.length && <p className="text-sm text-muted">No content.</p>}
      {roots.slice(0, limit).map((c) => (
        <Group
          key={c.id}
          c={c}
          kids={items.filter((k) => k.parent_id === c.id)}
        />
      ))}
    </div>
  );
}
