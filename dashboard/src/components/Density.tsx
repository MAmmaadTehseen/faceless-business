"use client";
import { useEffect, useState } from "react";
export function Density() {
  const [density, setDensity] = useState("comfortable");
  useEffect(() => {
    const read = () => setDensity(localStorage.getItem("dashboard-density") === "compact" ? "compact" : "comfortable");
    read(); window.addEventListener("dashboard-density-change", read); window.addEventListener("storage", read);
    return () => { window.removeEventListener("dashboard-density-change", read); window.removeEventListener("storage", read); };
  }, []);
  useEffect(() => { document.documentElement.dataset.density = density; }, [density]);
  function change(value: string) { setDensity(value); localStorage.setItem("dashboard-density", value); window.dispatchEvent(new Event("dashboard-density-change")); }
  return <div className="density-control" role="group" aria-label="Display density">{["comfortable", "compact"].map(value => <button key={value} aria-pressed={density === value} onClick={() => change(value)}>{value === "comfortable" ? "Comfortable" : "Compact"}</button>)}</div>;
}
