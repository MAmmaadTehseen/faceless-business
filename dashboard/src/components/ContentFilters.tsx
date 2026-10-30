"use client";
import { FilterSheet } from "./FilterSheet";
import Link from "next/link";
import { CHANNELS } from "@/lib/channels";
import { categories } from "@/lib/categories";
import { Filters, sorts } from "@/lib/content-filters";
export function ContentFilters({
  sp,
  channel,
  path,
  defaultSort = "newest",
  analytics = false,
}: {
  sp: Filters;
  channel: string;
  path: string;
  defaultSort?: string;
  analytics?: boolean;
}) {
  const fields = [
    [
      "channel",
      "Channel",
      [["all", "All channels"], ...CHANNELS.map((c) => [c.key, c.short])],
    ],
    [
      "kind",
      "Type",
      [
        ["", "All types"],
        ["long", "Long"],
        ["derived", "Short from video"],
        ["daily", "Daily standalone Short"],
        ["short", "All Shorts"],
      ],
    ],
    [
      "platform",
      "Platform",
      [
        ["", "All platforms"],
        ...["youtube", "instagram", "facebook"].map((v) => [v, v]),
      ],
    ],
    [
      "status",
      "Status",
      [
        ["", "All statuses"],
        ...["scheduled", "live", "queued", "failed", "private", "public"].map(
          (v) => [v, v],
        ),
      ],
    ],
    [
      "category",
      "Category",
      [["", "All categories"], ...categories.map((v) => [v, v])],
    ],
    [
      "days",
      "Date range",
      [
        ["7", "7 days"],
        ["28", "28 days"],
        ["90", "90 days"],
        ["all", "All time"],
      ],
    ],
    ["sort", "Sort", Object.entries(sorts)],
  ] as [string, string, string[][]][];
  const count = [
    !!sp.q?.trim(),
    channel !== "all",
    !!sp.kind,
    !!sp.platform,
    !!sp.status && sp.status !== "all",
    !!sp.category,
    !!sp.days && sp.days !== "all",
  ].filter(Boolean).length;
  return (
    <FilterSheet count={count}><form
      key={JSON.stringify(sp) + channel}
      action={path}
      className="filter-bar"
      aria-label="Content filters"
    >
      {analytics && (
        <input type="hidden" name="tab" value={sp.tab ?? "overview"} />
      )}
      <input
        name="q"
        aria-label="Search title or topic"
        placeholder="Search title or topic…"
        defaultValue={sp.q ?? ""}
      />
      {fields.map(([name, label, options]) => (
        <select
          key={name}
          name={name}
          aria-label={label}
          defaultValue={
            sp[name] ??
            (name === "channel"
              ? channel
              : name === "sort"
                ? defaultSort
                : name === "days"
                  ? analytics
                    ? "28"
                    : "all"
                  : "")
          }
        >
          {options.map(([v, t]) => (
            <option key={v} value={v}>
              {t}
            </option>
          ))}
        </select>
      ))}
      <button className="btn">Apply</button>
      <span className="badge" aria-live="polite">
        {count} active
      </span>
      <Link
        className="badge"
        href={`${path}?channel=all${analytics ? "&tab=" + (sp.tab ?? "overview") : ""}`}
      >
        Clear
      </Link>
    </form></FilterSheet>
  );
}
