import { NextResponse } from "next/server";
import { db } from "@/lib/supabase";
import { DEFAULT_CHANNEL, isChannelKey } from "@/lib/channels";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const topic = typeof body.topic === "string" ? body.topic.trim() : "";
  if (!topic) return NextResponse.json({ error: "topic required" }, { status: 400 });
  const channel = isChannelKey(body.channel) ? body.channel : DEFAULT_CHANNEL;
  const { data, error } = await db().from("topic_queue")
    .insert({ topic, channel, priority: 10, status: "queued", added_by: "user" })
    .select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, row: data });
}
