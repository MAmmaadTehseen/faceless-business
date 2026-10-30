import { channelMeta } from "./channels";

// Ordered to keep adjacent series distinguishable; labels and stripes also identify series.
export const SERIES_PALETTE = [
  "#ff9f43",
  "#a3e635",
  "#fb7185",
  "#60a5fa",
  "#c4a0ff",
  "#22d3ee",
  "#fde047",
  "#2dd4bf",
] as const;
export function seriesColor(name: string, index: number): string {
  return (
    channelMeta(name)?.brand.fg ?? SERIES_PALETTE[index % SERIES_PALETTE.length]
  );
}
