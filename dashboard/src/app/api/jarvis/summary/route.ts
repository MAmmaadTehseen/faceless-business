import { NextRequest, NextResponse } from "next/server";
import { authorized, summarize } from "@/lib/jarvis-summary";
import { loadSummaryRows } from "@/lib/jarvis-data";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const headers = { "Cache-Control": "private, no-store" };
  if (!authorized(req.headers.get("authorization"), process.env.JARVIS_READ_TOKEN)) return NextResponse.json({ error: "unauthorized" }, { status: 401, headers });
  const window = req.nextUrl.searchParams.get("window") ?? "1h";
  if (window !== "1h" && window !== "24h") return NextResponse.json({ error: "invalid window" }, { status: 400, headers });
  try {
    const now = new Date();
    return NextResponse.json(summarize(await loadSummaryRows(window, now), window, now), { headers });
  } catch {
    return NextResponse.json({ error: "summary unavailable" }, { status: 503, headers });
  }
}
