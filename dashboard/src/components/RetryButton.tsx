"use client";
import { ActionButton } from "./ActionButton";
export function RetryButton({ publications, label = "Retry" }: {
  publications: { id: number; content_id: string; platform: string; status: string; error?: string | null }[];
  label?: string;
}) {
  const selected = publications.filter(p => ["failed", "queued"].includes(p.status) && ["youtube", "instagram", "facebook"].includes(p.platform));
  if (!selected.length) return null;
  return <span title={selected.map(p => p.error).filter(Boolean).join("\n")}><ActionButton action="retry" label={label} configured inputs={{ids: selected.map(p => p.id).join(",")}} confirmation={`Retry ${selected.length} publication(s): ${selected.map(p => `${p.platform} / ${p.content_id}`).join(", ")}? This attempts publication even when local quota counters are full.`}/></span>;
}
