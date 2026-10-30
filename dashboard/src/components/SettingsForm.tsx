"use client";
import { Section } from "./Section";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Settings } from "@/lib/types";
import { CHANNELS, accentCss } from "@/lib/channels";

const splitKeywords = (v: string) =>
  v
    .split(/\r?\n|,/)
    .map((x) => x.trim())
    .filter(Boolean);

export function SettingsForm({
  initial,
  readOnly = false,
}: {
  initial: Settings;
  readOnly?: boolean;
}) {
  const router = useRouter();
  const [s, setS] = useState<Settings>(initial);
  const [keywords, setKeywords] = useState(
    (initial.niche_keywords ?? []).join("\n"),
  );
  const [channelKeywords, setChannelKeywords] = useState<
    Record<string, string>
  >(() =>
    Object.fromEntries(
      CHANNELS.map((c) => [
        c.key,
        (initial[`niche_keywords_${c.key}`] ?? []).join("\n"),
      ]),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) =>
    setS((p) => ({ ...p, [k]: v }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    const payload: Settings = {
      ...s,
      niche_keywords: splitKeywords(keywords),
      niche_keywords_futurework: splitKeywords(
        channelKeywords.futurework ?? "",
      ),
      niche_keywords_tradewinds: splitKeywords(
        channelKeywords.tradewinds ?? "",
      ),
      niche_keywords_escapevelocity: splitKeywords(
        channelKeywords.escapevelocity ?? "",
      ),
    };
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    setBusy(false);
    const json = await res.json().catch(() => ({}));
    setMsg(res.ok ? "Saved." : (json.error ?? "Save failed"));
    if (res.ok) router.refresh();
  }

  return (
    <form onSubmit={save}>
      <fieldset disabled={readOnly} className="space-y-4">
        <Section title="Pipeline">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={s.pipeline_paused}
              onChange={(e) => set("pipeline_paused", e.target.checked)}
            />
            <span>Pipeline paused<span className="block text-xs text-muted">Stop scheduled production until resumed.</span></span>
          </label>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Long videos per run">
              <input
                type="number"
                min={0}
                value={s.long_videos_per_run}
                onChange={(e) =>
                  set("long_videos_per_run", Number(e.target.value))
                }
                className="w-full"
              />
            </Field>
            <Field label="Shorts per long">
              <input
                type="number"
                min={0}
                value={s.shorts_per_long}
                onChange={(e) => set("shorts_per_long", Number(e.target.value))}
                className="w-full"
              />
            </Field>
            <Field label="Publish privacy">
              <select
                value={s.publish_privacy}
                onChange={(e) =>
                  set(
                    "publish_privacy",
                    e.target.value as Settings["publish_privacy"],
                  )
                }
                className="w-full"
              >
                <option value="private">private</option>
                <option value="public">public</option>
              </select>
            </Field>
            <Field label="TTS voice">
              <input
                value={s.tts_voice}
                onChange={(e) => set("tts_voice", e.target.value)}
                className="w-full"
              />
            </Field>
          </div>
          <details><summary className="text-sm text-muted">Upload limits</summary><div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">            <Field label="YouTube uploads per day">
              <input
                type="number"
                min={1}
                step={1}
                value={s.youtube_uploads_per_day ?? 100}
                onChange={(e) =>
                  set("youtube_uploads_per_day", Number(e.target.value))
                }
                className="w-full"
              />
              <span className="text-xs text-muted">
                Google's default is 100 per day across all channels. Uploads beyond this queue for the next sync.
              </span>
            </Field>
            <Field label="YouTube quota units per day">
              <input
                type="number"
                min={1000}
                step={1}
                value={s.youtube_quota_units_per_day ?? 10000}
                onChange={(e) =>
                  set("youtube_quota_units_per_day", Number(e.target.value))
                }
                className="w-full"
              />
              <span className="text-xs text-muted">
                General bucket (thumbnails, title updates, replies). Google's default is 10,000. Uploads are counted separately below.
              </span>
            </Field>
</div></details>
          <Field label="Niche keywords (one per line)">
            <textarea
              rows={4}
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full"
            />
          </Field>
        </Section>

        <Section title="Per-channel keywords">
          <p className="text-xs text-muted">
            One per line. Leave a channel empty to use the defaults from its
            channel.json.
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {CHANNELS.map((c) => (
              <Field
                key={c.key}
                label={
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="inline-block h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: accentCss(c) }}
                    />
                    {c.name}
                  </span>
                }
              >
                <textarea
                  rows={6}
                  value={channelKeywords[c.key] ?? ""}
                  placeholder="(channel.json default)"
                  onChange={(e) =>
                    setChannelKeywords((p) => ({
                      ...p,
                      [c.key]: e.target.value,
                    }))
                  }
                  className="w-full"
                />
              </Field>
            ))}
          </div>
        </Section>

        <Section title="Engagement">
          <p className="text-xs text-muted">
            Apply these rules to new comments on the next engagement run.
          </p>
          <div className="flex flex-wrap gap-4 text-sm">
            {(["youtube", "instagram", "facebook"] as const).map((p) => (
              <label key={p} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!s.auto_reply?.[p]}
                  onChange={(e) =>
                    set("auto_reply", {
                      ...s.auto_reply,
                      [p]: e.target.checked,
                    })
                  }
                />
                <span>Auto-reply {p}<span className="block text-xs text-muted">Send approved automated replies on the next run.</span></span>
              </label>
            ))}
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!s.auto_like?.facebook}
                onChange={(e) =>
                  set("auto_like", { facebook: e.target.checked })
                }
              />
              <span>Auto-like facebook<span className="block text-xs text-muted">Like eligible Facebook comments during engagement.</span></span>
            </label>
          </div>
          <Field label="Max replies per day">
            <input
              type="number"
              min={0}
              value={s.max_replies_per_day}
              onChange={(e) =>
                set("max_replies_per_day", Number(e.target.value))
              }
              className="w-full sm:w-48"
            />
          </Field>
          <Field label="Reply tone notes">
            <textarea
              rows={3}
              value={s.reply_tone_notes}
              onChange={(e) => set("reply_tone_notes", e.target.value)}
              className="w-full"
            />
          </Field>
        </Section>

        <Section title="Budget">
          <Field label="Monthly budget (USD)">
            <input
              type="number"
              min={0}
              step="0.01"
              value={s.monthly_budget_usd}
              onChange={(e) =>
                set("monthly_budget_usd", Number(e.target.value))
              }
              className="w-full sm:w-48"
            />
          </Field>
        </Section>

        <div className={`flex items-center gap-3 ${readOnly ? "hidden" : ""}`}>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Saving..." : "Save settings"}
          </button>
          {msg && <span className="text-sm text-muted">{msg}</span>}
        </div>
      </fieldset>
    </form>
  );
}

function Field({
  label,
  children,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-muted">{label}</span>
      {children}
    </label>
  );
}
