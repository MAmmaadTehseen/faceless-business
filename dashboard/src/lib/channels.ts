// Channel metadata, copied from channels/<key>/channel.json so the dashboard
// needs no filesystem access at runtime. Keep in sync when a channel.json changes.

export type ChannelKey = "futurework" | "tradewinds" | "escapevelocity";
export type ChannelFilter = "all" | ChannelKey;

export type ChannelMeta = {
  key: ChannelKey;
  name: string;
  handle: string;
  /** style.accent RGB */
  accent: [number, number, number];
};

export const CHANNELS: ChannelMeta[] = [
  { key: "futurework", name: "Future Work Explained", handle: "futurework.explained", accent: [251, 191, 36] },
  { key: "tradewinds", name: "Trade Winds Report", handle: "tradewindsreport", accent: [231, 196, 122] },
  { key: "escapevelocity", name: "Escape Velocity", handle: "escapevelocitydaily", accent: [34, 211, 238] },
];

export const CHANNEL_KEYS = CHANNELS.map((c) => c.key) as ChannelKey[];
export const DEFAULT_CHANNEL: ChannelKey = "futurework";
export const CHANNEL_COOKIE = "fb_channel";

export function isChannelKey(v: unknown): v is ChannelKey {
  return typeof v === "string" && (CHANNEL_KEYS as string[]).includes(v);
}

export function parseChannelFilter(v: unknown): ChannelFilter {
  return isChannelKey(v) ? v : "all";
}

export function channelMeta(key: string | null | undefined): ChannelMeta | null {
  return CHANNELS.find((c) => c.key === key) ?? null;
}

export function accentCss(meta: ChannelMeta): string {
  const [r, g, b] = meta.accent;
  return `rgb(${r}, ${g}, ${b})`;
}
