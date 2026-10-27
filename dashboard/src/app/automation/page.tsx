import { getSettings } from "@/lib/data";
import { SettingsForm } from "@/components/SettingsForm";

export default async function AutomationPage() {
  let settings;
  try {
    settings = await getSettings();
  } catch (e) {
    return <p className="text-red-500">DB error: {e instanceof Error ? e.message : String(e)}</p>;
  }
  return (
    <div>
      <h1 className="mb-3 text-xl font-semibold">Automation</h1>
      <SettingsForm initial={settings} />
    </div>
  );
}
