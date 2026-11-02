import { parseChannelFilter, type ChannelFilter } from "./channels";
export const SCOPE_COOKIE = "dashboard_scope";
export const PLATFORMS = ["all", "youtube", "instagram", "facebook", "hub"] as const;
export type Platform = typeof PLATFORMS[number];
export type Scope = { channel: ChannelFilter; platform: Platform };
type Params = Record<string, string | string[] | undefined>;
export function parseScope(params: Params = {}, saved?: string): Scope {
  let fallback: Params = {};
  try { const value = JSON.parse(decodeURIComponent(saved ?? "")); if (value && typeof value === "object" && !Array.isArray(value)) fallback = value; } catch { /* No valid saved scope. */ }
  const channel = params.channel !== undefined ? params.channel : fallback.channel;
  const platform = params.platform !== undefined ? params.platform : fallback.platform;
  return { channel: parseChannelFilter(typeof channel === "string" ? channel : "all"), platform: PLATFORMS.includes(platform as Platform) ? platform as Platform : "all" };
}
export function scopeParams(scope: Scope) { return { channel: scope.channel, platform: scope.platform === "all" ? "" : scope.platform }; }
export function scopeHref(href: string, scope: Scope) {
  if (!href || href.startsWith("#") || /^(?:[a-z]+:|\/\/)/i.test(href)) return href;
  const url = new URL(href, "https://scope.local");
  if (!url.searchParams.has("channel")) url.searchParams.set("channel", scope.channel);
  if (!url.searchParams.has("platform")) url.searchParams.set("platform", scope.platform);
  return `${url.pathname}${url.search}${url.hash}`;
}
export function saveScope(scope: Scope) {
  document.cookie = `${SCOPE_COOKIE}=${encodeURIComponent(JSON.stringify(scope))}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
}
export function filterPublications<T extends { platform: string }>(rows: T[], platform: string) { return rows.filter(p => !platform || platform === "all" || p.platform === platform); }
