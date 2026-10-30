import Link from "next/link";
import { getAnalytics } from "@/lib/analytics";
import { getOverview } from "@/lib/data";
import { getContent } from "@/lib/content-data";
import { getChannelFilter } from "@/lib/channel-filter";
import { isOwner } from "@/lib/role";
import { CHANNELS, parseChannelFilter } from "@/lib/channels";
import { fmtUsd, fmtDate } from "@/lib/format";
import { ContentList } from "@/components/ContentList";
import { ContentFilters } from "@/components/ContentFilters";
import { filterContent } from "@/lib/content-filters";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { ActionButton } from "@/components/ActionButton";
import { HubAnalytics } from "@/components/HubAnalytics";
import { getHubAnalytics } from "@/lib/hub-analytics";
import { Countdown } from "@/components/Countdown";
export default async function Home({ searchParams }: { searchParams: Promise<Record<string,string>> }) {
  const sp = await searchParams;
  const channel = sp.channel ? parseChannelFilter(sp.channel) : await getChannelFilter();
  const [ov, items, owner, analytics, today] = await Promise.all([getOverview(channel, sp.platform), getContent(channel,true,sp.days), isOwner(), getAnalytics(channel,7,false,sp.platform), getAnalytics(channel,1,false,sp.platform)]);
  if (sp.platform === "hub") return <div className="space-y-6"><PageHeader title="Overview"/><HubAnalytics data={await getHubAnalytics(channel,7)}/></div>;
  const configured = !!process.env.GITHUB_TOKEN;
  const next = items.flatMap(c => c.publications).filter(p => p.publish_at && Date.parse(p.publish_at) > Date.now() && (!sp.platform || p.platform === sp.platform)).sort((a,b) => Date.parse(a.publish_at!) - Date.parse(b.publish_at!))[0];
  const attention = [ ...(ov.paused ? [{text:"Pipeline is paused",href:"/automation"}] : []), ...(ov.failedRun ? [{text:"Latest run needs review",href:"/costs"}] : []), ...ov.failedPubs.map(p=>({text:`${p.title} · upload failed`,href:"/content?status=failed"})), ...ov.failedContent.map(c=>({text:`${c.title} · production needs review`,href:"/content?status=failed"})), ...(ov.costs.pct >= 80 ? [{text:`${ov.costs.pct.toFixed(0)}% of monthly budget used`,href:"/costs"}] : []) ];
  const delta = analytics.total.views - analytics.previous.views;
  const running = ov.health.filter(h => h.lastRun && ["running","in_progress","queued"].includes(h.lastRun.status ?? ""));
  return <div className="space-y-8">
    <PageHeader title="Overview" action={owner && <details className="run-menu"><summary className="btn">Workspace actions</summary><div><ActionButton action="sync" label="Sync now" configured={configured}/><ActionButton action="engage" label="Reply now" configured={configured}/></div></details>}/>
    <section>
      <div className="hero"><p className="hero-label">Views · last 24 hours</p><p className="hero-value">{today.total.views.toLocaleString()}</p><p className="text-xs text-muted mt-2">{delta > 0 ? "+" : ""}{delta.toLocaleString()} views · last 7 days vs previous 7</p></div>
      <div className="supporting-stats">
        <div><p>Subscribers gained</p><strong title="Subscriber gains are not stored in the current metrics source">—</strong></div>
        <div><p>Pending replies</p><Link href="/inbox"><strong>{ov.pending.length}</strong></Link></div>
        <div><p>Month spend / budget</p><Link href="/costs"><strong>{fmtUsd(ov.costs.mtd)} <span className="text-muted text-xs">/ {fmtUsd(ov.costs.budget)}</span></strong></Link><div className="budget-track"><span style={{width:`${Math.min(100,ov.costs.pct)}%`}}/></div></div>
        <div><p>Next publish</p>{next?.publish_at ? <strong title={fmtDate(next.publish_at)}><Countdown at={next.publish_at}/></strong> : <span className="text-muted">Nothing scheduled</span>}</div>
      </div>
    </section>
    <section><div className="flex justify-between mb-3"><h2 className="text-base font-semibold">Needs attention</h2><Link className="text-xs text-muted" href="/content?status=failed">View all →</Link></div><div className="attention-list">{attention.length ? attention.slice(0,5).map((a,i)=><Link key={i} href={a.href}><span>{a.text}</span><span className="text-muted">→</span></Link>) : <p className="text-muted">Everything looks clear.</p>}</div></section>
    <section><h2 className="text-base font-semibold mb-4">Channels</h2><div className="home-channels">{CHANNELS.filter(c=>channel === "all" || c.key === channel).map(c=>{const h=ov.health.find(h=>h.key===c.key); const a=analytics.channels.find(a=>a.name===c.key);return <div className="channel-card" key={c.key}><div className="flex items-center justify-between gap-3"><h3 className="font-semibold flex items-center gap-2"><i className="series-dot" style={{background:c.brand.fg}}/>{c.short}</h3>{owner && <details className="run-menu"><summary className="btn">Run</summary><div><ActionButton action="produce" label="Produce now" channel={c.key} configured={configured}/><ActionButton action="shorts" label="Daily Short now" channel={c.key} configured={configured}/></div></details>}</div><div className="channel-stats"><div>{(a?.views??0).toLocaleString()}<span>Views · 7d</span></div><div>{a?.likes??0}<span>Likes</span></div><div>{h?.queued??0}<span>Topics queued</span></div></div><svg viewBox="0 0 300 48" className="w-full h-12" role="img" aria-label="Views over seven days"><polyline fill="none" stroke="var(--muted)" strokeWidth="2" points={(a?.daily??[0,0]).map((v,i,all)=>`${i*300/Math.max(1,all.length-1)},${44-v/Math.max(1,...all)*36}`).join(" ")}/></svg></div>})}</div></section>
    <section><h2 className="text-base font-semibold mb-3">Runs in flight</h2>{running.length ? <div className="card space-y-3">{running.map(h=><p key={h.key}>{h.lastRun?.workflow ?? "Production"} <span className="text-muted">in progress</span></p>)}</div> : <p className="text-muted">No runs in flight.</p>}{ov.queuedUploads.length > 0 && <details className="mt-3"><summary className="text-xs text-muted">{ov.queuedUploads.length} uploads waiting for quota</summary><div className="card mt-3">{ov.queuedUploads.map(p=><details key={p.id}><summary>{p.title} <span className="status-chip ml-2">queued</span></summary><p className="text-xs text-muted">{p.error ?? "Awaiting upload quota"}</p></details>)}</div></details>}</section>
    <Section title="Last published" action={<Link className="btn" href={`/content?channel=${channel}${sp.platform ? `&platform=${sp.platform}` : ""}`}>All content →</Link>}><details><summary className="text-xs text-muted">Filter content</summary><ContentFilters sp={sp} channel={channel} path="/"/></details><ContentList items={filterContent(items.filter(c=>c.publications.some(p=>["published","live"].includes(p.status))),sp)} sort={sp.sort??"newest"} limit={5}/></Section>
  </div>;
}
