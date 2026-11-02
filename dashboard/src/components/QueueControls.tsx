"use client";
import { BottomSheet } from "./BottomSheet";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { CHANNELS, ChannelKey, DEFAULT_CHANNEL } from "@/lib/channels";

export function AddTopicForm({ defaultChannel }: { defaultChannel?: ChannelKey }) {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [channel, setChannel] = useState<ChannelKey>(defaultChannel ?? DEFAULT_CHANNEL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/queue/add", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ topic, channel }),
    });
    setBusy(false);
    if (!res.ok) return setError((await res.json().catch(() => ({}))).error ?? "Failed");
    setTopic("");
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap gap-2">
      <input className="min-w-0 flex-1 basis-full sm:basis-0" placeholder="New topic..." value={topic} onChange={(e) => setTopic(e.target.value)} />
      <select value={channel} onChange={(e) => setChannel(e.target.value as ChannelKey)} aria-label="Channel">
        {CHANNELS.map((c) => <option key={c.key} value={c.key}>{c.name}</option>)}
      </select>
      <button className="btn btn-primary" disabled={busy || !topic.trim()}>Add</button>
      {error && <span className="text-xs text-alert-fg">{error}</span>}
    </form>
  );
}

export function QueueRowActions({ id }: { id: number }) {
  const [open,setOpen] = useState(false);
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function act(action: "bump" | "kill") {
    if (action === "kill" && !confirm("Kill this topic?")) return;
    setBusy(true);
    const res = await fetch(`/api/queue/${id}/${action}`, { method: "POST" });
    setBusy(false);
    if (!res.ok) alert((await res.json().catch(() => ({}))).error ?? "Failed");
    router.refresh();
  }
  return <div className="queue-row-actions"><span className="desktop-queue-actions"><button className="btn" aria-label="Increase priority by 5" disabled={busy} onClick={()=>act("bump")}>↑</button><button className="btn btn-danger" aria-label="Kill topic" disabled={busy} onClick={()=>act("kill")}>×</button></span><button className="btn mobile-action-trigger" aria-label="Topic actions" onClick={()=>setOpen(true)}>•••</button><BottomSheet open={open} close={()=>setOpen(false)} title="Topic actions"><div className="grid gap-2"><button className="btn" disabled={busy} onClick={()=>act("bump")}>Increase priority +5</button><button className="btn btn-danger" disabled={busy} onClick={()=>act("kill")}>Kill topic</button></div></BottomSheet></div>;
}
