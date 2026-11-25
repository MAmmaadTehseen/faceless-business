// Scale: circles whose diameters are proportional to value grow side by side
// on a baseline (smallest circle >= 24 px), labels + values under them.
import React from "react";
import {
  AbsoluteFill,
  Brand,
  PushIn,
  ScaleItem,
  clamp01,
  css,
  darkStroke,
  dim,
  easeOutCubic,
  fontFamilyFor,
  Title,
  uiScale,
  wrapFitted,
} from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";

const GROW_FRAMES = 30; // ~1 s
const MIN_D = 24; // minimum visible diameter in px (readable dot on phones)

export const Scale: React.FC<{
  title: string;
  items: ScaleItem[];
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ title, items, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const accent = brand.accent;
  const font = fontFamilyFor(brand);
  const maxVal = Math.max(...items.map((i) => i.value), 1e-9);

  const ui = uiScale(width, height);
  const minD = Math.max(MIN_D, 24 * ui);
  const bandTop = portrait ? height * 0.58 : height * 0.28;
  const bandH = portrait ? height * 0.32 : height * 0.44;
  const baseY = bandTop + bandH * 0.80;
  const maxD = bandH * 0.74;

  // Diameters strictly proportional to value, floored so the smallest stays
  // a readable >= 24 px disc with its value still shown.
  const dFinal = (v: number) => Math.max(minD, (v / maxVal) * maxD);

  const n = items.length;
  const slot = (width * 0.92) / Math.max(1, n);
  const cxAt = (i: number) => width * 0.5 + (i - (n - 1) / 2) * slot;

  const grow = (i: number) => easeOutCubic(clamp01((frame - i * 4) / GROW_FRAMES));

  const labelSize = Math.max(44, 44 * ui);
  const shownSize = Math.max(64, 64 * ui);

  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: css(brand.bg), fontFamily: font }}>
        <Title text={title} top={portrait ? height * 0.09 : height * 0.075} width={width} height={height} brand={brand} />
        {/* baseline */}
        <div
          style={{
            position: "absolute",
            left: width * 0.05,
            right: width * 0.05,
            top: baseY,
            height: Math.max(3, width / 540),
            background: css(accent, 0.35),
          }}
        />
        {items.map((item, i) => {
          const g = grow(i);
          const d = Math.max(minD * 0.9, dFinal(item.value) * g);
          const cx = cxAt(i);
          const cy = baseY - d / 2;
          const isLast = i === items.length - 1;
          const { lines: labelLines, fontSize: labelFs } = wrapFitted(
            item.label,
            slot * 0.96,
            labelSize,
            2,
            Math.max(40, 44 * ui),
          );
          return (
            <React.Fragment key={i}>
              <div
                style={{
                  position: "absolute",
                  left: cx - d / 2,
                  top: cy - d / 2,
                  width: d,
                  height: d,
                  borderRadius: "50%",
                  background: css(accent, isLast ? 0.42 : 0.24),
                  border: `${Math.max(3, width / 430)}px solid ${css(isLast ? accent : dim(accent))}`,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: cx - slot * 0.48,
                  width: slot * 0.96,
                  top: baseY + bandH * 0.045,
                  textAlign: "center",
                  opacity: clamp01(g * 1.8),
                }}
              >
                <div
                  style={{
                    fontSize: labelFs,
                    fontWeight: 700,
                    color: "#e7eaf0",
                    lineHeight: 1.12,
                  }}
                >
                  {labelLines.map((ln, k) => (
                    <div key={k}>{ln}</div>
                  ))}
                </div>
                <div
                  style={{
                    fontSize: shownSize,
                    fontWeight: 800,
                    color: css(accent),
                    textShadow: darkStroke(shownSize),
                    marginTop: labelSize * 0.12,
                    whiteSpace: "nowrap",
                  }}
                >
                  {item.shown}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </AbsoluteFill>
    </PushIn>
  );
};
