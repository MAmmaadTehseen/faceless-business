"use client";
import { useState, useEffect } from "react";
import { BottomSheet } from "./BottomSheet";
export function FilterSheet({ count, children }: { count: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  useEffect(() => { const mq = matchMedia("(max-width:1023px)"); const update = () => setMobile(mq.matches); update(); mq.addEventListener("change", update); return () => mq.removeEventListener("change", update); }, []);
  return <div className="filter-container"><button className="btn filter-trigger" onClick={() => setOpen(true)}>Filters · {count}</button>{mobile ? <BottomSheet open={open} close={() => setOpen(false)} title="Filters">{children}</BottomSheet> : <div className="filter-panel">{children}</div>}</div>;
}
