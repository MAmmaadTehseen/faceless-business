"use client";
import Link from "next/link";
import { useSearchParams, usePathname } from "next/navigation";
import { parseScope, scopeHref } from "@/lib/scope";
export default function ScopeLink(props: React.ComponentProps<typeof Link>) {
  const params = useSearchParams();
  const path = usePathname();
  const href = typeof props.href === "string" ? scopeHref(props.href.startsWith("?") ? `${path}${props.href}` : props.href, parseScope(Object.fromEntries(params))) : props.href;
  return <Link {...props} href={typeof href === "string" ? withRange(href, params) : href}/>;
}

/** The header date range follows the owner from page to page, like channel and platform. */
function withRange(href: string, params: URLSearchParams) {
  if (!href.startsWith("/") && !href.startsWith("?")) return href;
  const url = new URL(href, "https://scope.local");
  if (["days", "from", "to"].some(k => url.searchParams.has(k))) return href;
  for (const k of ["days", "from", "to"]) { const v = params.get(k); if (v) url.searchParams.set(k, v); }
  return `${url.pathname}${url.search}${url.hash}`;
}
