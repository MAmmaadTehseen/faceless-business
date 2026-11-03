import { fmtCount } from "@/lib/format";

/** Exact count remains available on hover alongside the compact display. */
export function Count({ value }: { value: number | null | undefined }) {
  return <span title={value == null ? undefined : String(value)}>{fmtCount(value)}</span>;
}
