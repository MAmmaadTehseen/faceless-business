import "server-only";
import { cookies, headers } from "next/headers";
import { parseScope, scopeParams, SCOPE_COOKIE } from "./scope";
export async function getScope(params?: Record<string, string | string[] | undefined>) {
  const h = await headers();
  return parseScope(params ?? Object.fromEntries(new URLSearchParams(h.get("x-dashboard-search") ?? "")), (await cookies()).get(SCOPE_COOKIE)?.value);
}
export async function scopedSearch(params: Record<string,string>): Promise<Record<string,string>> { return { ...params, ...scopeParams(await getScope(params)) }; }
