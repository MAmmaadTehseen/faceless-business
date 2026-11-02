"use client";
import { parseScope, scopeHref } from "@/lib/scope";
import Link from "@/components/ScopeLink";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";
export function ReplaceLink(props: React.ComponentProps<typeof Link>) {
  const params = useSearchParams(); const path = usePathname();
  const href = scopeHref(String(props.href).startsWith("?") ? path + props.href : String(props.href), parseScope(Object.fromEntries(params)));
  const router = useRouter(); const [pending, start] = useTransition();
  return <Link {...props} href={href} scroll={false} replace aria-busy={pending} className={`${props.className ?? ""} ${pending ? "opacity-60" : ""}`} onClick={e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); start(() => router.replace(href, { scroll: false })); }} />;
}
