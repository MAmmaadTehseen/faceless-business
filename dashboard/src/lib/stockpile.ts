import "server-only";
import { db } from "./supabase";
import { CHANNELS, ChannelFilter } from "./channels";
import { cached } from "./cache";

type Row = { id: string; channel: string; kind: string; parent_id: string | null; bytes: number | null };
function metadata(value: string | null): { bytes?: number } | null {
  try { return JSON.parse(value || "{}").stockpile ?? null; } catch { return null; }
}
/** Banked rows with bundle sizes from migration 018's banked_summary; reads qa_notes (large text) if it is missing. */
async function bankedRows(channel: ChannelFilter): Promise<Row[]> {
  const rows: Row[] = [];
  for (let offset = 0; ; offset += 1000) {
    let query = db().rpc("banked_summary").select("id,channel,kind,parent_id,bytes").order("id").range(offset, offset + 999);
    if (channel !== "all") query = query.eq("channel", channel);
    const { data, error } = await query;
    if (error?.code === "PGRST202") return legacyBankedRows(channel);
    if (error) throw error;
    const page = (data ?? []) as unknown as Row[];
    rows.push(...page);
    if (page.length < 1000) return rows;
  }
}

async function legacyBankedRows(channel: ChannelFilter): Promise<Row[]> {
  const rows: Row[] = [];
  for (let offset = 0; ; offset += 1000) {
    let query = db().from("content").select("id,channel,kind,parent_id,qa_notes").eq("status", "banked").order("id").range(offset, offset + 999);
    if (channel !== "all") query = query.eq("channel", channel);
    const { data, error } = await query;
    if (error) throw error;
    rows.push(...(data ?? []).map(({ qa_notes, ...r }) => ({ ...r, bytes: r.parent_id ? 0 : metadata(qa_notes)?.bytes ?? 0 })));
    if ((data ?? []).length < 1000) return rows;
  }
}

// Only the small summary below is cached.
export const getStockpile = cached("stockpile", loadStockpile);
async function loadStockpile(channel: ChannelFilter) {
  const rows = await bankedRows(channel);
  const { data, error } = await db().from("settings").select("key,value").in("key", ["banked_release_per_day", "stockpile_drive_space"]);
  if (error) throw error;
  const settings = Object.fromEntries((data ?? []).map(r => [r.key, r.value]));
  const rate = Math.max(0, Number(settings.banked_release_per_day) || 0);
  return { rate, checkedAt: settings.stockpile_drive_space?.checked_at as string | undefined,
    driveUsed: settings.stockpile_drive_space?.used as number | undefined,
    channels: CHANNELS.filter(c => channel === "all" || c.key === channel).map(c => {
      const banked = rows.filter(r => r.channel === c.key);
      const bundles = banked.filter(r => !r.parent_id).length;
      return { key: c.key, name: c.short, longs: banked.filter(r => r.kind === "long").length,
        shorts: banked.filter(r => r.kind === "short").length,
        days: rate ? Math.ceil(bundles / rate) : null,
        bytes: banked.filter(r => !r.parent_id).reduce((sum, r) => sum + (r.bytes ?? 0), 0) };
    }) };
}
