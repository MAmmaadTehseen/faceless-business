import { NextResponse } from "next/server";
import { db } from "@/lib/supabase";
import { replyToComment } from "@/lib/platforms";

export async function POST(
  req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const body = await req.json().catch(() => ({}));
  const text = typeof body.text === "string" ? body.text.trim() : "";
  if (!text)
    return NextResponse.json({ error: "text required" }, { status: 400 });

  const { data: c, error } = await db()
    .from("comments")
    .select("*,reply_text")
    .eq("id", id)
    .single();
  if (error || !c)
    return NextResponse.json({ error: "comment not found" }, { status: 404 });

  try {
    await replyToComment(c.platform, c.platform_comment_id, text);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    await db()
      .from("comments")
      .update({ reply_status: "failed", draft_reply: text })
      .eq("id", id);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
  const { error: saveError } = await db()
    .from("comments")
    .update({
      reply_status: "sent",
      reply_text: text,
      reply_sent_at: new Date().toISOString(),
      draft_reply: text,
    })
    .eq("id", id);
  if (saveError)
    return NextResponse.json(
      { error: "Reply sent, but saving failed. Refresh before retrying." },
      { status: 502 },
    );
  return NextResponse.json({ ok: true });
}
