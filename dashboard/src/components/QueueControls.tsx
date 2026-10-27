"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export function AddTopicForm() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/queue/add", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ topic }),
    });
    setBusy(false);
    if (!res.ok) return setError((await res.json().catch(() => ({}))).error ?? "Failed");
    setTopic("");
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <input className="min-w-0 flex-1" placeholder="New topic..." value={topic} onChange={(e) => setTopic(e.target.value)} />
      <button className="btn btn-primary" disabled={busy || !topic.trim()}>Add</button>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </form>
  );
}

export function QueueRowActions({ id }: { id: number }) {
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
  return (
    <div className="flex gap-1">
      <button className="btn" disabled={busy} onClick={() => act("bump")}>+5</button>
      <button className="btn text-red-500" disabled={busy} onClick={() => act("kill")}>Kill</button>
    </div>
  );
}
