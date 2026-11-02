"use client";
import { useEffect, useState } from "react";

type Props = {
  title: string;
  overview: React.ReactNode;
  shorts: React.ReactNode;
  comments: React.ReactNode;
  details: React.ReactNode;
};
const labels = ["Overview", "Shorts", "Comments", "Details"] as const;
type Tab = typeof labels[number];

export function VideoTabs({ title, overview, shorts, comments, details }: Props) {
  const [tab, setTab] = useState<Tab>("Overview");
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 200);
    const revealShort = () => {
      if (location.hash.startsWith("#short-")) setTab("Shorts");
    };
    update();
    revealShort();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("hashchange", revealShort);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("hashchange", revealShort);
    };
  }, []);
  const panels = { Overview: overview, Shorts: shorts, Comments: comments, Details: details };
  function select(label: Tab) {
    setTab(label);
    if (label === "Details") {
      document.querySelector<HTMLDetailsElement>(".video-details")?.setAttribute("open", "");
    }
  }
  return <div className="video-tab-layout">
    <div className="video-tab-chrome">
      <p className={`compact-video-title ${scrolled ? "shown" : ""}`}>{title}</p>
      <div className="video-tabs" role="tablist" aria-label="Video sections" onKeyDown={event => {
        const index = labels.indexOf(tab);
        const next = event.key === "ArrowRight" ? labels[(index + 1) % labels.length]
          : event.key === "ArrowLeft" ? labels[(index + labels.length - 1) % labels.length]
          : event.key === "Home" ? labels[0] : event.key === "End" ? labels.at(-1) : undefined;
        if (next) {
          event.preventDefault();
          select(next);
          document.getElementById(`tab-${next}`)?.focus();
        }
      }}>
        {labels.map(label => <button key={label} role="tab" id={`tab-${label}`}
          aria-controls={`panel-${label}`} aria-selected={tab === label}
          tabIndex={tab === label ? 0 : -1} onClick={() => select(label)}>{label}</button>)}
      </div>
    </div>
    {labels.map(label => <div key={label} className="video-tab-panel" id={`panel-${label}`}
      role="tabpanel" aria-labelledby={`tab-${label}`} hidden={tab !== label}>{panels[label]}</div>)}
  </div>;
}
