"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { CHANNELS, ChannelFilter, accentCss } from "@/lib/channels";

const links = [
  ["/", "Content"],
  ["/inbox", "Inbox"],
  ["/queue", "Queue"],
  ["/automation", "Automation"],
  ["/costs", "Costs"],
] as const;

export function Nav({ channel }: { channel: ChannelFilter }) {
  const path = usePathname();
  const router = useRouter();
  if (path === "/login") return null;
  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
  }
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-card/90 backdrop-blur">
      <nav className="mx-auto flex max-w-5xl items-center gap-1 overflow-x-auto px-2 py-2 text-sm sm:px-6">
        {links.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            className={`whitespace-nowrap rounded px-3 py-1.5 ${path === href ? "bg-accent text-white" : "hover:bg-border"}`}
          >
            {label}
          </Link>
        ))}
        <button onClick={logout} className="ml-auto whitespace-nowrap px-3 py-1.5 text-muted hover:text-fg">
          Log out
        </button>
      </nav>
      <ChannelSwitcher key={channel} current={channel} />
    </header>
  );
}

function ChannelSwitcher({ current }: { current: ChannelFilter }) {
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
    startTransition(() => router.refresh());
  }

  const pills: { key: ChannelFilter; label: string; color?: string }[] = [
    { key: "all", label: "All" },
    ...CHANNELS.map((c) => ({ key: c.key as ChannelFilter, label: c.name, color: accentCss(c) })),
  ];

  return (
    <div className={`mx-auto flex max-w-5xl items-center gap-1 overflow-x-auto px-2 pb-2 text-xs sm:px-6 ${pending ? "opacity-60" : ""}`}
      role="radiogroup" aria-label="Channel filter">
      {pills.map((p) => {
        const active = selected === p.key;
        return (
          <button
            key={p.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => choose(p.key)}
            className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 ${
              active ? "border-accent bg-accent/15 font-medium" : "border-border text-muted hover:bg-border hover:text-fg"
            }`}
          >
            {p.color && <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />}
            {p.label}
          </button>
        );
      })}
    </div>
  );
}
