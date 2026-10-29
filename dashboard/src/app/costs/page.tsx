import Link from "next/link";
import { db } from "@/lib/supabase";
import { getSettings } from "@/lib/data";
import { Cost, Run } from "@/lib/types";
import { fmtDate, fmtUsd } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { CHANNELS, channelMeta } from "@/lib/channels";
import { ChannelBadge, ChannelDot } from "@/components/ChannelBadge";

export default async function CostsPage() {
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const daysElapsed = now.getDate();
  const channel = await getChannelFilter();
  const all = channel === "all";

  let costsQ = db().from("costs").select("id,at,step,channel,content_id,model,usd").gte("at", monthStart.toISOString()).limit(5000);
  let contentQ = db().from("content").select("id,channel,title,kind,claude_cost_usd,created_at").order("created_at", { ascending: false }).limit(30);
  let runsQ = db().from("runs").select("*").order("started_at", { ascending: false }).limit(20);
  if (!all) {
    costsQ = costsQ.eq("channel", channel);
    contentQ = contentQ.eq("channel", channel);
    runsQ = runsQ.eq("channel", channel);
  }
  const [settings, costsRes, contentRes, runsRes] = await Promise.all([
    getSettings().catch(() => null), costsQ, contentQ, runsQ,
  ]);
  if (costsRes.error) return <p className="text-red-500">DB error: {costsRes.error.message}</p>;

  const costs = (costsRes.data ?? []) as Cost[];
  const mtd = costs.reduce((a, c) => a + (c.usd ?? 0), 0);
  const projected = daysElapsed > 0 ? (mtd / daysElapsed) * daysInMonth : 0;
  const budget = settings?.monthly_budget_usd ?? 0;
  const pct = budget > 0 ? Math.min(100, (mtd / budget) * 100) : 0;

  const bySteps = new Map<string, { usd: number; n: number }>();
  for (const c of costs) {
    const e = bySteps.get(c.step) ?? { usd: 0, n: 0 };
    e.usd += c.usd ?? 0; e.n += 1;
    bySteps.set(c.step, e);
  }
  const steps = [...bySteps.entries()].sort((a, b) => b[1].usd - a[1].usd);

  // Per-channel subtotals (only shown when viewing all channels). Null channel = legacy rows.
  const byChannel = new Map<string, { usd: number; n: number }>();
  for (const c of costs) {
    const k = c.channel ?? "";
    const e = byChannel.get(k) ?? { usd: 0, n: 0 };
    e.usd += c.usd ?? 0; e.n += 1;
    byChannel.set(k, e);
  }
  const channelRows = [
    ...CHANNELS.map((m) => ({ key: m.key, meta: m, ...(byChannel.get(m.key) ?? { usd: 0, n: 0 }) })),
    ...[...byChannel.entries()].filter(([k]) => !channelMeta(k)).map(([k, e]) => ({ key: k || "(unassigned)", meta: null, ...e })),
  ];

  // Per-content cost: sum from costs table for last 30 content rows, fall back to content.claude_cost_usd.
  const recent = (contentRes.data ?? []) as { id: string; channel: string; title: string; kind: string; claude_cost_usd: number | null; created_at: string }[];
  const ids = recent.map((c) => c.id);
  const perContent = new Map<string, number>();
  if (ids.length) {
    const { data } = await db().from("costs").select("content_id,usd").in("content_id", ids).limit(10000);
    for (const r of data ?? []) if (r.content_id) perContent.set(r.content_id, (perContent.get(r.content_id) ?? 0) + (r.usd ?? 0));
  }
  const runs = (runsRes.data ?? []) as Run[];

  return (
    <div className="space-y-4">
      <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
        Costs {!all && <ChannelBadge channel={channel} />}
      </h1>

      <section className="card space-y-2">
        <div className="grid grid-cols-3 gap-2 text-center">
          <Stat label="Month to date" value={fmtUsd(mtd)} />
          <Stat label="Projected" value={fmtUsd(projected)} warn={budget > 0 && projected > budget} />
          <Stat label="Budget" value={budget ? fmtUsd(budget) : "-"} />
        </div>
        <div className="h-2 w-full overflow-hidden rounded bg-border">
          <div className={`h-full ${pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-green-500"}`} style={{ width: `${pct}%` }} />
        </div>
        <p className="text-xs text-muted">
          {pct.toFixed(0)}% of budget used, day {daysElapsed} of {daysInMonth}.{" "}
          <Link href="/automation" className="underline">Change budget</Link>
        </p>
      </section>

      {all && (
        <section className="card">
          <h2 className="mb-2 font-medium">By channel (this month)</h2>
          <table className="w-full text-sm">
            <tbody>
              {channelRows.map((r) => (
                <tr key={r.key} className="border-t border-border">
                  <td className="py-1">
                    <span className="inline-flex items-center gap-1.5">
                      {r.meta && <ChannelDot meta={r.meta} />}
                      {r.meta?.name ?? r.key}
                    </span>
                  </td>
                  <td className="py-1 text-right text-muted">{r.n} calls</td>
                  <td className="py-1 text-right">{fmtUsd(r.usd)}</td>
                </tr>
              ))}
              <tr className="border-t border-border font-medium">
                <td className="py-1">Total</td>
                <td />
                <td className="py-1 text-right">{fmtUsd(mtd)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      <section className="card">
        <h2 className="mb-2 font-medium">By step (this month)</h2>
        {steps.length === 0 && <p className="text-sm text-muted">No costs this month.</p>}
        <table className="w-full text-sm">
          <tbody>
            {steps.map(([step, e]) => (
              <tr key={step} className="border-t border-border">
                <td className="py-1">{step}</td>
                <td className="py-1 text-right text-muted">{e.n} calls</td>
                <td className="py-1 text-right">{fmtUsd(e.usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="mb-2 font-medium">Per content (last 30)</h2>
        {recent.length === 0 && <p className="text-sm text-muted">No content yet.</p>}
        <table className="w-full text-sm">
          <tbody>
            {recent.map((c) => (
              <tr key={c.id} className="border-t border-border">
                <td className="py-1 pr-2">
                  {all && <span className="mr-1"><ChannelBadge channel={c.channel} /></span>}
                  <span className="badge mr-1 uppercase">{c.kind}</span>
                  <span className="line-clamp-1">{c.title}</span>
                  <span className="text-xs text-muted">{fmtDate(c.created_at)}</span>
                </td>
                <td className="py-1 text-right align-top">{fmtUsd(perContent.get(c.id) ?? c.claude_cost_usd ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2 className="mb-2 font-medium">Last 20 runs</h2>
        {runs.length === 0 && <p className="text-sm text-muted">No runs yet.</p>}
        <ul className="divide-y divide-border text-sm">
          {runs.map((r) => (
            <li key={r.id} className="py-1.5">
              <div className="flex flex-wrap items-center gap-x-2">
                <span className={`badge ${r.status === "failed" ? "border-red-500/60 text-red-500" : r.status === "ok" || r.status === "success" ? "text-green-600 dark:text-green-400" : ""}`}>{r.status ?? "?"}</span>
                <span className="font-medium">{r.workflow ?? "run"}</span>
                {all && <ChannelBadge channel={r.channel} />}
                <span className="text-xs text-muted">{fmtDate(r.started_at)}{r.finished_at ? ` → ${fmtDate(r.finished_at)}` : ""}</span>
              </div>
              {r.log && (
                <details className="mt-0.5 text-xs text-muted">
                  <summary className="cursor-pointer">log</summary>
                  <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words">{r.log}</pre>
                </details>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-lg font-semibold ${warn ? "text-red-500" : ""}`}>{value}</div>
    </div>
  );
}
