import { NextRequest, NextResponse } from "next/server";
import { COOKIE_NAME, verifySessionToken } from "@/lib/auth";

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (pathname === "/login" || pathname === "/api/login") return NextResponse.next();
  const role = await verifySessionToken(req.cookies.get(COOKIE_NAME)?.value);
  if (role) {
    // Reviewer accounts are read-only: any mutating API call is refused.
    if (role === "reviewer" && pathname.startsWith("/api/") && req.method !== "GET" && pathname !== "/api/logout") {
      return NextResponse.json({ error: "read-only reviewer account" }, { status: 403 });
    }
    const headers = new Headers(req.headers);
    headers.set("x-dashboard-role", role);
    return NextResponse.next({ request: { headers } });
  }
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
