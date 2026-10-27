import { NextResponse } from "next/server";
import { db } from "@/lib/supabase";
import { Settings } from "@/lib/types";

const str = (v: unknown) => (typeof v === "string" ? v : "");
const num = (v: unknown, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
const int = (v: unknown, d = 0) => Math.max(0, Math.round(num(v, d)));

export async function PUT(req: Request) {
  const b = (await req.json().catch(() => null)) as Partial<Settings> | null;
  if (!b) return NextResponse.json({ error: "invalid json" }, { status: 400 });

  const clean: Settings = {
    pipeline_paused: !!b.pipeline_paused,
    long_videos_per_run: int(b.long_videos_per_run, 1),
    shorts_per_long: int(b.shorts_per_long, 2),
    auto_reply: {
      youtube: !!b.auto_reply?.youtube,
      instagram: !!b.auto_reply?.instagram,
      facebook: !!b.auto_reply?.facebook,
    },
    auto_like: { facebook: !!b.auto_like?.facebook },
    max_replies_per_day: int(b.max_replies_per_day, 40),
    reply_tone_notes: str(b.reply_tone_notes),
    monthly_budget_usd: Math.max(0, num(b.monthly_budget_usd, 0)),
    publish_privacy: b.publish_privacy === "public" ? "public" : "private",
    niche_keywords: Array.isArray(b.niche_keywords) ? b.niche_keywords.map(String).filter(Boolean) : [],
    tts_voice: str(b.tts_voice),
  };

  // Values are jsonb; supabase-js serialises each JS value as JSON.
  const rows = Object.entries(clean).map(([key, value]) => ({ key, value }));
  const { error } = await db().from("settings").upsert(rows, { onConflict: "key" });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, settings: clean });
}
