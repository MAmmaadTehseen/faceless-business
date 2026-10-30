"use client";
import { useEffect, useState } from "react";
type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
export function Pwa() {
  const [prompt, setPrompt] = useState<InstallEvent | null>(null);
  useEffect(() => {
    let disposed = false;
    let observer: MutationObserver | undefined;
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").then(() => navigator.serviceWorker.ready).then(reg => {
        if (disposed) return;
        const seen = new Set<string>();
        const discover = () => {
          const urls = [...document.querySelectorAll<HTMLLinkElement | HTMLScriptElement>('link[rel="stylesheet"],link[rel="preload"],script[src]')]
            .map(el => "href" in el ? el.href : el.src)
            .filter(url => !seen.has(url));
          urls.forEach(url => seen.add(url));
          if (urls.length) reg.active?.postMessage({ type: "ASSETS", urls });
        };
        discover();
        // Next adds route chunks after client navigation, too.
        observer = new MutationObserver(discover);
        observer.observe(document.documentElement, { childList: true, subtree: true });
      }).catch(() => { /* App remains usable if registration is unavailable. */ });
    }
    const install = (event: Event) => {
      try { if (localStorage.getItem("faceless-install-dismissed")) return; } catch {}
      event.preventDefault(); setPrompt(event as InstallEvent);
    };
    const installed = () => setPrompt(null);
    window.addEventListener("beforeinstallprompt", install);
    window.addEventListener("appinstalled", installed);
    return () => {
      disposed = true;
      observer?.disconnect();
      window.removeEventListener("beforeinstallprompt", install);
      window.removeEventListener("appinstalled", installed);
    };
  }, []);
  return prompt && <aside className="install-hint md:hidden" aria-label="Install app"><span>Keep Faceless on your home screen</span><button className="btn btn-primary" onClick={async () => { try { await prompt.prompt(); await prompt.userChoice; } catch { /* Browser may cancel the install prompt. */ } finally { setPrompt(null); } }}>Install app</button><button className="btn" onClick={() => { try { localStorage.setItem("faceless-install-dismissed", "1"); } catch {} setPrompt(null); }}>Dismiss</button></aside>;
}
