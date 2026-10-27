import Link from "next/link";
import { getBannerState } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export async function Banners() {
  const { paused, failedRun } = await getBannerState();
  if (!paused && !failedRun) return null;
  return (
    <div className="mb-4 space-y-2 text-sm">
      {paused && (
        <div className="rounded border border-amber-500/50 bg-amber-500/10 px-3 py-2">
          Pipeline is <b>paused</b>. <Link href="/automation" className="underline">Resume in Automation</Link>.
        </div>
      )}
      {failedRun && (
        <div className="rounded border border-red-500/50 bg-red-500/10 px-3 py-2">
          Latest run <b>failed</b> ({failedRun.workflow ?? "run"} at {fmtDate(failedRun.started_at)}).{" "}
          <Link href="/costs" className="underline">See runs</Link>.
        </div>
      )}
    </div>
  );
}
