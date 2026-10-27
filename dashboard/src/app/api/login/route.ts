import { NextResponse } from "next/server";
import { COOKIE_NAME, cookieOptions, createSessionToken } from "@/lib/auth";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected || typeof body.password !== "string" || body.password !== expected) {
    return NextResponse.json({ error: "invalid" }, { status: 401 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, await createSessionToken(), cookieOptions());
  return res;
}
