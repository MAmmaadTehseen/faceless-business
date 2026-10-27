import { NextResponse } from "next/server";
import { db } from "@/lib/supabase";

export async function POST(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { data: row, error } = await db().from("topic_queue").select("priority").eq("id", id).single();
  if (error || !row) return NextResponse.json({ error: "not found" }, { status: 404 });
  const { error: e2 } = await db().from("topic_queue").update({ priority: (row.priority ?? 0) + 5 }).eq("id", id);
  if (e2) return NextResponse.json({ error: e2.message }, { status: 500 });
  return NextResponse.json({ ok: true, priority: (row.priority ?? 0) + 5 });
}
