import { AutoFilters } from "@/components/AutoFilters";
import { parseChannelFilter } from "@/lib/channels";
import { SeriesReport } from "@/components/SeriesReport";
import { Section } from "@/components/Section";
import Link from "next/link";
import { db } from "@/lib/supabase";
import { getSettings } from "@/lib/data";
import { Cost, Run } from "@/lib/types";
import { fmtDate, fmtUsd } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { CHANNELS, channelMeta } from "@/lib/channels";
import { ChannelBadge } from "@/components/ChannelBadge";
import { PageHeader } from "@/components/PageHeader";

export default async function CostsPage({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const sp = await searchParams;
  const days = sp.days ?? "month";
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const daysInMonth = new Date(
    now.getFullYear(),
    now.getMonth() + 1,
    0,
  ).getDate();
  const daysElapsed = now.getDate();
  const channel = parseChannelFilter(sp.channel);
  const all = channel === "all";

  let costsQ = db()
    .from("costs")
    .select("id,at,step,channel,content_id,model,usd")

    .limit(5000);
  let contentQ = db()
    .from("content")
    .select("id,channel,title,kind,claude_cost_usd,created_at")
    .order("created_at", { ascending: false })
    .limit(30);
  let runsQ = db()
    .from("runs")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(20);
  const cutoff = days === "all" ? null : days === "month" ? monthStart.toISOString() : new Date(Date.now() - ([1,7,30].includes(Number(days)) ? Number(days) : 30) * 86400000).toISOString();
  if (cutoff) { costsQ = costsQ.gte("at", cutoff); contentQ = contentQ.gte("created_at", cutoff); runsQ = runsQ.gte("started_at", cutoff); }
  if (!all) {
    costsQ = costsQ.eq("channel", channel);
    contentQ = contentQ.eq("channel", channel);
    runsQ = runsQ.eq("channel", channel);
  }
  const [settings, costsRes, contentRes, runsRes] = await Promise.all([
    getSettings().catch(() => null),
    costsQ,
    contentQ,
    runsQ,
  ]);
  if (costsRes.error)
    return <p className="text-alert-fg">DB error: {costsRes.error.message}</p>;

  const costs = (costsRes.data ?? []) as Cost[];
  const mtd = costs.reduce((a, c) => a + (c.usd ?? 0), 0);
  const monthly = days === "month" ? mtd : (await db().from("costs").select("usd,channel").gte("at", monthStart.toISOString())).data?.filter(c => all || c.channel === channel).reduce((n,c) => n + (c.usd ?? 0), 0) ?? 0;
  const projected = daysElapsed > 0 ? (monthly / daysElapsed) * daysInMonth : 0;
  const budget = settings?.monthly_budget_usd ?? 0;
  const pct = budget > 0 ? Math.min(100, (monthly / budget) * 100) : 0;

  const bySteps = new Map<string, { usd: number; n: number }>();
  for (const c of costs) {
    const e = bySteps.get(c.step) ?? { usd: 0, n: 0 };
    e.usd += c.usd ?? 0;
    e.n += 1;
    bySteps.set(c.step, e);
  }
  const steps = [...bySteps.entries()].sort((a, b) => b[1].usd - a[1].usd);

  // Per-channel subtotals (only shown when viewing all channels). Null channel = legacy rows.
  const byChannel = new Map<string, { usd: number; n: number }>();
  for (const c of costs) {
    const k = c.channel ?? "";
    const e = byChannel.get(k) ?? { usd: 0, n: 0 };
    e.usd += c.usd ?? 0;
    e.n += 1;
    byChannel.set(k, e);
  }
  const channelRows = [
    ...CHANNELS.map((m) => ({
      key: m.key,
      meta: m,
      ...(byChannel.get(m.key) ?? { usd: 0, n: 0 }),
    })),
    ...[...byChannel.entries()]
      .filter(([k]) => !channelMeta(k))
      .map(([k, e]) => ({ key: k || "(unassigned)", meta: null, ...e })),
  ];

  // Per-content cost: sum from costs table for last 30 content rows, fall back to content.claude_cost_usd.
  const recent = (contentRes.data ?? []) as {
    id: string;
    channel: string;
    title: string;
    kind: string;
    claude_cost_usd: number | null;
    created_at: string;
  }[];
  const ids = recent.map((c) => c.id);
  const perContent = new Map<string, number>();
  if (ids.length) {
    let detailQuery = db()
      .from("costs")
      .select("content_id,usd")
      .in("content_id", ids)
      .limit(10000);
    if (cutoff) detailQuery = detailQuery.gte("at", cutoff);
    const { data } = await detailQuery;
    for (const r of data ?? [])
      if (r.content_id)
        perContent.set(
          r.content_id,
          (perContent.get(r.content_id) ?? 0) + (r.usd ?? 0),
        );
  }
  const runs = (runsRes.data ?? []) as Run[];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Costs"
        blurb="Claude API spend logged by every pipeline step, plus the last runs and their logs."
      >
        {!all && <ChannelBadge channel={channel} />}
      </PageHeader>

      <AutoFilters><select name="days" aria-label="Date range" defaultValue={days}>{[["1","Last 24 hours"],["7","7 days"],["30","30 days"],["all","All time"],["month","This month"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></AutoFilters>
      <section className="card space-y-3">
        <div className="grid grid-cols-3 gap-2 text-center sm:text-left">
          <Stat label={days === "month" ? "Month to date" : "Selected period"} value={fmtUsd(mtd)} />
          <Stat
            label="Projected"
            value={fmtUsd(projected)}
            warn={budget > 0 && projected > budget}
          />
          <Stat label="Budget" value={budget ? fmtUsd(budget) : "-"} />
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-card-2">
          <div
            className={`h-full rounded-full ${pct >= 90 ? "bg-alert shadow-[0_0_10px_var(--alert)]" : pct >= 70 ? "bg-warn" : "bg-accent"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-muted">
          {pct.toFixed(0)}% of budget used, day {daysElapsed} of {daysInMonth}.{" "}
          <Link href="/automation" className="text-accent-fg underline">
            Change budget
          </Link>
        </p>
      </section>

      {all && (
        <Section title="By channel (selected period)">
          <SeriesReport
            name="costs-by-channel"
            chart={false}
            columns={[
              { key: "calls", label: "Calls" },
              { key: "spend", label: "Spend", format: "usd", share: true },
            ]}
            rows={channelRows.map((r) => ({
              id: r.key,
              title: r.meta?.name ?? r.key,
              values: { calls: r.n, spend: r.usd },
            }))}
          />
        </Section>
      )}

      <Section title="By step (selected period)">
        <SeriesReport
          name="costs-by-step"
          chart={false}
          columns={[
            { key: "calls", label: "Calls" },
            { key: "spend", label: "Spend", format: "usd", share: true },
          ]}
          rows={steps.map(([step, e]) => ({
            id: step,
            title: step,
            values: { calls: e.n, spend: e.usd },
          }))}
        />
      </Section>

      <Section title="Per content (last 30)">
        <SeriesReport
          name="costs-per-content"
          chart={false}
          columns={[
            { key: "spend", label: "Spend", format: "usd", share: true },
          ]}
          rows={recent.map((c) => ({
            id: c.id,
            title: c.title,
            href: `/content?q=${encodeURIComponent(c.title)}`,
            subtitle: `${channelMeta(c.channel)?.short ?? c.channel} · ${c.kind} · ${fmtDate(c.created_at)}`,
            values: { spend: perContent.get(c.id) ?? c.claude_cost_usd ?? 0 },
          }))}
        />
      </Section>

      <Section title="Last 20 runs">
        {runs.length === 0 && (
          <p className="text-sm text-muted">No runs yet.</p>
        )}
        <ul className="divide-y divide-border text-sm">
          {runs.map((r) => (
            <li key={r.id} className="py-1.5">
              <div className="flex flex-wrap items-center gap-x-2">
                {r.status &&
                  !["ok", "success", "completed"].includes(r.status) && (
                    <span className="badge badge-alert">{r.status}</span>
                  )}
                <span className="font-medium">{r.workflow ?? "run"}</span>
                {all && <ChannelBadge channel={r.channel} />}
                <span className="text-xs text-muted">
                  {fmtDate(r.started_at)}
                  {r.finished_at ? ` → ${fmtDate(r.finished_at)}` : ""}
                </span>
              </div>
              {r.log && (
                <details className="mt-0.5 text-xs text-muted">
                  <summary className="cursor-pointer">log</summary>
                  <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words">
                    {r.log}
                  </pre>
                </details>
              )}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function Stat({
  label,
  value,
  warn,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div
        className={`stat-value text-right mt-1 ${warn ? "text-alert-fg" : ""}`}
      >
        {value}
      </div>
    </div>
  );
}
