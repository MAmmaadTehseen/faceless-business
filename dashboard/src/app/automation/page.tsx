import { isOwner } from "@/lib/role";
import { getSettings } from "@/lib/data";
import { SettingsForm } from "@/components/SettingsForm";
import { PageHeader } from "@/components/PageHeader";

export default async function AutomationPage() {
  let settings;
  try {
    settings = await getSettings();
  } catch (e) {
    return (
      <p className="text-alert-fg">
        DB error: {e instanceof Error ? e.message : String(e)}
      </p>
    );
  }
  return (
    <div>
      <PageHeader
        title="Automation"
        blurb="Pipeline switches, per-channel keywords, engagement rules and the monthly budget guard. Changes apply on the next run."
      />
      <SettingsForm initial={settings} readOnly={!(await isOwner())} />
    </div>
  );
}
