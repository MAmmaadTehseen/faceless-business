"use client";
import { useId, useState } from "react";
import { seriesColor } from "@/lib/palette";

export type ReportColumn = {
  key: string;
  label: string;
  format?: "number" | "percent" | "usd" | "date";
  share?: boolean;
};
export type ReportRow = {
  id: string;
  title: string;
  status?: string;
  subtitle?: string;
  links?: { label: string; href: string }[];
  color?: string;
  href?: string;
  thumbnail?: string | null;
  duration?: number | null;
  values: Record<string, number | null>;
  daily?: number[];
};
const axisNumber = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 0,
});
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
function display(value: number | null, format?: ReportColumn["format"]) {
  return value == null
    ? "—"
    : format === "date"
      ? new Date(value).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          timeZone: "UTC",
        })
      : format === "usd"
        ? `$${value.toFixed(2)}`
        : format === "percent"
          ? `${value.toFixed(1)}%`
          : number.format(value);
}
function csvCell(value: unknown) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}
export function SeriesReport({
  rows,
  columns,
  dates = [],
  name = "report",
  chart = true,
  initialSort,
  initialDescending = true,
}: {
  rows: ReportRow[];
  columns: ReportColumn[];
  dates?: string[];
  name?: string;
  chart?: boolean;
  initialSort?: string;
  initialDescending?: boolean;
}) {
  const id = useId();
  const [excluded, setExcluded] = useState<string[]>([]);
  const [show, setShow] = useState(true);
  const [sort, setSort] = useState(initialSort ?? columns[0]?.key ?? "title");
  const [descending, setDescending] = useState(initialDescending);
  const [hover, setHover] = useState<number | null>(null);
  const colored = rows.map((r, i) => ({
    ...r,
    color: r.color ?? seriesColor(r.id, i),
  }));
  const selected = colored.filter((r) => !excluded.includes(r.id));
  const sorted = [...colored].sort(
    (a, b) =>
      (sort === "title"
        ? a.title.localeCompare(b.title)
        : (a.values[sort] ?? -Infinity) - (b.values[sort] ?? -Infinity)) *
      (descending ? -1 : 1),
  );
  const totals = Object.fromEntries(
    columns.map((c) => [
      c.key,
      rows.reduce((n, r) => n + (r.values[c.key] ?? 0), 0),
    ]),
  );
  const hasChart =
    chart && dates.length > 0 && rows.some((r) => r.daily !== undefined);
  const max = Math.max(1, ...selected.flatMap((r) => r.daily ?? []));
  const x = (i: number) => 56 + (i * 888) / Math.max(1, dates.length - 1);
  const y = (v: number) => 210 - (v / max) * 174;
  function order(key: string) {
    if (sort === key) setDescending(!descending);
    else {
      setSort(key);
      setDescending(key !== "title");
    }
  }
  function download() {
    const csv = [
      ["Title", ...columns.map((c) => c.label)],
      ...sorted.map((r) => [
        r.title,
        ...columns.map((c) =>
          c.format === "date" && r.values[c.key] != null
            ? new Date(r.values[c.key]!).toISOString().slice(0, 10)
            : r.values[c.key],
        ),
      ]),
    ]
      .map((r) => r.map(csvCell).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8;" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="series-report space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {hasChart && (
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={show}
              onChange={(e) => setShow(e.target.checked)}
              aria-controls={id}
            />
            Show chart
          </label>
        )}
        <button className="btn" onClick={download} disabled={!rows.length}>
          Download CSV
        </button>
      </div>
      {hasChart && show && (
        <div
          id={id}
          className="report-chart"
          onMouseLeave={() => setHover(null)}
        >
          {!selected.length ? (
            <p className="text-muted p-6">
              Select a series below to show the chart.
            </p>
          ) : (
            <>
              {!selected.some((r) => r.daily?.some((v) => v > 0)) && (
                <p className="text-sm text-muted mb-3">
                  No activity recorded for this period.
                </p>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted">
                {selected.map((r) => (
                  <span key={r.id} className="inline-flex items-center gap-2">
                    <i className="series-dot" style={{ background: r.color }} />
                    {r.title}
                  </span>
                ))}
              </div>
              <svg
                viewBox="0 0 1000 254"
                role="img"
                aria-label={`${name}: daily values`}
                className="w-full"
                onMouseMove={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  setHover(
                    Math.max(
                      0,
                      Math.min(
                        dates.length - 1,
                        Math.round(
                          ((((e.clientX - rect.left) / rect.width) * 1000 -
                            56) /
                            888) *
                            (dates.length - 1),
                        ),
                      ),
                    ),
                  );
                }}
              >
                {[0, 0.5, 1].map((f) => (
                  <g key={f}>
                    <line
                      x1="56"
                      x2="944"
                      y1={y(max * f)}
                      y2={y(max * f)}
                      stroke="var(--border)"
                    />
                    <text
                      x="45"
                      y={y(max * f) + 4}
                      textAnchor="end"
                      fill="var(--muted)"
                      fontSize="13"
                    >
                      {axisNumber.format(max * f)}
                    </text>
                  </g>
                ))}
                {selected.map((r) => (
                  <g key={r.id}>
                    <polyline
                      points={dates
                        .map((_, i) => `${x(i)},${y(r.daily?.[i] ?? 0)}`)
                        .join(" ")}
                      fill="none"
                      stroke={r.color}
                      strokeWidth="2.5"
                      vectorEffect="non-scaling-stroke"
                    />
                    {dates.length === 1 && (
                      <circle
                        cx={x(0)}
                        cy={y(r.daily?.[0] ?? 0)}
                        r="4"
                        fill={r.color}
                      />
                    )}
                  </g>
                ))}
                {hover !== null && (
                  <g>
                    <line
                      x1={x(hover)}
                      x2={x(hover)}
                      y1="30"
                      y2="210"
                      stroke="var(--muted)"
                      strokeDasharray="4 4"
                    />
                    {selected.map((r) => (
                      <circle
                        key={r.id}
                        cx={x(hover)}
                        cy={y(r.daily?.[hover] ?? 0)}
                        r="4"
                        fill={r.color}
                        stroke="var(--card)"
                        strokeWidth="2"
                      />
                    ))}
                  </g>
                )}
                <text x="56" y="242" fill="var(--muted)" fontSize="13">
                  {dates[0]}
                </text>
                <text
                  x="944"
                  y="242"
                  textAnchor="end"
                  fill="var(--muted)"
                  fontSize="13"
                >
                  {dates.at(-1)}
                </text>
              </svg>
              {hover !== null && (
                <div
                  className="chart-tooltip"
                  style={{
                    left: hover > dates.length / 2 ? "auto" : "8%",
                    right: hover > dates.length / 2 ? "4%" : "auto",
                  }}
                >
                  <p className="font-medium mb-2">{dates[hover]}</p>
                  {[...selected]
                    .sort(
                      (a, b) =>
                        (b.daily?.[hover] ?? 0) - (a.daily?.[hover] ?? 0),
                    )
                    .map((r) => (
                      <div key={r.id} className="flex items-center gap-2 py-1">
                        <i
                          className="series-dot"
                          style={{ background: r.color }}
                        />
                        <span className="flex-1">{r.title}</span>
                        <b className="tabular-nums">
                          {number.format(r.daily?.[hover] ?? 0)}
                        </b>
                      </div>
                    ))}
                </div>
              )}
              <label className="chart-date-control text-xs text-muted">
                Inspect date{" "}
                <input
                  type="range"
                  min="0"
                  max={dates.length - 1}
                  value={hover ?? 0}
                  onChange={(e) => setHover(Number(e.target.value))}
                  aria-label="Inspect chart date"
                  aria-valuetext={`${dates[hover ?? 0]}: ${selected.map((r) => `${r.title} ${number.format(r.daily?.[hover ?? 0] ?? 0)}`).join(", ")}`}
                />
              </label>
            </>
          )}
        </div>
      )}
      {!rows.length ? (
        <p className="text-sm text-muted py-6">
          No data for this period. Widen the date range or sync published
          content.
        </p>
      ) : (
        <table className="report-table w-full text-sm">
          <thead>
            <tr>
              <th
                className="text-left"
                aria-sort={
                  sort === "title"
                    ? descending
                      ? "descending"
                      : "ascending"
                    : "none"
                }
              >
                <button onClick={() => order("title")}>
                  Content / source{" "}
                  {sort === "title" ? (descending ? "↓" : "↑") : ""}
                </button>
              </th>
              {columns.map((c) => (
                <th
                  className="text-right"
                  key={c.key}
                  aria-sort={
                    sort === c.key
                      ? descending
                        ? "descending"
                        : "ascending"
                      : "none"
                  }
                >
                  <button onClick={() => order(c.key)}>
                    {c.label} {sort === c.key ? (descending ? "↓" : "↑") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.id} style={{ borderLeft: `3px solid ${r.color}` }}>
                <td>
                  <div className="report-title">
                    {hasChart && (
                      <input
                        type="checkbox"
                        checked={!excluded.includes(r.id)}
                        onChange={(e) =>
                          setExcluded(
                            e.target.checked
                              ? excluded.filter((k) => k !== r.id)
                              : [...excluded, r.id],
                          )
                        }
                        aria-label={`Include ${r.title} in chart`}
                      />
                    )}
                    {r.thumbnail && (
                      <div className="report-thumbnail">
                        <img src={r.thumbnail} alt="" />
                        {r.duration != null && (
                          <span>
                            {Math.floor(r.duration / 60)}:
                            {String(Math.floor(r.duration % 60)).padStart(
                              2,
                              "0",
                            )}
                          </span>
                        )}
                      </div>
                    )}
                    <div>
                      {r.href ? (
                        <a
                          href={r.href}
                          className="text-accent-fg hover:underline"
                        >
                          {r.title}
                        </a>
                      ) : (
                        <span>{r.title}</span>
                      )}
                      {r.status && (
                        <span
                          className={`badge ml-2 ${r.status.includes("failed") ? "badge-alert" : /queued|scheduled/.test(r.status) ? "badge-warn" : ""}`}
                        >
                          {r.status}
                        </span>
                      )}
                      {r.subtitle && (
                        <p className="text-xs text-muted mt-1">{r.subtitle}</p>
                      )}
                      {r.links && (
                        <div className="flex flex-wrap gap-3 mt-1 text-xs text-accent-fg">
                          {r.links.map((l) => (
                            <a key={l.label} href={l.href}>
                              {l.label}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </td>
                {columns.map((c) => (
                  <td
                    key={c.key}
                    data-label={c.label}
                    className="text-right tabular-nums"
                  >
                    <span>
                      {display(r.values[c.key], c.format)}
                      {c.share && (
                        <small className="text-muted ml-3">
                          {totals[c.key]
                            ? (
                                ((r.values[c.key] ?? 0) / totals[c.key]) *
                                100
                              ).toFixed(1)
                            : "0.0"}
                          %
                        </small>
                      )}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
