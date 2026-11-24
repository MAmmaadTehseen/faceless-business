import { NextRequest, NextResponse } from "next/server";
import { authorized } from "@/lib/jarvis-summary";
import { aggregate, parseQuery } from "@/lib/jarvis-query";
import { loadQueryRows } from "@/lib/jarvis-data";
import { CHANNEL_KEYS } from "@/lib/channels";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Read-only analytics for Jarvis: uploads, audience gain, top items and spend over any window.
export async function GET(req: NextRequest) {
  const headers = { "Cache-Control": "private, no-store" };
  if (!authorized(req.headers.get("authorization"), process.env.JARVIS_READ_TOKEN)) return NextResponse.json({ error: "unauthorized" }, { status: 401, headers });
  const now = new Date();
  const parsed = parseQuery(req.nextUrl.searchParams, CHANNEL_KEYS, now);
  if ("error" in parsed) return NextResponse.json({ error: parsed.error }, { status: 400, headers });
  try {
    return NextResponse.json(aggregate(parsed.query, await loadQueryRows(parsed.query, now), now), { headers });
  } catch {
    return NextResponse.json({ error: "query unavailable" }, { status: 503, headers });
  }
}
