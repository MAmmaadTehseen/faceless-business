"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

type Status = { state: "idle" | "running" | "done" | "failed"; run: { updated_at: string; html_url: string } | null; error?: string };

function ago(iso?: string) {
  if (!iso) return "";
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  return m < 1 ? "just now" : m < 60 ? `${m}m ago` : `${Math.round(m / 60)}h ago`;
}

/** Header pill + pull-to-refresh. Owners dispatch sync.yml; reviewers just reload cached data. */
export function SyncControl() {
  const router = useRouter();
  const [s, setS] = useState<Status | null>(null);
  const [msg, setMsg] = useState("");
  const [pull, setPull] = useState(0);
  const owner = useRef(true);
  const wasRunning = useRef(false);

  const poll = useCallback(async () => {
    const res = await fetch("/api/sync").catch(() => null);
    if (!res) return;
    if (res.status === 403) { owner.current = false; setS(null); return; }
    if (!res.ok) return;
    const next = (await res.json()) as Status;
    if (wasRunning.current && next.state !== "running") { router.refresh(); setMsg(next.state === "done" ? "Sync done · numbers updated" : "Sync failed · see GitHub"); }
    wasRunning.current = next.state === "running";
    setS(next);
  }, [router]);

  useEffect(() => { poll(); }, [poll]);
  useEffect(() => {
    if (s?.state !== "running") return;
    const t = setInterval(poll, 10_000);
    return () => clearInterval(t);
  }, [s?.state, poll]);
  useEffect(() => { if (!msg) return; const t = setTimeout(() => setMsg(""), 4000); return () => clearTimeout(t); }, [msg]);

  const sync = useCallback(async () => {
    if (!owner.current) { router.refresh(); return; }
    if (s?.state === "running") return;
    setS(prev => ({ run: prev?.run ?? null, state: "running" }));
    wasRunning.current = true;
    const res = await fetch("/api/sync", { method: "POST" }).catch(() => null);
    const body = res ? await res.json().catch(() => ({})) : { error: "Offline" };
    if (!res?.ok) { wasRunning.current = false; setMsg(body.error ?? "Sync could not start"); poll(); return; }
    setMsg("Sync started · about 5 min");
    setTimeout(poll, 5000);
  }, [s?.state, poll, router]);

  // Pull to refresh: only from the very top, only a deliberate downward drag.
  useEffect(() => {
    let y0: number | null = null, d = 0;
    const start = (e: TouchEvent) => { y0 = window.scrollY <= 0 ? e.touches[0].clientY : null; d = 0; };
    const move = (e: TouchEvent) => { if (y0 === null) return; d = Math.max(0, Math.min(90, e.touches[0].clientY - y0)); setPull(d); };
    const end = () => { if (y0 !== null && d > 70) sync(); y0 = null; d = 0; setPull(0); };
    addEventListener("touchstart", start, { passive: true });
    addEventListener("touchmove", move, { passive: true });
    addEventListener("touchend", end);
    return () => { removeEventListener("touchstart", start); removeEventListener("touchmove", move); removeEventListener("touchend", end); };
  }, [sync]);

  const running = s?.state === "running";
  const label = running ? "Syncing…" : s?.state === "failed" ? "Sync failed" : s?.run ? `Synced ${ago(s.run.updated_at)}` : "Refresh";
  return <>
    <div className="ptr" style={{ height: pull * 0.6 }} aria-hidden>{pull > 70 ? "Release to sync" : "Pull to sync"}</div>
    <button type="button" className={`sync-pill${running ? " busy" : ""}${s?.state === "failed" ? " failed" : ""}`} onClick={sync} aria-live="polite" disabled={running}>
      <span className="dot" aria-hidden />{label}
    </button>
    {msg && <div className="toast-pill" role="status">{msg}</div>}
  </>;
}
