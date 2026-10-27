import { NextResponse } from "next/server";
import { db } from "@/lib/supabase";
import { likeComment } from "@/lib/platforms";

export async function POST(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { data: c, error } = await db().from("comments").select("*").eq("id", id).single();
  if (error || !c) return NextResponse.json({ error: "comment not found" }, { status: 404 });
  if (c.platform !== "facebook") return NextResponse.json({ error: "like only supported for facebook" }, { status: 400 });
  try {
    await likeComment(c.platform, c.platform_comment_id);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 502 });
  }
  await db().from("comments").update({ liked: true }).eq("id", id);
  return NextResponse.json({ ok: true });
}
