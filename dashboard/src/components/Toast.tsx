"use client";
import { useEffect, useState } from "react";
export function toast(message: string) {
  window.dispatchEvent(new CustomEvent("dashboard-toast", { detail: message }));
}
export function ToastHost() {
  const [message, setMessage] = useState("");
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const show = (e: Event) => {
      setMessage((e as CustomEvent<string>).detail);
      clearTimeout(timer);
      timer = setTimeout(() => setMessage(""), 6000);
    };
    window.addEventListener("dashboard-toast", show);
    return () => {
      window.removeEventListener("dashboard-toast", show);
      clearTimeout(timer);
    };
  }, []);
  return (
    <div
      role="status"
      aria-live="polite"
      className={message ? "toast" : "sr-only"}
    >
      {message && (
        <>
          <span>{message}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => setMessage("")}
          >
            ×
          </button>
        </>
      )}
    </div>
  );
}
