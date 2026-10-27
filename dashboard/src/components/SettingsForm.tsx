"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Settings } from "@/lib/types";

export function SettingsForm({ initial }: { initial: Settings }) {
  const router = useRouter();
  const [s, setS] = useState<Settings>(initial);
  const [keywords, setKeywords] = useState((initial.niche_keywords ?? []).join("\n"));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS((p) => ({ ...p, [k]: v }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    const payload: Settings = {
      ...s,
      niche_keywords: keywords.split(/\r?\n|,/).map((x) => x.trim()).filter(Boolean),
    };
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    setBusy(false);
    const json = await res.json().catch(() => ({}));
    setMsg(res.ok ? "Saved." : json.error ?? "Save failed");
    if (res.ok) router.refresh();
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <section className="card space-y-3">
        <h2 className="font-medium">Pipeline</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={s.pipeline_paused} onChange={(e) => set("pipeline_paused", e.target.checked)} />
          Pipeline paused
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Long videos per run">
            <input type="number" min={0} value={s.long_videos_per_run} onChange={(e) => set("long_videos_per_run", Number(e.target.value))} className="w-full" />
          </Field>
          <Field label="Shorts per long">
            <input type="number" min={0} value={s.shorts_per_long} onChange={(e) => set("shorts_per_long", Number(e.target.value))} className="w-full" />
          </Field>
          <Field label="Publish privacy">
            <select value={s.publish_privacy} onChange={(e) => set("publish_privacy", e.target.value as Settings["publish_privacy"])} className="w-full">
              <option value="private">private</option>
              <option value="public">public</option>
            </select>
          </Field>
          <Field label="TTS voice">
            <input value={s.tts_voice} onChange={(e) => set("tts_voice", e.target.value)} className="w-full" />
          </Field>
        </div>
        <Field label="Niche keywords (one per line)">
          <textarea rows={4} value={keywords} onChange={(e) => setKeywords(e.target.value)} className="w-full" />
        </Field>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Engagement</h2>
        <div className="flex flex-wrap gap-4 text-sm">
          {(["youtube", "instagram", "facebook"] as const).map((p) => (
            <label key={p} className="flex items-center gap-2">
              <input type="checkbox" checked={!!s.auto_reply?.[p]}
                onChange={(e) => set("auto_reply", { ...s.auto_reply, [p]: e.target.checked })} />
              Auto-reply {p}
            </label>
          ))}
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={!!s.auto_like?.facebook}
              onChange={(e) => set("auto_like", { facebook: e.target.checked })} />
            Auto-like facebook
          </label>
        </div>
        <Field label="Max replies per day">
          <input type="number" min={0} value={s.max_replies_per_day} onChange={(e) => set("max_replies_per_day", Number(e.target.value))} className="w-full sm:w-48" />
        </Field>
        <Field label="Reply tone notes">
          <textarea rows={3} value={s.reply_tone_notes} onChange={(e) => set("reply_tone_notes", e.target.value)} className="w-full" />
        </Field>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Budget</h2>
        <Field label="Monthly budget (USD)">
          <input type="number" min={0} step="0.01" value={s.monthly_budget_usd} onChange={(e) => set("monthly_budget_usd", Number(e.target.value))} className="w-full sm:w-48" />
        </Field>
      </section>

      <div className="flex items-center gap-3">
        <button className="btn btn-primary" disabled={busy}>{busy ? "Saving..." : "Save settings"}</button>
        {msg && <span className="text-sm text-muted">{msg}</span>}
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-muted">{label}</span>
      {children}
    </label>
  );
}
