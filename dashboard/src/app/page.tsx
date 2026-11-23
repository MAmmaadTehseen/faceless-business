import { Stockpile } from "@/components/Stockpile";
import { Count } from "@/components/Count";
import { scopedSearch } from "@/lib/server-scope";
import Link from "@/components/ScopeLink";
import { ActionSheet } from "@/components/BottomSheet";
import { getAnalytics } from "@/lib/analytics";
import { getOverview } from "@/lib/data";
import { getPlatformContent } from "@/lib/content-data";
import { getChannelFilter } from "@/lib/channel-filter";
import { isOwner } from "@/lib/role";
import { CHANNELS, accentCss, parseChannelFilter } from "@/lib/channels";
import { fmtUsd, fmtDate, fmtCount } from "@/lib/format";
import { ContentList } from "@/components/ContentList";
import { ActionButton } from "@/components/ActionButton";
import { HubAnalytics } from "@/components/HubAnalytics";
import { getHubAnalytics } from "@/lib/hub-analytics";
import { Countdown } from "@/components/Countdown";
import { Donut, Legend } from "@/components/Donut";
import { parseRange } from "@/lib/range";

export default async function Home({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const sp = await scopedSearch(await searchParams);
  const channel = sp.channel ? parseChannelFilter(sp.channel) : await getChannelFilter();
  const range = parseRange(sp);
  const [ov, items, owner, analytics] = await Promise.all([getOverview(channel, sp.platform), getPlatformContent(channel, undefined, sp.platform), isOwner(), getAnalytics(channel, range.days, range.allTime, sp.platform, range.end)]);
  if (sp.platform === "hub") return <div><h1 className="cr-h1">Hub site</h1><HubAnalytics data={await getHubAnalytics(channel, Math.max(1, Math.round(range.days)))} /></div>;
  const configured = !!process.env.GITHUB_TOKEN;
  const next = items.flatMap(c => c.publications).filter(p => p.publish_at && Date.parse(p.publish_at) > Date.now()).sort((a, b) => Date.parse(a.publish_at!) - Date.parse(b.publish_at!))[0];
  type Todo = { sev: "bad" | "warn"; text: string; meta: string; cta: string; href: string };
  const todo: Todo[] = [
    ...(!sp.platform && ov.paused ? [{ sev: "bad" as const, text: "Pipeline is paused", meta: "Nothing new is produced or published", cta: "Open", href: "/automation" }] : []),
    ...(!sp.platform && ov.failedRun ? [{ sev: "bad" as const, text: `${ov.failedRun.workflow ?? "Latest run"} failed`, meta: fmtDate(ov.failedRun.started_at), cta: "Review", href: "/costs" }] : []),
    ...ov.failedPubs.map(p => ({ sev: "bad" as const, text: p.title, meta: `${p.platform} upload failed${p.error ? ` · ${p.error.slice(0, 70)}` : ""}`, cta: "Retry", href: `/content/${encodeURIComponent(p.content_id)}` })),
    ...ov.failedContent.map(c => ({ sev: "warn" as const, text: c.title, meta: "Production or QA needs review", cta: "Rebuild", href: `/content/${encodeURIComponent(c.id)}` })),
    ...(ov.pending.length ? [{ sev: "warn" as const, text: `${ov.pending.length} comments waiting`, meta: "Replies to approve or send", cta: "Open", href: "/inbox" }] : []),
    ...(!sp.platform && ov.costs.pct >= 80 ? [{ sev: "warn" as const, text: `${ov.costs.pct.toFixed(0)}% of the monthly budget used`, meta: `${fmtUsd(ov.costs.mtd)} of ${fmtUsd(ov.costs.budget)}`, cta: "Costs", href: "/costs" }] : []),
  ];
  const bad = todo.filter(t => t.sev === "bad").length;
  const delta = analytics.total.views - analytics.previous.views;
  const shown = CHANNELS.filter(c => channel === "all" || c.key === channel);
  const slices = shown.map(c => ({ label: c.short, value: analytics.channels.find(a => a.name === c.key)?.views ?? 0, color: accentCss(c) }));
  const running = ov.health.filter(h => (channel === "all" || h.key === channel) && !sp.platform && h.lastRun && ["running", "in_progress", "queued"].includes(h.lastRun.status ?? ""));
  const budgetLeft = Math.max(0, ov.costs.budget - ov.costs.mtd);
  return <div>
    <p className="eyebrow">{new Date().toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })} · {range.label}</p>
    <h1 className="cr-h1">{todo.length === 0 ? "All clear today" : bad ? `${todo.length} ${todo.length === 1 ? "thing needs" : "things need"} you` : `${todo.length} to look at`}</h1>

    <section className="cr-sec" style={{ marginTop: 14 }}><div className="cr-strip">
      <Donut slices={slices} size={124} center={fmtCount(analytics.total.views)} sub="views" label="Views by channel" />
      <div style={{ minWidth: 0 }}>
        <span className={`cr-delta ${delta >= 0 ? "cr-up" : "cr-down"}`}>{delta >= 0 ? "▲" : "▼"} {fmtCount(Math.abs(delta))} vs previous {range.label}</span>
        <div style={{ marginTop: 10 }}><Legend slices={slices} /></div>
      </div>
    </div></section>

    <section className="cr-sec"><div className="cr-sechead"><h2>Today</h2>{owner && <ActionButton action="engage" label="Reply now" configured={configured} />}</div>
      {todo.length ? <ul className="cr-todo">{todo.slice(0, 6).map((t, i) => <li key={i}><Link href={t.href}><span className={`cr-sev ${t.sev}`} /><span style={{ minWidth: 0 }}><b>{t.text}</b><small>{t.meta}</small></span><span className="cr-cta">{t.cta}</span></Link></li>)}</ul> : <p className="cr-sub">Nothing is waiting on you.</p>}
      {todo.length > 6 && <Link className="cr-link" href="/content?status=failed">All {todo.length} items →</Link>}
    </section>

    <div className="cr-two">
      <section className="cr-sec"><div className="cr-sechead"><h2>Channels</h2><Link className="cr-link" href="/analytics">Analytics →</Link></div>
        <div className="cr-chgrid">{shown.map(c => {
          const h = ov.health.find(h => h.key === c.key), a = analytics.channels.find(a => a.name === c.key);
          const views = a?.views ?? 0, prev = a?.previous.views ?? 0, g = prev ? Math.round((views - prev) / prev * 100) : null;
          return <div className="cr-ch" key={c.key}>
            <Donut slices={[{ label: c.short, value: views, color: accentCss(c) }, { label: "Other channels", value: Math.max(0, analytics.total.views - views) || (views ? 0 : 1), color: "var(--border)" }]} size={52} label={`${c.short} share of views`} />
            <span style={{ minWidth: 0 }}>
              <Link href={`/?channel=${c.key}`} className="name">{c.short}</Link><br />
              <span className="meta">{h?.queued ?? 0} topics queued</span><br />
              <span className={`cr-pill ${h?.level === "alert" ? "bad" : h?.level === "warn" ? "warn" : "ok"}`}>{h?.level === "alert" ? "Last run failed" : h?.level === "warn" ? "Check" : "Healthy"}</span>
              {owner && <span style={{ marginLeft: 8 }}><ActionSheet label="Run"><div className="grid gap-2"><ActionButton action="produce" label="Produce now" channel={c.key} configured={configured} /><ActionButton action="shorts" label="Daily Short now" channel={c.key} configured={configured} /></div></ActionSheet></span>}
            </span>
            <span className="v"><b>{fmtCount(views)}</b><span className={`cr-delta ${g === null ? "" : g >= 0 ? "cr-up" : "cr-down"}`}>{g === null ? "new" : `${g >= 0 ? "+" : ""}${g}%`}</span></span>
          </div>;
        })}</div>
      </section>
      <div>
        {!sp.platform && <section className="cr-sec"><div className="cr-sechead"><h2>Spend</h2><Link className="cr-link" href="/costs">Costs →</Link></div>
          <div className="card cr-piebox">
            <Donut slices={[{ label: "Spent", value: ov.costs.mtd, color: "var(--accent)" }, { label: "Left", value: budgetLeft, color: "var(--border)" }]} size={104} center={`${Math.round(ov.costs.pct)}%`} sub={`of ${fmtUsd(ov.costs.budget)}`} label="Monthly budget used" />
            <p className="cr-sub" style={{ flex: 1, minWidth: 150 }}>{fmtUsd(ov.costs.mtd)} spent this month, {fmtUsd(budgetLeft)} left. On pace for {fmtUsd(ov.costs.projected)}.</p>
          </div></section>}
        <section className="cr-sec"><div className="cr-sechead"><h2>Next up</h2></div>
          <div className="card">
            <p>{next?.publish_at ? <>Next publish in <b><Countdown at={next.publish_at} /></b> <span className="cr-sub">({fmtDate(next.publish_at)})</span></> : <span className="cr-sub">Nothing scheduled</span>}</p>
            <p className="cr-sub" style={{ marginTop: 6 }}>{running.length ? running.map(h => `${h.lastRun?.workflow ?? "Production"} running`).join(" · ") : "No runs in flight."}</p>
            {ov.queuedUploads.length > 0 && <details style={{ marginTop: 6 }}><summary className="cr-sub"><Count value={ov.queuedUploads.length} /> uploads waiting for quota</summary>{ov.queuedUploads.map(p => <p key={p.id} className="text-sm">{p.title} <span className="cr-pill mute">queued</span></p>)}</details>}
          </div>
        </section>
      </div>
    </div>

    {!sp.platform && <div className="cr-sec"><Stockpile channel={channel} /></div>}
    <section className="cr-sec"><div className="cr-sechead"><h2>Latest</h2><Link className="cr-link" href="/content">All content →</Link></div>
      <ContentList items={items.filter(c => c.publications.some(p => ["published", "live"].includes(p.status))).slice(0, 8)} sort="newest" limit={5} />
    </section>
  </div>;
}
