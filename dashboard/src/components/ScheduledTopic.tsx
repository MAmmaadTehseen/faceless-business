"use client";
import { useEffect, useState } from "react";
export function ScheduledTopic({ at, run }: { at: string; run: number }) {
  const [local, setLocal] = useState(at);
  useEffect(() => setLocal(new Date(at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZoneName: undefined })), [at]);
  const date = new Date(at);
  const label = run === 1 ? `Next run · ${date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })} ${date.toISOString().slice(11,16)} UTC` : `in ${run} runs · ${date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}`;
  return <span className="badge" title={local} aria-label={`Scheduled: ${label}`}>Scheduled · {label}</span>;
}
