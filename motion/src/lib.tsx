// Shared prop types + helpers for every composition.
import React from "react";
import { continueRender, delayRender, staticFile } from "remotion";

export const FPS = 30;

export interface Brand {
  accent: [number, number, number];
  bg: [number, number, number];
  font?: string;
  /** File in motion/public/fonts (copied from assets/fonts/ofl) loaded as `font`. */
  fontFile?: string;
}

export interface ChartItem {
  label: string;
  value: number;
  shown: string;
}

export interface TimelineEvent {
  when: string;
  label: string;
}

export interface ScaleItem {
  label: string;
  value: number;
  shown: string;
}

export const css = (c: [number, number, number], alpha = 1): string =>
  `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${alpha})`;

/** Dimmed accent for non-highlight bars / land shapes (mix with land grey). */
export const dim = (c: [number, number, number]): [number, number, number] => [
  Math.round(c[0] * 0.45 + 66 * 0.55),
  Math.round(c[1] * 0.45 + 80 * 0.55),
  Math.round(c[2] * 0.45 + 104 * 0.55),
];

export const SEA: [number, number, number] = [8, 12, 22];
export const LAND: [number, number, number] = [66, 80, 104];

/** ease-out cubic: fast start, soft landing. */
export const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

/** clamp helper */
export const clamp01 = (t: number): number => Math.min(1, Math.max(0, t));

/**
 * Count-up formatting: "0.05%" -> "0.03%", "14,000" -> "9,214",
 * "$2.1B" -> "$0.8B". Keeps any non-numeric prefix/suffix, counts the numeric
 * core, preserves the decimal places and grouping of the final `shown` text.
 * Integers keep thousands grouping; decimals and compact suffixes pass through.
 */
export const formatCount = (shown: string, progress: number): string => {
  const m = shown.match(/^(.*?)([\d,]+(?:\.\d+)?)(.*)$/s);
  if (!m) return shown;
  const [, pre, num, post] = m;
  const decimals = num.includes(".") ? num.split(".")[1].length : 0;
  const target = parseFloat(num.replace(/,/g, ""));
  const cur = target * clamp01(progress);
  const body =
    decimals > 0
      ? cur.toFixed(decimals)
      : Math.round(cur).toLocaleString("en-US");
  return `${pre}${body}${post}`;
};

/**
 * Push-in wrapper: after the main animation a slow 3-4 % scale-up keeps every
 * frame moving so the QA freeze detector (4 s+) never sees a still frame.
 */
export const PushIn: React.FC<{
  children: React.ReactNode;
  frame: number;
  durationInFrames: number;
  amount?: number;
}> = ({ children, frame, durationInFrames, amount = 0.035 }) => {
  const t = clamp01(frame / Math.max(1, durationInFrames - 1));
  const z = 1 + amount * t;
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        overflow: "hidden",
        transform: `scale(${z})`,
        transformOrigin: "center center",
      }}
    >
      {children}
    </div>
  );
};

export const AbsoluteFill: React.FC<React.ComponentProps<"div">> = (props) => (
  <div
    {...props}
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      overflow: "hidden",
      ...props.style,
    }}
  />
);

// Font stacks by script; the runner installs fonts-noto-core/cjk/extra so the
// families resolve locally. Missing families fall through the chain.
export const FONT_STACKS: Record<string, string> = {
  cjk: "'Noto Sans CJK SC', 'Noto Sans CJK JP', 'Noto Sans', sans-serif",
  jp: "'Noto Sans CJK JP', 'Noto Sans CJK SC', 'Noto Sans', sans-serif",
  devanagari: "'Noto Sans Devanagari', 'Noto Sans', sans-serif",
  nastaliq: "'Noto Nastaliq Urdu Local', 'Noto Nastaliq Urdu', 'Noto Naskh Arabic', 'Noto Sans', sans-serif",
  latin: "'Noto Sans', 'DejaVu Sans', sans-serif",
};

// Locally bundled Nastaliq face (SIL OFL 1.1; same file the Debian
// fonts-noto-core package installs). Headless Chrome does not reliably
// resolve the system 'Noto Nastaliq Urdu' family and falls back to Naskh,
// which reshapes the word, so the bundled face is placed first in the
// nastaliq stack. delayRender waits for it so the first rendered frame
// already uses it; on failure it falls through to the system stack.
let nastaliqFaceStarted = false;
export const ensureNastaliqFont = (): void => {
  if (nastaliqFaceStarted) return;
  nastaliqFaceStarted = true;
  const handle = delayRender("Loading Noto Nastaliq Urdu Local font");
  const face = new FontFace(
    "Noto Nastaliq Urdu Local",
    `url('${staticFile("fonts/NotoNastaliqUrdu-Bold.ttf")}') format('truetype')`,
    { weight: "700" },
  );
  document.fonts.add(face);
  face
    .load()
    .then(() => continueRender(handle))
    .catch(() => continueRender(handle)); // fall through to the system stack
};

