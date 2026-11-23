"use client";
import { parseScope, saveScope, PLATFORMS } from "@/lib/scope";
import Link from "@/components/ScopeLink";
import { BottomSheet } from "./BottomSheet";
import { Density } from "./Density";
import { SyncControl } from "./SyncControl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { CHANNELS, ChannelFilter, accentCss, parseChannelFilter } from "@/lib/channels";
import { RANGES, parseRange } from "@/lib/range";

const icons = {
  home: "M3 11l9-7 9 7v9h-6v-6H9v6H3z",
  content: "M4 5h16v14H4zM10 9l5 3-5 3z",
  analytics: "M12 3a9 9 0 1 0 9 9h-9zM14 2v8h8a8 8 0 0 0-8-8z",
  inbox: "M3 13h5l2 3h4l2-3h5M5 5h14l2 8v6H3v-6z",
  queue: "M4 6h16M4 12h10M4 18h6",
  automation: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
  costs: "M12 3v18M8 7h6a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h7",
  more: "M4 12h16M4 6h16M4 18h16",
  logout: "M10 17l5-5-5-5M15 12H3M21 4v16",
  calendar: "M3 5h18v16H3zM3 10h18M8 3v4M16 3v4",
};
const main = [["/", "Today", icons.home], ["/content", "Content", icons.content], ["/analytics", "Analytics", icons.analytics], ["/inbox", "Inbox", icons.inbox]] as const;
const extra = [["/queue", "Queue", icons.queue], ["/automation", "Automation", icons.automation], ["/costs", "Costs", icons.costs]] as const;
const PLATFORM_LABEL: Record<string, string> = { all: "All platforms", youtube: "YouTube", instagram: "Instagram", facebook: "Facebook", hub: "Hub site" };
const PUBLIC = new Set(["/login", "/privacy", "/terms"]);

function Icon({ d }: { d: string }) {
  return <svg aria-hidden viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;
}
function Mark() {
  return <Link href="/" className="cr-mark" aria-label="Faceless, today"><i aria-hidden />Faceless</Link>;
}

function ThemeToggle() {
  function toggle() {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("dashboard-theme", root.dataset.theme); } catch {}
  }
  return <button type="button" className="cr-icon" onClick={toggle} aria-label="Switch light or dark">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><circle cx="12" cy="12" r="8" /><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" /></svg>
  </button>;
}

