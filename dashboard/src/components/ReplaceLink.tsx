"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
export function ReplaceLink(props: React.ComponentProps<typeof Link>) {
  const router = useRouter(); const [pending, start] = useTransition();
  return <Link {...props} scroll={false} replace aria-busy={pending} className={`${props.className ?? ""} ${pending ? "opacity-60" : ""}`} onClick={e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); start(() => router.replace(String(props.href), { scroll: false })); }} />;
}
