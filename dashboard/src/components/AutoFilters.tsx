"use client";
import { useRef, useTransition, useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
export function AutoFilters({ children, className = "filter-bar", ...props }: React.ComponentProps<"form">) {
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const formRef = useRef<HTMLFormElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    const input = formRef.current?.elements.namedItem("q");
    if (timer.current && document.activeElement !== input) { clearTimeout(timer.current); timer.current = null; }
    if (input instanceof HTMLInputElement && !timer.current && input.value !== (params.get("q") ?? "")) input.value = params.get("q") ?? "";
  }, [params]);
  const [pending, start] = useTransition();
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  function update(form: HTMLFormElement, delay: number, changedName?: string) {
    if (timer.current) clearTimeout(timer.current);
    const navigate = () => {
      timer.current = null;
      const params = new URLSearchParams(window.location.search);
      if (changedName === "sort") params.delete("sortDirection");
      for (const [key, value] of new FormData(form)) {
        if (typeof value === "string" && value) params.set(key, value);
        else params.delete(key);
      }
      start(() => router.replace(`${path}?${params}`, { scroll: false }));
    };
    if (delay) timer.current = setTimeout(navigate, delay); else navigate();
  }
  return <form ref={formRef} {...props} className={`${className} ${pending ? "opacity-60" : ""}`} aria-busy={pending} onSubmit={e => { e.preventDefault(); update(e.currentTarget, 0); }} onChange={e => update(e.currentTarget, e.target instanceof HTMLInputElement ? 300 : 0, e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement ? e.target.name : undefined)}>{children}<span className="text-xs text-muted" role="status">{pending ? "Updating…" : ""}</span></form>;
}
