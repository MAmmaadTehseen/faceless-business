"use client";
import { toast } from "./Toast";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
export function ActionButton({
  action,
  label,
  channel,
  configured,
  inputs,
  confirmation,
}: {
  action: string;
  label: string;
  channel?: string;
  configured: boolean;
  inputs?: Record<string, string>;
  confirmation?: string;
}) {
  const router = useRouter();
  const [requestId, setRequestId] = useState("");
  const [message, setMessage] = useState("");
  const [since, setSince] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!since) return;
    const timer = setInterval(async () => {
      try {
        const r = await fetch(`/api/actions?status=${action}&request_id=${encodeURIComponent(requestId)}`);
        const j = await r.json();
        if (!r.ok) {
          setMessage(j.error);
          setSince(0);
          return;
        }
        if (j.created_at && Date.parse(j.created_at) >= since - 5000) {
          if (j.status !== "completed") setMessage(j.status === "in_progress" ? "Running" : "Dispatched");
          if (j.status === "completed") {
            setMessage(
              j.conclusion === "success" ? "Done" : `Failed (${j.conclusion})`,
            );
            setSince(0);
            router.refresh();
          }
        }
        if (Date.now() - since > 180000) router.refresh();
        if (Date.now() - since > 7200000) {
          setSince(0);
          setMessage("Check GitHub for run status");
        }
      } catch {
        setMessage("Status unavailable; retrying");
      }
    }, 15000);
    return () => clearInterval(timer);
  }, [since, action, router, requestId]);
  async function trigger() {
    if (confirmation && !confirm(confirmation)) return;
    if (
      channel &&
      !confirm(
        `${label} for ${channel}? Production uses the configured budget and upload quota.`,
      )
    )
      return;
    setBusy(true);
    try {
      const r = await fetch("/api/actions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, channel, privacy: "private", ...inputs }),
      });
      const j = await r.json();
      setMessage(r.ok ? "Dispatched" : j.error);
      toast(
        r.ok
          ? `${label}: workflow started`
          : (j.error ?? "Could not start workflow"),
      );
      if (r.ok) { setRequestId(j.requestId ?? ""); setSince(Date.now()); }
    } catch {
      setMessage("Could not start workflow");
    } finally {
      setBusy(false);
    }
  }
  return (
    <span className="inline-flex flex-col gap-1">
      <button
        className={action === "retry" ? "btn btn-ghost" : "btn"}
        title={configured ? label : "not configured"}
        disabled={!configured || busy || !!since}
        onClick={trigger}
      >
        {label}
      </button>
      {message && (
        <span role="status" className="text-xs text-muted max-w-64">
          {message}
        </span>
      )}
    </span>
  );
}
