import Link from "next/link";
import { headers } from "next/headers";
import { getBannerState } from "@/lib/data";
import { fmtDate } from "@/lib/format";

export async function Banners() {
  const { paused, failedRun } = await getBannerState();
  const reviewer = (await headers()).get("x-dashboard-role") === "reviewer";
  if (!paused && !failedRun && !reviewer) return null;
  return (
    <div className="mb-5 space-y-2 text-sm">
      {reviewer && (
        <div className="rounded-lg border border-accent/50 bg-accent-soft px-3 py-2">
          <b>Read-only reviewer account.</b> You can browse everything; sending replies and changing settings is disabled.
        </div>
      )}
      {paused && (
        <div className="rounded-lg border border-warn/50 bg-warn/10 px-3 py-2">
          Pipeline is <b>paused</b>. <Link href="/automation" className="text-accent-fg underline">Resume in Automation</Link>.
        </div>
      )}
      {failedRun && (
        <div className="rounded-lg border border-alert/60 bg-alert-soft px-3 py-2 text-alert-fg">
          Latest run <b>failed</b> ({failedRun.workflow ?? "run"} at {fmtDate(failedRun.started_at)}).{" "}
          <Link href="/costs" className="underline">See runs</Link>.
        </div>
      )}
    </div>
  );
}
