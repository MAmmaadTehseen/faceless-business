/** The header's date range, shared by every page through the `days` (or `from`/`to`) URL params. */
export const RANGES = [["6h", "6 hours"], ["1", "24 hours"], ["7", "7 days"], ["28", "28 days"], ["90", "90 days"], ["all", "All time"]] as const;
export type Range = { key: string; days: number; end?: number; allTime: boolean; label: string };
const DAY = 86400000;

export function parseRange(sp: Record<string, string | undefined>, fallback = "7"): Range {
  const from = sp.from && Date.parse(sp.from), to = sp.to && Date.parse(sp.to);
  if (from && to && to >= from) {
    const end = to + DAY; // inclusive end date
    return { key: "custom", days: Math.max(1, Math.round((end - from) / DAY)), end, allTime: false, label: `${sp.from!.slice(5).replace("-", "/")} – ${sp.to!.slice(5).replace("-", "/")}` };
  }
  const key = RANGES.some(([k]) => k === sp.days) ? sp.days! : sp.days === "30" ? "28" : fallback;
  const label = RANGES.find(([k]) => k === key)![1];
  if (key === "all") return { key, days: 28, allTime: true, label };
  return { key, days: key === "6h" ? 0.25 : Number(key), allTime: false, label };
}
