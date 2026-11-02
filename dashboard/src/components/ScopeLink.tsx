"use client";
import Link from "next/link";
import { useSearchParams, usePathname } from "next/navigation";
import { parseScope, scopeHref } from "@/lib/scope";
export default function ScopeLink(props: React.ComponentProps<typeof Link>) {
  const params = useSearchParams();
  const path = usePathname();
  const href = typeof props.href === "string" ? scopeHref(props.href.startsWith("?") ? `${path}${props.href}` : props.href, parseScope(Object.fromEntries(params))) : props.href;
  return <Link {...props} href={href}/>;
}
