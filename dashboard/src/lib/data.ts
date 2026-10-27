import "server-only";
import { db } from "./supabase";
import { DEFAULT_SETTINGS, Run, Settings } from "./types";

export async function getSettings(): Promise<Settings> {
  const { data, error } = await db().from("settings").select("key,value");
  if (error) throw error;
  const s: Record<string, unknown> = { ...DEFAULT_SETTINGS };
  for (const row of data ?? []) s[row.key] = row.value;
  return s as Settings;
}

export async function getLatestRun(): Promise<Run | null> {
  const { data } = await db()
    .from("runs")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  return (data as Run) ?? null;
}

// Shared by the layout banner. Never throws so a missing DB only degrades the banner.
export async function getBannerState() {
  try {
    const [settings, run] = await Promise.all([getSettings(), getLatestRun()]);
    return { paused: !!settings.pipeline_paused, failedRun: run?.status === "failed" ? run : null };
  } catch {
    return { paused: false, failedRun: null };
  }
}
