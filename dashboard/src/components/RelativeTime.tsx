import { fmtDate } from "@/lib/format";
export function RelativeTime({ value }: { value: string | null | undefined }) {
  if (!value) return <span>—</span>;
  const sec = Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 1000));
  const text =
    sec < 60
      ? "just now"
      : sec < 3600
        ? `${Math.floor(sec / 60)} min ago`
        : sec < 86400
          ? `${Math.floor(sec / 3600)} h ago`
          : `${Math.floor(sec / 86400)} d ago`;
  return (
    <time dateTime={value} title={fmtDate(value)} suppressHydrationWarning>
      {text}
    </time>
  );
}
