"use client";
import { useState } from "react";
export function FilterSheet({ count, children }: { count: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return <div className={`filter-container ${open ? "filters-open" : ""}`}><button className="btn filter-trigger" onClick={() => setOpen(true)}>Filters · {count} active</button><div className="filter-panel"><button className="btn filter-close" onClick={() => setOpen(false)}>Close filters</button>{children}</div></div>;
}
