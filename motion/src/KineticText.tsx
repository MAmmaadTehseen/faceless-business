// KineticText: 1-8 words pop in one by one (scale 0.8 -> 1 + opacity, ~0.12 s
// apart); heavy font, 110-150 px on a 1080 px short side, fitted to the width
// with at most 3 lines. The key word (a digit, else the longest word) takes the
// accent colour; the rest are white. Portrait: text in the top 34 %.
import React from "react";
import {
  AbsoluteFill,
  Brand,
  PushIn,
  clamp01,
  css,
  fontFamilyFor,
  HEAVY_FONT,
  textWidth,
  uiScale,
  darkStroke,
} from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";

const POP_FRAMES = 9;
const GAP_FRAMES = 3.6; // ~0.12 s between word starts

/** Longest word, ties broken by first occurrence. */
const keyWordIndex = (words: string[]): number => {
  let best = 0;
  for (let i = 1; i < words.length; i++) {
    if (words[i].length > words[best].length) best = i;
  }
  return best;
};

export const KineticText: React.FC<{
  text: string;
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ text, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const accent = brand.accent;
  const words = text.split(/\s+/).filter(Boolean).slice(0, 8);
  const base = fontFamilyFor(brand);
  const heavy = brand.font ? `'${brand.font}', ${HEAVY_FONT}` : HEAVY_FONT;

  const stateOf = (i: number) => {
    const t = clamp01((frame - i * GAP_FRAMES) / POP_FRAMES);
    const ease = 1 - Math.pow(1 - t, 3);
    return { opacity: t, scale: 0.8 + 0.2 * ease };
  };

  const ui = uiScale(width, height);
  const keyIdx = words.findIndex((w) => /\d/.test(w));
  const accentIdx = keyIdx >= 0 ? keyIdx : words.length ? keyWordIndex(words) : 0;

  // Portrait: block occupies the top ~34 % (captions own 36-60 %).
  const blockTop = portrait ? height * 0.05 : height * 0.32;
  const blockH = portrait ? height * 0.28 : height * 0.36;
  const maxLines = portrait ? 3 : 2;

  // Fit to width: 110-150 px at a 1080 px short side, at most `maxLines` lines.
  // `simulate` reproduces the flex-wrap layout (greedy wrap + column gap) so
  // the chosen size provably fits both the width and the block height; if the
  // 110 px floor cannot fit, it wins anyway (never below 110).
  const avail = width * 0.88;
  const GAP = 0.3; // columnGap = fs * GAP
  const wordW = (w: string) => textWidth(w, 1, 0.62);
  const simulate = (fs: number): number => {
    let lines = 1;
    let cur = -1;
    for (const w of words) {
      const ww = wordW(w) * fs;
      if (cur < 0) {
        cur = ww;
      } else if (cur + GAP * fs + ww > avail) {
        lines++;
        cur = ww;
      } else {
        cur += GAP * fs + ww;
      }
    }
    return lines;
  };
  const heightOf = (fs: number, lines: number) =>
    lines * fs * 1.21 + (lines - 1) * 0.16 * fs;
  const totalW = words.reduce((s, w) => s + wordW(w), 0) + GAP * Math.max(0, words.length - 1);
  const longestW = Math.max(...words.map(wordW), 1e-6);
  const fit = Math.min(
    (avail * maxLines * 0.8) / Math.max(totalW, 1e-6),
    avail / longestW,
  );
  let fontSize = Math.min(150 * ui, Math.max(110 * ui, fit));
  for (let k = 0; k < 12; k++) {
    const lines = simulate(fontSize);
    if (lines <= maxLines && heightOf(fontSize, lines) <= blockH) break;
    const next = fontSize * 0.93;
    if (next <= 110 * ui) break;
    fontSize = next;
  }

  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: css(brand.bg), fontFamily: base }}>
        <div
          style={{
            position: "absolute",
            left: width * 0.06,
            right: width * 0.06,
            top: blockTop,
            height: blockH,
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignContent: "center",
            columnGap: `${fontSize * 0.3}px`,
            rowGap: `${fontSize * 0.16}px`,
            overflow: "hidden",
          }}
        >
          {words.map((w, i) => {
            const st = stateOf(i);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: st.opacity,
                  transform: `scale(${st.scale})`,
                  color: i === accentIdx ? css(accent) : "#fff",
                  fontSize,
                  fontWeight: 800,
                  letterSpacing: "-0.015em",
                  textShadow: darkStroke(fontSize),
                  whiteSpace: "nowrap",
                  fontFamily: heavy,
                }}
              >
                {w}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    </PushIn>
  );
};
