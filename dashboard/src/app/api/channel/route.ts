import { NextResponse } from "next/server";
import { CHANNEL_COOKIE, isChannelKey } from "@/lib/channels";

// Sets the channel filter cookie. Allowed for reviewers (see middleware): it only
// changes what the dashboard shows, never the database.
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const channel = body?.channel;
  if (channel !== "all" && !isChannelKey(channel)) {
    return NextResponse.json({ error: "invalid channel" }, { status: 400 });
  }
  const res = NextResponse.json({ ok: true, channel });
  res.cookies.set(CHANNEL_COOKIE, channel, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 365 * 86400,
  });
  return res;
}
