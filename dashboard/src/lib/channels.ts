// Channel metadata, copied from channels/<key>/channel.json so the dashboard
// needs no filesystem access at runtime. Keep in sync when a channel.json changes.

export type ChannelKey = "futurework" | "tradewinds" | "escapevelocity";
export type ChannelFilter = "all" | ChannelKey;

export type ChannelMeta = {
  key: ChannelKey;
  name: string;
  /** Short label for tight spaces (stat tiles, mobile pills). */
  short: string;
  handle: string;
  /** style.accent RGB */
  accent: [number, number, number];
  /** Brand palette used for badges: background from style.bg, text from style.accent. */
  brand: { bg: string; fg: string };
  schedule: string;
};

export const CHANNELS: ChannelMeta[] = [
  {
    key: "futurework", name: "Future Work Explained", short: "Future Work", handle: "futurework.explained",
    accent: [251, 191, 36], brand: { bg: "#172448", fg: "#fbbf24" }, schedule: "Mon · Wed · Fri 06:00 UTC",
  },
  {
    key: "tradewinds", name: "Trade Winds Report", short: "Trade Winds", handle: "tradewindsreport",
    accent: [231, 196, 122], brand: { bg: "#3a1a22", fg: "#e7c47a" }, schedule: "Tue · Thu · Sat 11:00 UTC",
  },
  {
    key: "escapevelocity", name: "Escape Velocity", short: "Escape Velocity", handle: "escapevelocitydaily",
    accent: [34, 211, 238], brand: { bg: "#0a1220", fg: "#22d3ee" }, schedule: "Mon · Thu · Sun 16:00 UTC",
  },
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
