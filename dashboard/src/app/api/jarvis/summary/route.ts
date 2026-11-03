import { NextRequest, NextResponse } from "next/server";
import { authorized, summarize } from "@/lib/jarvis-summary";
import { db } from "@/lib/supabase";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const headers = { "Cache-Control": "private, no-store" };
  if (!authorized(req.headers.get("authorization"), process.env.JARVIS_READ_TOKEN)) return NextResponse.json({ error: "unauthorized" }, { status: 401, headers });
  const window = req.nextUrl.searchParams.get("window") ?? "1h";
  if (window !== "1h" && window !== "24h") return NextResponse.json({ error: "invalid window" }, { status: 400, headers });
  try {
    const specs = [
      ["content", "id,channel"], ["publications", "id,content_id,platform,status,published_at,publish_at,status_changed_at"],
      ["metrics", "id,publication_id,captured_at,views,likes,comments"], ["costs", "id,at,usd"],
      ["settings", "key,value"], ["comments", "id"], ["runs", "id"],
    ];
    const entries = await Promise.all(specs.map(async ([table, columns]) => {
      const rows: Record<string, any>[] = [];
      for (let offset = 0; ; offset += 1000) {
        let q = db().from(table).select(columns).order(table === "settings" ? "key" : "id").range(offset, offset + 999);
        if (table === "settings") q = q.eq("key", "monthly_budget_usd");
        if (table === "costs") q = q.gte("at", new Date().toISOString().slice(0,7)+"-01T00:00:00Z");
        if (table === "comments") q = q.in("reply_status", ["new", "drafted"]);
        if (table === "runs") q = q.eq("status", "running");
        const { data, error } = await q;
        if (error) throw new Error("summary unavailable");
        rows.push(...(data as unknown as Record<string, any>[] ?? []));
        if (!data || data.length < 1000) break;
      }
      return [table, rows] as const;
    }));
    return NextResponse.json(summarize(Object.fromEntries(entries), window), { headers });
  } catch {
    return NextResponse.json({ error: "summary unavailable" }, { status: 503, headers });
  }
}