/** App shell: header (date range, sync, theme), channel and platform rows, bottom nav on phones, left rail on desktop. */
export function Shell({ unread = 0, banners, children }: { channel: ChannelFilter; unread?: number; banners: React.ReactNode; children: React.ReactNode }) {
  const path = usePathname();
  const params = useSearchParams();
  const router = useRouter();
  const channel = parseChannelFilter(params.get("channel") ?? "all");
  const platform = parseScope(Object.fromEntries(params)).platform;
  const range = parseRange(Object.fromEntries(params));
  const [pending, startTransition] = useTransition();
  const [optimistic, setOptimistic] = useState<{ channel?: string; platform?: string; range?: string }>({});
  const [datesOpen, setDatesOpen] = useState(false);
  const [more, setMore] = useState(false);
  const [badge, setBadge] = useState(unread);

  useEffect(() => { if (!PUBLIC.has(path)) saveScope({ channel, platform }); }, [channel, platform, path]);
  useEffect(() => { if (!pending) setOptimistic({}); }, [pending]);
  useEffect(() => {
    const abort = new AbortController();
    fetch(`/api/scope?channel=${channel}&platform=${platform}`, { signal: abort.signal }).then(r => r.ok ? r.json() : null).then(data => { if (data) setBadge(data.unread); }).catch(() => {});
    return () => abort.abort();
  }, [channel, platform]);

  /** Filter changes swap the chip at once, then show the load bar until the server answers. */
  function go(change: Record<string, string | null>, shown: typeof optimistic) {
    setOptimistic(shown);
    const q = new URLSearchParams(params);
    for (const [k, v] of Object.entries(change)) v === null ? q.delete(k) : q.set(k, v);
    q.delete("page");
    if (change.platform) q.delete("tab");
    saveScope(parseScope(Object.fromEntries(q)));
    startTransition(() => router.replace(`${path}?${q}`, { scroll: false }));
  }
  async function logout() { await fetch("/api/logout", { method: "POST" }); router.push("/login"); }

  if (path === "/login") return <main className="login-shell"><div hidden><Density /></div>{children}</main>;
  if (PUBLIC.has(path)) return <>
    <header className="cr-top cr-frame" style={{ paddingBottom: 10 }}><Mark /><span className="cr-spacer" /><nav className="flex gap-4 text-sm"><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/login">Log in</Link></nav></header>
    <main className="cr-frame cr-main">{children}</main>
  </>;

  const shownChannel = optimistic.channel ?? channel, shownPlatform = optimistic.platform ?? platform, shownRange = optimistic.range ?? range.label;
  const active = (href: string) => href === "/" ? path === "/" : path === href || path.startsWith(href + "/");
  const inbox = (label: string) => <>{label}{badge > 0 && <b className="cr-badge">{badge > 99 ? "99+" : badge}</b>}</>;
  return <>
    {pending && <div className="cr-loadbar" role="progressbar" aria-label="Updating" />}
    <div className="cr-frame">
      <header className="cr-top">
        <Mark /><span className="cr-spacer" />
        <button type="button" className="sync-pill" style={{ borderColor: "var(--border-strong)" }} aria-expanded={datesOpen} aria-controls="cr-dates" onClick={() => setDatesOpen(!datesOpen)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d={icons.calendar} /></svg>{shownRange}
        </button>
        <SyncControl />
        <ThemeToggle />
      </header>
      {datesOpen && <div className="cr-datepanel" id="cr-dates">
        <div className="cr-seg" role="radiogroup" aria-label="Date range">{RANGES.map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={range.key === k} onClick={() => { setDatesOpen(false); go({ days: k, from: null, to: null }, { range: l }); }}>{l}</button>)}</div>
        <form className="cr-custom" onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); const from = String(f.get("from")), to = String(f.get("to")); if (!from || !to || to < from) return; setDatesOpen(false); go({ from, to, days: null }, { range: `${from.slice(5)} – ${to.slice(5)}` }); }}>
          <label htmlFor="cr-from">From<input id="cr-from" name="from" type="date" required defaultValue={params.get("from") ?? ""} /></label>
          <label htmlFor="cr-to">To<input id="cr-to" name="to" type="date" required defaultValue={params.get("to") ?? ""} /></label>
          <button className="btn btn-primary">Apply</button>
        </form>
      </div>}
      <div className="cr-chips" role="radiogroup" aria-label="Channel">
        {[{ key: "all", name: "All channels", color: "" }, ...CHANNELS.map(c => ({ key: c.key, name: c.short, color: accentCss(c) }))].map(c =>
          <button key={c.key} type="button" role="radio" className="cr-chip" aria-checked={shownChannel === c.key} onClick={() => go({ channel: c.key }, { channel: c.key })}>
            {c.color && <span className="cr-sw" style={{ background: c.color }} aria-hidden />}{c.name}
          </button>)}
      </div>
      <div className="cr-chips plat" role="radiogroup" aria-label="Platform">
        {PLATFORMS.map(p => <button key={p} type="button" role="radio" className="cr-chip" aria-checked={shownPlatform === p} onClick={() => go({ platform: p }, { platform: p })}>{PLATFORM_LABEL[p]}</button>)}
      </div>
      <main className={`cr-main${pending ? " loading" : ""}`} aria-busy={pending || undefined}>
        <div className="cr-banners">{banners}</div>
        {children}
      </main>
    </div>
    <nav className="cr-nav" aria-label="Main">
      {main.map(([href, label, d]) => <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}><Icon d={d} />{href === "/inbox" ? inbox(label) : label}</Link>)}
      <span className="cr-rail-extra">
        {extra.map(([href, label, d]) => <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}><Icon d={d} />{label}</Link>)}
        <button type="button" onClick={logout}><Icon d={icons.logout} />Log out</button>
      </span>
      <button type="button" className="cr-more" onClick={() => setMore(true)} aria-current={extra.some(([h]) => active(h)) ? "page" : undefined} aria-haspopup="dialog"><Icon d={icons.more} />More</button>
    </nav>
    <BottomSheet open={more} close={() => setMore(false)} title="More">
      {extra.map(([href, label]) => <Link className="sheet-link" key={href} href={href} onClick={() => setMore(false)}>{label}</Link>)}
      <Density />
      <button className="sheet-link" onClick={logout}>Log out</button>
    </BottomSheet>
  </>;
}
