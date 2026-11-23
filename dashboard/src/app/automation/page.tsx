import { isOwner } from "@/lib/role";
import { getSettings } from "@/lib/data";
import { db } from "@/lib/supabase";
import { SettingsForm } from "@/components/SettingsForm";
import { DonutCard } from "@/components/Donut";
import { fmtCount } from "@/lib/format";

/** Today's YouTube quota bucket. Google resets at midnight Pacific, so the row key is the Pacific date (see pipeline/publish/quota.py). */
async function quotaToday() {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Los_Angeles" }).format(new Date());
  const { data } = await db().from("quota_log").select("units,uploads").eq("day", day).maybeSingle();
  return { units: data?.units ?? 0, uploads: data?.uploads ?? 0 };
}

export default async function AutomationPage() {
  let settings;
  try {
    settings = await getSettings();
  } catch (e) {
    return <p className="text-alert-fg">DB error: {e instanceof Error ? e.message : String(e)}</p>;
  }
  const quota = await quotaToday().catch(() => null);
  const unitBudget = settings.youtube_quota_units_per_day ?? 10000, uploadBudget = settings.youtube_uploads_per_day ?? 100;
  return <div className="automation-settings">
    <h1 className="cr-h1">Automation</h1>
    <p className="cr-sub">Pipeline switches, per-channel keywords, engagement rules and the monthly budget guard. Changes apply on the next run.</p>
    <section className="cr-sec"><div className="cr-sechead"><h2>Pipeline</h2><span className={`cr-pill ${settings.pipeline_paused ? "bad" : "ok"}`}>{settings.pipeline_paused ? "Paused" : "Ready to run"}</span></div>
      {quota && <div className="cr-two">
        <DonutCard label="YouTube quota units used today" size={108} center={`${Math.round(quota.units / unitBudget * 100)}%`} sub="units" format={fmtCount}
          slices={[{ label: "Units used", value: quota.units, color: "var(--warn)" }, { label: "Units left", value: Math.max(0, unitBudget - quota.units), color: "var(--border)" }]} />
        <DonutCard label="YouTube uploads used today" size={108} center={`${quota.uploads}`} sub={`of ${uploadBudget}`}
          slices={[{ label: "Uploads used", value: quota.uploads, color: "var(--accent)" }, { label: "Uploads left", value: Math.max(0, uploadBudget - quota.uploads), color: "var(--border)" }]} />
      </div>}
      <p className="text-xs text-muted" style={{ marginTop: 8 }}>Quota resets at midnight Pacific (08:00 UTC). 1,000 units are held back for sync and replies.</p>
    </section>
    <section className="cr-sec"><SettingsForm initial={settings} readOnly={!(await isOwner())} /></section>
  </div>;
}
