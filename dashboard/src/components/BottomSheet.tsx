"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
/** Modal sheets share keyboard, focus, scroll and touch dismissal behavior. */
export function BottomSheet({ open, close, title, children }: { open: boolean; close: () => void; title: string; children: React.ReactNode }) {
  const panel = useRef<HTMLElement>(null);
  const start = useRef(0);
  const onClose = useRef(close); onClose.current = close;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLElement>('button,a,input,select')?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose.current();
      if (e.key !== "Tab") return;
      const items = [...(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input,select,textarea,summary') ?? [])].filter(el => el.getClientRects().length);
      const first = items[0], last = items.at(-1);
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", key);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", key); previous?.focus(); };
  }, [open]);
  if (!open) return null;
  return createPortal(<div className="sheet-backdrop" onClick={close}><section ref={panel} className="mobile-sheet" role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}><div className="sheet-handle" onTouchStart={e => { start.current = e.touches[0].clientY; }} onTouchEnd={e => { if (e.changedTouches[0].clientY - start.current > 60) close(); }}><span /></div><div className="sheet-heading"><h2>{title}</h2><button className="btn" onClick={close}>Done</button></div>{children}</section></div>, document.body);
}
export function ActionSheet({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return <><details className="desktop-action-menu run-menu"><summary className="btn">{label}</summary><div>{children}</div></details><button className="btn mobile-action-trigger" onClick={() => setOpen(true)}>{label}</button><BottomSheet open={open} close={() => setOpen(false)} title={label}>{children}</BottomSheet></>;
}
