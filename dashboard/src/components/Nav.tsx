"use client";
import { parseScope, saveScope, PLATFORMS } from "@/lib/scope";
import Link from "@/components/ScopeLink";
import { BottomSheet } from "./BottomSheet";
import { Density } from "./Density";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { CHANNELS, ChannelFilter, accentCss, parseChannelFilter } from "@/lib/channels";

const links = [
  ["/", "Overview", "M3 12 12 4l9 8M5 10v10h5v-6h4v6h5V10"],
  ["/content", "Content", "M4 4h16v16H4zM10 8l6 4-6 4z"],
  ["/analytics", "Analytics", "M4 20V4M4 20h17M8 16l4-6 4 2 5-7"],
  ["/inbox", "Inbox", "M3 13h5l2 3h4l2-3h5M5 5h14l2 8v6H3v-6z"],
  ["/queue", "Queue", "M4 6h16M4 12h10M4 18h6"],
  [
    "/automation",
    "Automation",
    "M12 3v3m0 12v3M3 12h3m12 0h3M6 6l2 2m8 8 2 2m0-12-2 2M8 16l-2 2M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  ],
  ["/costs", "Costs", "M12 3v18M8 7h6a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h7"],
] as const;

const PUBLIC = new Set(["/login", "/privacy", "/terms"]);
const SIDEBAR = "lg:w-60";

function Icon({ d }: { d: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="h-4 w-4 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid h-8 w-8 place-items-center rounded-lg bg-card-2 text-sm font-semibold text-white"
      >
        F
      </span>
      <span className="leading-tight">
        <span className="block text-sm font-semibold tracking-tight">
          Faceless
        </span>
        {!compact && (
          <span className="block text-[11px] text-muted">
            three-channel ops
          </span>
        )}
      </span>
    </Link>
  );
}

/**
 * App shell: left sidebar on desktop, top bar on mobile. Public pages (login,
 * privacy, terms) get a slim header instead of the full navigation.
 */
export function Shell({
  channel,
  unread = 0,
  banners,
  children,
}: {
  channel: ChannelFilter;
  unread?: number;
  banners: React.ReactNode;
  children: React.ReactNode;
}) {
  const path = usePathname();
  const params = useSearchParams();
  channel = parseChannelFilter(params.get("channel") ?? "all");
  const platform = parseScope(Object.fromEntries(params)).platform;
  useEffect(() => { if (!PUBLIC.has(path)) saveScope({ channel, platform }); }, [channel, platform, path]);
  const scopedHref = (href: string) => { const q = new URLSearchParams(); q.set("channel", channel); q.set("platform", platform); return `${href}?${q}`; };
  const [badge, setBadge] = useState(unread);
  useEffect(() => {
    const abort = new AbortController();
    fetch(`/api/scope?channel=${channel}&platform=${platform}`, {signal:abort.signal}).then(r => r.ok ? r.json() : null).then(data => { if(data) setBadge(data.unread); }).catch(() => {});
    return () => abort.abort();
  }, [channel, platform]);
  const [more, setMore] = useState(false);
  const [scope, setScope] = useState(false);
  const router = useRouter();
  const isPublic = PUBLIC.has(path);

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
  }

  if (path === "/login") return <main className="login-shell"><div hidden><Density /></div>{children}</main>;

  if (isPublic) {
    return (
      <>
        <div hidden><Density /></div>
        <header className="border-b border-border bg-bg-2/80 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
            <Brand compact />
            <nav className="flex gap-4 text-xs text-muted">
              <Link
                href="/privacy"
                className={path === "/privacy" ? "text-fg" : "hover:text-fg"}
              >
                Privacy
              </Link>
              <Link
                href="/terms"
                className={path === "/terms" ? "text-fg" : "hover:text-fg"}
              >
                Terms
              </Link>
              {path !== "/login" && (
                <Link href="/login" className="hover:text-fg">
                  Log in
                </Link>
              )}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">{children}</main>
      </>
    );
  }

  const navItems = links.map(([href, label, d]) => {
    const active = path === href;
    return (
      <Link
        key={href}
        href={scopedHref(href)}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition ${
          active
            ? "bg-card-2 text-accent-fg"
            : "text-muted hover:bg-card-2 hover:text-fg"
        }`}
      >
        <Icon d={d} />
        {label}
      </Link>
    );
  });

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-20 hidden ${SIDEBAR} overflow-y-auto flex-col border-r border-border bg-bg-2 lg:flex`}
      >
        <div className="px-5 pb-4 pt-5">
          <Brand />
        </div>
        <nav className="flex flex-col gap-1 px-3">{navItems}</nav>
        <div className="mt-6 px-3">
          <div className="section-title px-3 pb-2">Platform</div><PlatformSwitcher />
          <div className="section-title px-3 pb-2 mt-4">Channel</div>
          <ChannelSwitcher key={channel} current={channel} layout="list" />
        </div>
        <div className="mt-auto border-t border-border p-3">
          <button
            onClick={logout}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-muted hover:bg-card-2 hover:text-fg"
          >
            <Icon d="M10 17l5-5-5-5M15 12H3M21 4v16" />
            Log out
          </button>
        </div>
      </aside>

      <header className="mobile-header lg:hidden">
        <button className="scope-chip" onClick={() => setScope(true)} aria-haspopup="dialog">{CHANNELS.find(c => c.key === channel)?.short ?? "All channels"}{` / ${platform === "all" ? "All platforms" : platform === "youtube" ? "YouTube" : platform === "instagram" ? "Instagram" : platform === "facebook" ? "Facebook" : "Hub"}`} <span aria-hidden>⌄</span></button>
      </header>
      <BottomSheet open={scope} close={() => setScope(false)} title="Channels & platforms"><h2 className="section-title">Channel</h2><ChannelSwitcher key={channel} current={channel} layout="list" /><h2 className="section-title mt-4">Platform</h2><PlatformSwitcher /></BottomSheet>
      <nav className="mobile-tabs lg:hidden" aria-label="Main navigation">
        {[links[0], links[1], links[3], links[2]].map(([href, label, d]) => <Link key={href} href={scopedHref(href)} onClick={() => setMore(false)} aria-current={path === href ? "page" : undefined}><Icon d={d} /><span>{href === "/" ? "Home" : label}{href === "/inbox" && badge > 0 && <b className="unread-badge">{badge > 99 ? "99+" : badge}</b>}</span></Link>)}
        <button onClick={() => setMore(!more)} aria-current={["/queue", "/costs", "/automation"].includes(path) ? "page" : undefined} aria-expanded={more}><Icon d="M4 12h16M4 6h16M4 18h16" />More</button>
      </nav>
      <BottomSheet open={more} close={() => setMore(false)} title="More">{[links[4], links[6], links[5]].map(([href, label]) => <Link className="sheet-link" key={href} href={scopedHref(href)} onClick={() => setMore(false)}>{label}</Link>)}<Density /><button className="sheet-link" onClick={logout}>Log out</button></BottomSheet>

      <main className="lg:pl-60">
        <div className="workspace">
          <div className="workspace-header hidden lg:flex"><div>{banners}</div><Density /></div>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted">{CHANNELS.find(c => c.key === channel)?.short ?? "All channels"} / <span className="capitalize">{platform === "all" ? "All platforms" : platform === "youtube" ? "YouTube" : platform === "instagram" ? "Instagram" : platform === "facebook" ? "Facebook" : "Hub"}</span><Link className="badge" href={`${path}?${new URLSearchParams({ ...Object.fromEntries(params), channel: "all", platform: "all" })}`} replace scroll={false} onClick={() => saveScope({channel:"all", platform:"all"})}>Clear scope ×</Link></div>
          <div className="lg:hidden">{banners}</div>
          {children}
        </div>
      </main>
    </>
  );
}

function ChannelSwitcher({
  current,
  layout,
}: {
  current: ChannelFilter;
  layout: "list" | "pills";
}) {
  const router = useRouter();
  const search = useSearchParams();
  const [selected, setSelected] = useState<ChannelFilter>(current);
  const [pending, startTransition] = useTransition();

  function choose(next: ChannelFilter, platform = search.get("platform") ?? "all") {
    setSelected(next);
    startTransition(() => {
      const url = new URL(window.location.href);
      url.searchParams.set("channel", next);
      url.searchParams.set("platform", platform);
      saveScope(parseScope(Object.fromEntries(url.searchParams)));
      if (platform) url.searchParams.delete("tab");
      router.replace(url.pathname + url.search, { scroll: false });
    });
  }

  const pills: { key: ChannelFilter; label: string; color?: string }[] = [
    { key: "all", label: "All channels" },
    ...CHANNELS.map((c) => ({
      key: c.key as ChannelFilter,
      label: layout === "list" ? c.name : c.short,
      color: accentCss(c),
    })),
  ];

  const list = layout === "list";
  return (
    <div
      className={`${list ? "flex flex-col gap-0.5" : "flex items-center gap-1"} ${pending ? "opacity-60" : ""}`}
      role="radiogroup"
      aria-label="Channel filter"
    >
      {pills.map((p) => {
        const active = selected === p.key;
        return (
          <div key={p.key}><button
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => choose(p.key)}
            className={
              list
                ? `flex items-center gap-2.5 min-h-11 rounded-lg px-3 py-1.5 text-left text-sm transition ${active ? "bg-card-2 text-fg" : "text-muted hover:bg-card-2 hover:text-fg"}`
                : `inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs ${active ? "border-accent bg-accent-soft text-fg" : "border-border text-muted"}`
            }
          >
            {p.color ? (
              <span
                aria-hidden
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{
                  backgroundColor: p.color,

                }}
              />
            ) : (
              <span
                aria-hidden
                className="inline-block h-1.5 w-1.5 rounded-full border border-muted"
              />
            )}
            {p.label}
          </button>{list && p.key !== "all" && <details open={active || undefined} className="ml-6 text-xs text-muted"><summary className="cursor-pointer py-1">Platforms</summary>{["youtube", "instagram", "facebook", "hub"].map(platform => <button key={platform} onClick={() => choose(p.key, platform)} className={`block min-h-11 rounded px-3 py-1.5 capitalize hover:bg-card-2 ${search.get("platform") === platform && active ? "text-fg bg-accent-soft" : ""}`}>{platform}</button>)}</details>}</div>
        );
      })}
    </div>
  );
}

function PlatformSwitcher() {
  const search = useSearchParams();
  const router = useRouter();
  const scope = parseScope(Object.fromEntries(search));
  return <div role="radiogroup" aria-label="Platform scope" className="flex flex-col">{PLATFORMS.filter(p => p !== "hub" || scope.platform === "hub").map(p => <button key={p} role="radio" aria-checked={scope.platform === p} className={`min-h-11 rounded-lg px-3 text-left text-sm ${scope.platform === p ? "bg-card-2 text-fg" : "text-muted hover:bg-card-2"}`} onClick={() => { const q = new URLSearchParams(search); q.set("channel",scope.channel); q.set("platform",p); q.delete("tab"); saveScope({...scope,platform:p}); router.replace(`${window.location.pathname}?${q}`, {scroll:false}); }}>{p === "all" ? "All" : p === "youtube" ? "YouTube" : p === "instagram" ? "Instagram" : p === "facebook" ? "Facebook" : "Hub"}</button>)}</div>;
}
