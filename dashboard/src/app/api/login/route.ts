import { NextResponse } from "next/server";
import { COOKIE_NAME, cookieOptions, createSessionToken } from "@/lib/auth";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const owner = process.env.DASHBOARD_PASSWORD;
  const reviewer = process.env.DASHBOARD_REVIEWER_PASSWORD;
  const pw = typeof body.password === "string" ? body.password : "";
  let role: "owner" | "reviewer" | null = null;
  if (owner && pw === owner) role = "owner";
  else if (reviewer && pw === reviewer) role = "reviewer";
  if (!role) return NextResponse.json({ error: "invalid" }, { status: 401 });
  const res = NextResponse.json({ ok: true, role });
  res.cookies.set(COOKIE_NAME, await createSessionToken(role), cookieOptions());
  return res;
}
