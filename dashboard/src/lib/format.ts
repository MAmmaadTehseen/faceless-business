export function fmtDate(s: string | null | undefined): string {
  if (!s) return "-";
  const d = new Date(s);
  return (
    d.toLocaleString("en-US", {
      timeZone: "UTC",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }) + " UTC"
  );
}
export function fmtNum(n: number | null | undefined): string {
  if (n == null) return "-";
  return Intl.NumberFormat("en-US").format(n);
}
export function fmtUsd(n: number | null | undefined): string {
  return `$${(n ?? 0).toFixed(2)}`;
}
export function fmtSec(n: number | null | undefined): string {
  if (n == null) return "-";
  const m = Math.floor(n / 60);
  const s = Math.round(n % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}
