import Link from "next/link";
import { db } from "@/lib/supabase";
import { Content, Metric, Publication } from "@/lib/types";
import { fmtDate, fmtNum, fmtSec, fmtUsd } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { ChannelHealth, getOverview } from "@/lib/data";
import { CHANNELS, channelMeta } from "@/lib/channels";
import { ChannelBadge, ChannelDot } from "@/components/ChannelBadge";

type Search = { kind?: string; platform?: string; days?: string };

const PLATFORMS = ["youtube", "instagram", "facebook", "tiktok"];
const RECENT_LIMIT = 12;

export default async function OverviewPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const kind = sp.kind ?? "";
  const platform = sp.platform ?? "";
  const days = sp.days ?? "";
  const filtered = !!(kind || platform || days);
  const channel = await getChannelFilter();
  const showChannel = channel === "all";
  const meta = channelMeta(channel);

  const ov = await getOverview(channel);

  /* ---- Recent content (same query and nesting as before, now capped) ---- */
  let q = db().from("content").select("id,channel,kind,parent_id,topic,title,qa_status,status,claude_cost_usd,created_at")
    .order("created_at", { ascending: false }).limit(300);
  if (channel !== "all") q = q.eq("channel", channel);
  if (days) q = q.gte("created_at", new Date(Date.now() - Number(days) * 86400_000).toISOString());
  const { data: contentRows, error } = await q;
  if (error) return <p className="text-alert-fg">DB error: {error.message}</p>;
  const content = (contentRows ?? []) as Content[];

  const ids = content.map((c) => c.id);
  const { data: pubRows } = ids.length
    ? await db().from("publications").select("*").in("content_id", ids)
    : { data: [] };
  let pubs = (pubRows ?? []) as Publication[];
  if (platform) pubs = pubs.filter((p) => p.platform === platform);

  const pubIds = pubs.map((p) => p.id);
  const { data: metricRows } = pubIds.length
    ? await db().from("metrics").select("*").in("publication_id", pubIds).order("captured_at", { ascending: false })
    : { data: [] };
  const latest = new Map<number, Metric>();
  for (const m of (metricRows ?? []) as Metric[]) if (!latest.has(m.publication_id)) latest.set(m.publication_id, m);

  const pubsByContent = new Map<string, Publication[]>();
  for (const p of pubs) pubsByContent.set(p.content_id, [...(pubsByContent.get(p.content_id) ?? []), p]);

  const byId = new Set(ids);
  const children = new Map<string, Content[]>();
  const roots: Content[] = [];
  for (const c of content) {
    if (c.kind === "short" && c.parent_id && byId.has(c.parent_id)) {
      children.set(c.parent_id, [...(children.get(c.parent_id) ?? []), c]);
    } else roots.push(c);
  }
  const visible = (c: Content) => !(platform && !(pubsByContent.get(c.id)?.length));
  const matchesKind = (c: Content) => !kind || c.kind === kind;
  const rows = roots.filter((c) => {
    const kids = (children.get(c.id) ?? []).filter(matchesKind).filter(visible);
    return (matchesKind(c) && visible(c)) || kids.length > 0;
  });
  const shown = filtered ? rows : rows.slice(0, RECENT_LIMIT);

  /* ---- Needs attention ---- */
  const attention: { key: string; tone: "alert" | "warn"; text: React.ReactNode; href: string }[] = [];
  if (ov.paused) attention.push({ key: "paused", tone: "warn", href: "/automation", text: <>Pipeline is <b>paused</b>. Nothing will be produced until you resume it.</> });
  if (ov.failedRun) attention.push({ key: "run", tone: "alert", href: "/costs", text: <>Latest run <b>failed</b> ({ov.failedRun.workflow ?? "run"}, {fmtDate(ov.failedRun.started_at)}). Open the log under Costs.</> });
  for (const h of ov.health) {
    if (h.level === "alert" && h.lastRun && h.lastRun.id !== ov.failedRun?.id && (channel === "all" || channel === h.key)) {
      attention.push({ key: `run-${h.key}`, tone: "alert", href: "/costs", text: <>{channelMeta(h.key)?.name}: last run <b>failed</b> ({h.lastRun.workflow ?? "run"}, {fmtDate(h.lastRun.started_at)}).</> });
    }
  }
  for (const p of ov.failedPubs) attention.push({ key: `pub-${p.id}`, tone: "alert", href: "/", text: <>{p.platform} upload failed for <b>{p.title}</b>{p.error ? `: ${p.error}` : ""}</> });
  for (const c of ov.failedContent) attention.push({ key: `content-${c.id}`, tone: "alert", href: "/", text: <>{c.status === "failed" ? "Production" : "QA"} failed for <b>{c.title}</b> ({c.kind}).</> });
  const flagged = ov.pending.filter((c) => c.flagged).length;
  if (flagged) attention.push({ key: "flagged", tone: "alert", href: "/inbox", text: <><b>{flagged}</b> flagged comment{flagged === 1 ? "" : "s"} waiting for a human decision.</> });
  if (ov.pending.length) attention.push({ key: "pending", tone: "warn", href: "/inbox", text: <><b>{ov.pending.length}{ov.pending.length >= 50 ? "+" : ""}</b> comment{ov.pending.length === 1 ? "" : "s"} unanswered in the inbox.</> });
  if (ov.costs.budget > 0 && ov.costs.pct >= 80) attention.push({ key: "budget", tone: ov.costs.pct >= 95 ? "alert" : "warn", href: "/costs", text: <>Claude spend is at <b>{ov.costs.pct.toFixed(0)}%</b> of the monthly budget{ov.costs.projected > ov.costs.budget ? ", and projected to exceed it" : ""}.</> });
  const alerts = attention.filter((a) => a.tone === "alert").length;

  const worstHealth = ov.health.reduce<ChannelHealth["level"]>((w, h) => (h.level === "alert" || w === "alert" ? "alert" : h.level === "warn" ? "warn" : w), "ok");

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1 text-sm text-muted">
            {meta ? <>Showing <span className="text-fg">{meta.name}</span> only. {meta.schedule}.</> : "All three channels at a glance. Pick a channel in the switcher to narrow every page."}
          </p>
        </div>
        {meta && <ChannelBadge channel={channel} />}
      </header>

      {/* Stat tiles */}
      <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Published this week" value={String(ov.publishedWeek)} hint="uploads that went live, all platforms" />
        <Stat label="Queue" value={String(ov.queue.count)} hint={ov.queue.count === 0 ? "nothing to produce" : "topics ready to produce"} tone={ov.queue.count === 0 ? "alert" : undefined} href="/queue" />
        <Stat label="Inbox" value={`${ov.pending.length}${ov.pending.length >= 50 ? "+" : ""}`} hint={flagged ? `${flagged} flagged` : "comments awaiting reply"} tone={flagged ? "alert" : ov.pending.length ? "warn" : undefined} href="/inbox" />
        <Stat label="Cost this month" value={fmtUsd(ov.costs.mtd)} hint={ov.costs.budget ? `${ov.costs.pct.toFixed(0)}% of ${fmtUsd(ov.costs.budget)}` : "no budget set"} tone={ov.costs.pct >= 95 ? "alert" : ov.costs.pct >= 80 ? "warn" : undefined} href="/costs" />
        <Stat label="Channel health" value={worstHealth === "ok" ? "Healthy" : worstHealth === "warn" ? "Check" : "Failing"} hint={`${ov.health.filter((h) => h.level === "ok").length} of ${ov.health.length} channels green`} tone={worstHealth === "ok" ? "ok" : worstHealth} />
      </section>

      {/* Needs attention */}
      <Section
        title="Needs attention"
        count={attention.length}
        tone={alerts ? "alert" : attention.length ? "warn" : "ok"}
        blurb="Failures, unanswered comments and budget pressure. Clear this list and the pipeline runs itself."
      >
        {attention.length === 0 ? (
          <Empty>All clear. Nothing is failing and the inbox is answered.</Empty>
        ) : (
          <ul className="space-y-2">
            {attention.map((a) => (
              <li key={a.key}>
                <Link href={a.href} className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 text-sm transition hover:brightness-110 ${
                  a.tone === "alert" ? "border-alert/50 bg-alert-soft text-fg" : "border-warn/40 bg-warn/10 text-fg"
                }`}>
                  <span aria-hidden className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${a.tone === "alert" ? "bg-alert shadow-[0_0_8px_var(--alert)]" : "bg-warn"}`} />
                  <span className="min-w-0 flex-1">{a.text}</span>
                  <span className="text-xs text-muted">open</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Channel health */}
      {showChannel && (
        <Section title="Channels" blurb="Last run, last produced item and queued topics per channel.">
          <div className="grid gap-3 md:grid-cols-3">
            {ov.health.map((h) => {
              const m = CHANNELS.find((c) => c.key === h.key)!;
              return (
                <div key={h.key} className={`card ${h.level === "alert" ? "card-alert" : ""}`} style={{ borderTopColor: m.brand.fg, borderTopWidth: 2 }}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-2 font-medium"><ChannelDot meta={m} />{m.name}</span>
                    <span className={`badge ${h.level === "ok" ? "badge-ok" : h.level === "warn" ? "badge-warn" : "badge-alert"}`}>
                      {h.level === "ok" ? "healthy" : h.level === "warn" ? "check" : "failing"}
                    </span>
                  </div>
                  <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div><dt className="text-muted">Last run</dt><dd className="mt-0.5 font-medium">{h.lastRun ? <span className={h.lastRun.status === "failed" ? "text-alert-fg" : ""}>{h.lastRun.status ?? "?"}</span> : "none"}</dd><dd className="text-faint">{h.lastRun ? fmtDate(h.lastRun.started_at) : m.schedule}</dd></div>
                    <div><dt className="text-muted">Last item</dt><dd className="mt-0.5 font-medium">{h.lastContentAt ? fmtDate(h.lastContentAt) : "never"}</dd></div>
                    <div><dt className="text-muted">Queued</dt><dd className={`mt-0.5 font-medium ${h.queued === 0 ? "text-alert-fg" : ""}`}>{h.queued}</dd></div>
                  </dl>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Pipeline queue */}
      <Section title="Pipeline queue" count={ov.queue.count} blurb="Highest-priority topics go next. Add or reorder on the Queue page." action={<Link href="/queue" className="btn">Manage queue</Link>}>
        {ov.queue.top.length === 0 ? (
          <Empty tone="alert">Queue is empty. The next scheduled run will have nothing to produce. <Link href="/queue" className="text-accent-fg underline">Add a topic</Link>.</Empty>
        ) : (
          <ol className="divide-y divide-border">
            {ov.queue.top.map((r, i) => (
              <li key={r.id} className="flex items-center gap-3 py-2 text-sm">
                <span className="w-5 text-right font-mono text-xs text-faint">{i + 1}</span>
                {showChannel && <ChannelBadge channel={r.channel} short />}
                <span className="min-w-0 flex-1 truncate font-medium">{r.topic}</span>
                <span className="badge badge-accent">p{r.priority}</span>
                <span className="hidden text-xs text-muted sm:inline">{fmtDate(r.created_at)}</span>
              </li>
            ))}
          </ol>
        )}
      </Section>

      {/* Recent content */}
      <Section title="Recent content" blurb="Latest long videos with their Shorts nested, plus live metrics per platform."
        action={
          <form className="flex flex-wrap gap-2 text-sm">
            <select name="kind" defaultValue={kind} aria-label="Kind">
              <option value="">All kinds</option>
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
            <select name="platform" defaultValue={platform} aria-label="Platform">
              <option value="">All platforms</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select name="days" defaultValue={days} aria-label="Period">
              <option value="">All time</option>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
            </select>
            <button className="btn">Apply</button>
            {filtered && <Link href="/" className="btn">Clear</Link>}
          </form>
        }
      >
        {rows.length === 0 && <Empty>No content yet.</Empty>}
        <div className="space-y-3">
          {shown.map((c) => (
            <ContentCard key={c.id} c={c} pubs={pubsByContent} latest={latest}
              kids={(children.get(c.id) ?? []).filter(matchesKind).filter(visible)}
              dim={!(matchesKind(c) && visible(c))} showChannel={showChannel} />
          ))}
        </div>
        {!filtered && rows.length > RECENT_LIMIT && (
          <p className="mt-3 text-xs text-muted">Showing the latest {RECENT_LIMIT} of {rows.length}. <Link href="/?days=30" className="text-accent-fg underline">Filter to see more</Link>.</p>
        )}
      </Section>

      {/* Costs */}
      <Section title="Costs" blurb="Claude API spend this month against the budget guard." action={<Link href="/costs" className="btn">Cost breakdown</Link>}>
        <div className="grid grid-cols-3 gap-3 text-center sm:text-left">
          <div><div className="text-xs text-muted">Month to date</div><div className="stat-value mt-1">{fmtUsd(ov.costs.mtd)}</div></div>
          <div><div className="text-xs text-muted">Projected</div><div className={`stat-value mt-1 ${ov.costs.budget > 0 && ov.costs.projected > ov.costs.budget ? "text-alert-fg" : ""}`}>{fmtUsd(ov.costs.projected)}</div></div>
          <div><div className="text-xs text-muted">Budget</div><div className="stat-value mt-1">{ov.costs.budget ? fmtUsd(ov.costs.budget) : "-"}</div></div>
        </div>
        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-card-2">
          <div className={`h-full rounded-full ${ov.costs.pct >= 90 ? "bg-alert shadow-[0_0_10px_var(--alert)]" : ov.costs.pct >= 70 ? "bg-warn" : "bg-accent"}`} style={{ width: `${ov.costs.pct}%` }} />
        </div>
        <p className="mt-2 text-xs text-muted">{ov.costs.pct.toFixed(0)}% of budget used, day {ov.costs.daysElapsed} of {ov.costs.daysInMonth}.</p>
      </Section>
    </div>
  );
}

/* ---------- building blocks ---------- */

function Stat({ label, value, hint, tone, href }: { label: string; value: string; hint?: string; tone?: "ok" | "warn" | "alert"; href?: string }) {
  const color = tone === "alert" ? "text-alert-fg" : tone === "warn" ? "text-warn-fg" : tone === "ok" ? "text-ok-fg" : "text-fg";
  const inner = (
    <>
      <div className="text-xs text-muted">{label}</div>
      <div className={`stat-value mt-1.5 ${color}`}>{value}</div>
      {hint && <div className="mt-1 truncate text-[11px] text-faint">{hint}</div>}
    </>
  );
  const cls = `card block min-w-0 ${tone === "alert" ? "card-alert" : ""} ${href ? "transition hover:border-border-strong" : ""}`;
  return href ? <Link href={href} className={cls}>{inner}</Link> : <div className={cls}>{inner}</div>;
}

function Section({ title, blurb, count, tone, action, children }: {
  title: string; blurb?: string; count?: number; tone?: "ok" | "warn" | "alert"; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            {tone === "alert" && <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-alert shadow-[0_0_10px_var(--alert)]" />}
            <span className={tone === "alert" ? "text-alert-fg" : ""}>{title}</span>
            {count != null && <span className={`badge ${tone === "alert" ? "badge-alert" : tone === "warn" ? "badge-warn" : ""}`}>{count}</span>}
          </h2>
          {blurb && <p className="mt-0.5 text-sm text-muted">{blurb}</p>}
        </div>
        {action}
      </div>
      <div className={`card ${tone === "alert" ? "card-alert" : ""}`}>{children}</div>
    </section>
  );
}

function Empty({ children, tone }: { children: React.ReactNode; tone?: "alert" }) {
  return <p className={`text-sm ${tone === "alert" ? "text-alert-fg" : "text-muted"}`}>{children}</p>;
}

function ContentCard({ c, pubs, latest, kids, dim, showChannel }: {
  c: Content; pubs: Map<string, Publication[]>; latest: Map<number, Metric>; kids: Content[]; dim: boolean; showChannel: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-card-2/60 p-3">
      <ContentRow c={c} pubs={pubs.get(c.id) ?? []} latest={latest} dim={dim} showChannel={showChannel} />
      {kids.length > 0 && (
        <div className="mt-2 space-y-2 border-l-2 border-accent/40 pl-3">
          {kids.map((k) => <ContentRow key={k.id} c={k} pubs={pubs.get(k.id) ?? []} latest={latest} dim={false} />)}
        </div>
      )}
    </div>
  );
}

function statusClass(s: string) {
  if (s === "published" || s === "live" || s === "passed") return "text-ok-fg";
  if (s === "failed" || s === "killed") return "text-alert-fg";
  return "text-muted";
}

function ContentRow({ c, pubs, latest, dim, showChannel = false }: {
  c: Content; pubs: Publication[]; latest: Map<number, Metric>; dim: boolean; showChannel?: boolean;
}) {
  return (
    <div className={dim ? "opacity-50" : ""}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {showChannel && <ChannelBadge channel={c.channel} short />}
        <span className={`badge uppercase ${c.kind === "long" ? "badge-accent" : ""}`}>{c.kind}</span>
        <span className="font-medium">{c.title}</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted">
        <span>{c.topic}</span>
        <span className={statusClass(c.status)}>status: {c.status}</span>
        <span className={statusClass(c.qa_status)}>qa: {c.qa_status}</span>
        <span>{fmtDate(c.created_at)}</span>
      </div>
      {pubs.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs">
          {pubs.map((p) => {
            const m = latest.get(p.id);
            return (
              <li key={p.id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="badge">{p.platform}</span>
                <span className="text-muted">{p.privacy ?? "-"}</span>
                <span className={statusClass(p.status)}>{p.status}</span>
                {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="text-accent-fg underline">link</a>}
                {m ? (
                  <span className="text-muted">
                    {fmtNum(m.views)} views · {fmtNum(m.likes)} likes · {fmtNum(m.comments)} comments
                    {p.platform === "youtube" && (
                      <> · CTR {m.ctr != null ? `${(m.ctr * (m.ctr <= 1 ? 100 : 1)).toFixed(1)}%` : "-"} · avg {fmtSec(m.avg_view_duration_sec)}</>
                    )}
                  </span>
                ) : <span className="text-faint">no metrics</span>}
                {p.error && <span className="text-alert-fg">{p.error}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
