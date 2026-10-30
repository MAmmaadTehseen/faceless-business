"use client";
import { useEffect, useState } from "react";
type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
export function Pwa() {
  const [prompt, setPrompt] = useState<InstallEvent | null>(null);
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").then(() => navigator.serviceWorker.ready).then(reg => {
        const discover = () => reg.active?.postMessage({ type: "ASSETS", urls: [...document.querySelectorAll<HTMLLinkElement | HTMLScriptElement>('link[rel="stylesheet"],link[rel="preload"],script[src]')].map(el => "href" in el ? el.href : el.src) });
        discover(); window.addEventListener("load", discover, { once: true });
      }).catch(() => { /* App remains usable if registration is unavailable. */ });
    }
    const install = (event: Event) => {
      try { if (localStorage.getItem("faceless-install-dismissed")) return; } catch {}
      event.preventDefault(); setPrompt(event as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", install);
    return () => window.removeEventListener("beforeinstallprompt", install);
  }, []);
  return prompt && <aside className="install-hint md:hidden" aria-label="Install app"><span>Keep Faceless on your home screen</span><button className="btn btn-primary" onClick={async () => { await prompt.prompt(); await prompt.userChoice; setPrompt(null); }}>Install app</button><button className="btn" onClick={() => { try { localStorage.setItem("faceless-install-dismissed", "1"); } catch {} setPrompt(null); }}>Dismiss</button></aside>;
}
