import Link from "next/link";
import { headers } from "next/headers";
import { getBannerState } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export async function Banners() {
  const { paused, failedRun } = await getBannerState();
  const reviewer = (await headers()).get("x-dashboard-role") === "reviewer";
  if (!paused && !failedRun && !reviewer) return null;
  return (
    <div className="space-y-2 text-sm">
      {reviewer && (
        <div className="text-xs text-muted py-2">
          <span title="Sending replies and changing settings is disabled">Read-only workspace</span>
        </div>
      )}
      {paused && (
        <div className="text-xs text-muted py-2">
          Pipeline is <b>paused</b>. <Link href="/automation" className="text-accent-fg underline">Resume in Automation</Link>.
        </div>
      )}
      {failedRun && (
        <div className="text-xs text-alert-fg py-2">
          Latest run <b>failed</b> ({failedRun.workflow ?? "run"} at {fmtDate(failedRun.started_at)}).{" "}
          <Link href="/costs" className="underline">See runs</Link>.
        </div>
      )}
    </div>
  );
}
