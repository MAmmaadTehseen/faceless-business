import { recapRequestAllowed } from "@/lib/recap-local";
import { parseScope, SCOPE_COOKIE } from "@/lib/scope";
import { NextRequest, NextResponse } from "next/server";
import { COOKIE_NAME, verifySessionToken } from "@/lib/auth";

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (pathname === "/recap" || pathname.startsWith("/recap/") || pathname === "/api/recap" || pathname.startsWith("/api/recap/")) {
    if (!recapRequestAllowed(req)) return new NextResponse(null, { status: 404 });
    const headers = new Headers(req.headers);
    headers.set("x-local-recap", "1");
    return NextResponse.next({ request: { headers } });
  }
  if (
    pathname === "/login" ||
    pathname === "/api/login" ||
    pathname === "/privacy" ||
    pathname === "/terms"
  )
    return NextResponse.next();
  if (
    ["/sw.js", "/offline.html", "/manifest.json"].includes(pathname) ||
    pathname.startsWith("/icons/") ||
    /\.(png|ico|svg)$/.test(pathname)
  )
    return NextResponse.next();
  // Canonical scopes make even plain internal anchors preserve the saved selection.
  const scope = parseScope(Object.fromEntries(req.nextUrl.searchParams), req.cookies.get(SCOPE_COOKIE)?.value);
  function scopedNext(role: string) {
    const headers = new Headers(req.headers);
    headers.set("x-dashboard-role", role);
    headers.set("x-dashboard-search", req.nextUrl.search);
    const response = NextResponse.next({ request: { headers } });
    if (!pathname.startsWith("/api/") && !req.headers.has("rsc") && !req.headers.has("next-router-prefetch")) response.cookies.set(SCOPE_COOKIE, encodeURIComponent(JSON.stringify(scope)), { path: "/", maxAge: 31536000, sameSite: "lax", secure: req.nextUrl.protocol === "https:" });
    return response;
  }
  if (!pathname.startsWith("/api/") && (!req.nextUrl.searchParams.has("channel") || !req.nextUrl.searchParams.has("platform"))) {
    const url = new URL(req.nextUrl.pathname + req.nextUrl.search, req.url);
    url.searchParams.set("channel", scope.channel);
    url.searchParams.set("platform", scope.platform);
    url.host = req.headers.get("host") ?? url.host;
    const redirect = NextResponse.redirect(url);
    redirect.headers.set("Cache-Control", "private, no-store");
    redirect.headers.set("Vary", "Cookie");
    return redirect;
  }
  // Local visual QA is read-only and cannot bypass production authentication.
  if (
    process.env.NODE_ENV !== "production" &&
    process.env.DASHBOARD_QA_BYPASS === "1" &&
    req.method === "GET" &&
    (!pathname.startsWith("/api/") || pathname === "/api/scope")
  ) {
    return scopedNext("reviewer");
  }
  const role = await verifySessionToken(req.cookies.get(COOKIE_NAME)?.value);
  if (role) {
    // Reviewer accounts are read-only: any mutating API call is refused.
    if (
      role === "reviewer" &&
      pathname.startsWith("/api/") &&
      req.method !== "GET" &&
      pathname !== "/api/logout" &&
      pathname !== "/api/channel"
    ) {
      // /api/channel only sets a display-filter cookie, so reviewers may use it.
      return NextResponse.json(
        { error: "read-only reviewer account" },
        { status: 403 },
      );
    }
    return scopedNext(role);
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
