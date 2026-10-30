"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { CHANNELS, ChannelFilter, accentCss } from "@/lib/channels";

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
const SIDEBAR = "md:w-60";

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
        className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm font-bold text-white shadow-[0_0_18px_-4px_var(--accent)]"
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
  banners,
  children,
}: {
  channel: ChannelFilter;
  banners: React.ReactNode;
  children: React.ReactNode;
}) {
  const path = usePathname();
  const [more, setMore] = useState(false);
  const router = useRouter();
  const isPublic = PUBLIC.has(path);

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
  }

  if (isPublic) {
    return (
      <>
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
        href={href}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition ${
          active
            ? "bg-accent text-white shadow-[0_6px_18px_-8px_var(--accent)]"
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
        className={`fixed inset-y-0 left-0 z-20 hidden ${SIDEBAR} flex-col border-r border-border bg-bg-2 md:flex`}
      >
        <div className="px-5 pb-4 pt-5">
          <Brand />
        </div>
        <nav className="flex flex-col gap-1 px-3">{navItems}</nav>
        <div className="mt-6 px-3">
          <div className="section-title px-3 pb-2">Channel</div>
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

      <header className="mobile-header md:hidden">
        <Brand compact />
        <div className="overflow-x-auto"><ChannelSwitcher key={channel} current={channel} layout="pills" /></div>
      </header>
      <nav className="mobile-tabs md:hidden" aria-label="Main navigation">
        {[links[0], links[1], links[3], links[2]].map(([href, label, d]) => <Link key={href} href={href} onClick={() => setMore(false)} aria-current={path === href ? "page" : undefined}><Icon d={d} />{href === "/" ? "Home" : label}</Link>)}
        <button onClick={() => setMore(!more)} aria-expanded={more} aria-controls="more-menu"><Icon d="M4 12h16M4 6h16M4 18h16" />More</button>
      </nav>
      {more && <div className="sheet-backdrop md:hidden" onClick={() => setMore(false)}><section id="more-menu" className="mobile-sheet" role="dialog" aria-modal="true" aria-label="More navigation" onClick={e => e.stopPropagation()}><button className="btn float-right" autoFocus onClick={() => setMore(false)}>Close</button><h2>More</h2>{[links[4], links[6], links[5]].map(([href, label]) => <Link className="sheet-link" key={href} href={href} onClick={() => setMore(false)}>{label}</Link>)}<button className="sheet-link" onClick={logout}>Log out</button></section></div>}

      <main className="md:pl-60">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 lg:px-8">
          {banners}
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
  const [selected, setSelected] = useState<ChannelFilter>(current);
  const [pending, startTransition] = useTransition();

  async function choose(next: ChannelFilter) {
    if (next === selected) return;
    const prev = selected;
    setSelected(next);
    const res = await fetch("/api/channel", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ channel: next }),
    });
    if (!res.ok) return setSelected(prev);
    startTransition(() => {
      const url = new URL(window.location.href);
      if (url.searchParams.has("channel")) {
        url.searchParams.set("channel", next);
        router.replace(url.pathname + url.search);
      } else router.refresh();
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
          <button
            key={p.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => choose(p.key)}
            className={
              list
                ? `flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-left text-sm transition ${active ? "bg-accent-soft text-fg ring-1 ring-accent/50" : "text-muted hover:bg-card-2 hover:text-fg"}`
                : `inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs ${active ? "border-accent bg-accent-soft text-fg" : "border-border text-muted"}`
            }
          >
            {p.color ? (
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full"
                style={{
                  backgroundColor: p.color,
                  boxShadow: `0 0 6px ${p.color}`,
                }}
              />
            ) : (
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full border border-muted"
              />
            )}
            {p.label}
          </button>
        );
      })}
    </div>
  );
}
