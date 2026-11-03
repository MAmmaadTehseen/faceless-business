/** Edge-safe gate. LOCAL_RECAP never overrides Vercel. */
export function recapEnabled() {
  return !process.env.VERCEL && (process.env.NODE_ENV === "development" || process.env.LOCAL_RECAP === "1");
}
export function recapRequestAllowed(request: Request) {
  if (!recapEnabled()) return false;
  const host = request.headers.get("host") || "";
  if (!/^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(host)) return false;
  // Next itself populates x-forwarded-for from the socket; require loopback only.
  const forwarded = request.headers.get("x-forwarded-for");
  if ((forwarded && !["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(forwarded)) || request.headers.has("forwarded")) return false;
  const origin = request.headers.get("origin");
  if (origin && origin !== `http://${host}`) return false;
  const site = request.headers.get("sec-fetch-site");
  return !site || site === "same-origin" || site === "none";
}