// Channel headline font (owner-approved per channel). Loaded once per bundle page with
// delayRender so the first frame already uses it; on failure the stack falls through.
const brandFacesStarted = new Set<string>();
export const ensureBrandFont = (brand?: Brand): void => {
  if (!brand?.font || !brand.fontFile || brandFacesStarted.has(brand.font)) return;
  brandFacesStarted.add(brand.font);
  const handle = delayRender(`Loading ${brand.font}`);
  const face = new FontFace(
    brand.font,
    `url('${staticFile(`fonts/${brand.fontFile}`)}') format('truetype')`,
  );
  document.fonts.add(face);
  face
    .load()
    .then(() => continueRender(handle))
    .catch(() => continueRender(handle));
};

export const fontFamilyFor = (brand?: Brand, script?: string): string => {
  ensureBrandFont(brand);
  const stack = script && FONT_STACKS[script] ? FONT_STACKS[script] : FONT_STACKS.latin;
  return brand?.font ? `'${brand.font}', ${stack}` : stack;
};

/** Heavy display font for kinetic text / titles. */
export const HEAVY_FONT =
  "'Noto Sans', 'Noto Sans Display', 'DejaVu Sans', sans-serif";

export const TITLE_FONT = "'Noto Sans', 'DejaVu Sans', sans-serif";

/**
 * UI scale: every authored size targets a 1080 px short side (1080x1920
 * portrait, 1920x1080 landscape), so the same number reads identically in
 * both orientations. Scale sizes by this, never by width alone.
 */
export const uiScale = (width: number, height: number): number =>
  Math.min(width, height) / 1080;

/** Approximate rendered width of `text` at `fontSize` (Noto Sans bold-ish). */
export const textWidth = (
  text: string,
  fontSize: number,
  charW = 0.55,
): number => text.length * fontSize * charW;

/** Greedy word wrap by estimated width; never truncates. The default char
 *  width (0.58 em) is deliberately conservative for Noto Sans bold so a
 *  predicted line never overflows the real font. */
export const wrapWords = (
  text: string,
  maxWidth: number,
  fontSize: number,
  charW = 0.58,
  spaceW = 0.32,
): string[] => {
  const width = (s: string): number => {
    const words = s.split(" ");
    const letters = words.reduce((n, w) => n + w.length, 0);
    const gaps = Math.max(0, words.length - 1);
    return (letters * charW + gaps * spaceW) * fontSize;
  };
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";
  for (const w of words) {
    const candidate = line ? `${line} ${w}` : w;
    if (line && width(candidate) > maxWidth) {
      lines.push(line);
      line = w;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
};

/**
 * Dark outline for big value text: a tight ring of shadows renders in every
 * Chrome build Remotion uses (no paint-order dependency).
 */
export const darkStroke = (fontSize: number): string => {
  const r = Math.max(2, fontSize * 0.05);
  const a = "rgba(3, 5, 10, 0.85)";
  const parts: string[] = [];
  for (let k = 0; k < 12; k++) {
    const th = (k / 12) * Math.PI * 2;
    parts.push(
      `${(r * Math.cos(th)).toFixed(2)}px ${(r * Math.sin(th)).toFixed(2)}px 0 ${a}`,
    );
  }
  return parts.join(", ");
};

/**
 * Wrap to at most `maxLines` lines without ever truncating: shrink the font
 * within [floor, size] until the text fits; if it still needs more lines at
 * the floor, every wrapped line still renders (nothing is cut off).
 */
export const wrapFitted = (
  text: string,
  maxWidth: number,
  size: number,
  maxLines: number,
  floor: number,
): { lines: string[]; fontSize: number } => {
  let s = size;
  let lines = wrapWords(text, maxWidth, s);
  while (lines.length > maxLines && s > floor + 0.5) {
    s = Math.max(floor, s * 0.9);
    lines = wrapWords(text, maxWidth, s);
  }
  return { lines, fontSize: s };
};

/** Shared title: >= 72 px bold at a 1080 px short side, wrapped to fit the
 *  width; long titles shrink towards the 72 px floor to stay in two lines and
 *  never truncate. */
export const Title: React.FC<{
  text: string;
  top: number;
  width: number;
  height: number;
  brand?: Brand;
}> = ({ text, top, width, height, brand }) => {
  const s = uiScale(width, height);
  const avail = width * 0.88;
  const floor = 72 * s;
  const size = Math.min(84 * s, Math.max(floor, (avail * 2) / (0.62 * Math.max(1, text.length))));
  const { lines } = wrapFitted(text, avail, size, 2, floor);
  return (
    <div
      style={{
        position: "absolute",
        left: width * 0.06,
        right: width * 0.06,
        top,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        fontSize: size,
        lineHeight: 1.2,
        fontWeight: 800,
        color: "#fff",
        fontFamily: brand?.font ? fontFamilyFor(brand) : TITLE_FONT,
      }}
    >
      <div>
        {lines.map((ln, k) => (
          <div key={k}>{ln}</div>
        ))}
      </div>
    </div>
  );
};
