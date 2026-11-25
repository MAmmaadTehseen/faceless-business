// Timeline: a line draws left to right; each event's dot and labels pop in as
// the line reaches it. Portrait: band 64-94 % of the height, title in the top.
// Labels wrap to at most 2 lines and are never truncated; 8 % side padding
// keeps the first/last label blocks inside the frame.
import React from "react";
import {
  AbsoluteFill,
  Brand,
  PushIn,
  TimelineEvent,
  clamp01,
  css,
  darkStroke,
  easeOutCubic,
  fontFamilyFor,
  Title,
  uiScale,
  wrapFitted,
} from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";

const DRAW_FRAMES = 45; // ~1.5 s line draw
const POP_FRAMES = 9;

export const Timeline: React.FC<{
  title: string;
  events: TimelineEvent[];
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ title, events, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const accent = brand.accent;
  const font = fontFamilyFor(brand);
  const n = events.length;
  const drawT = clamp01(frame / DRAW_FRAMES);

  const bandTop = portrait ? height * 0.64 : height * 0.50;
  const bandH = portrait ? height * 0.30 : height * 0.32;
  const lineY = bandTop + bandH * 0.42;
  // 8 % side padding so the first/last label blocks stay inside the frame.
  const left = width * 0.08;
  const right = width - width * 0.08;
  const span = right - left;
  const xAt = (i: number) => left + (span * i) / Math.max(1, n - 1);

  const eventT = (i: number) =>
    clamp01((frame - (i / Math.max(1, n - 1)) * DRAW_FRAMES) / POP_FRAMES);

  const ui = uiScale(width, height);
  const dotR = portrait ? Math.max(14, 16 * ui) : Math.max(12, 13 * ui);
  const whenSize = Math.max(56, 60 * ui); // years: accent, >= 56 px
  const labelSize = Math.max(44, 44 * ui);

  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: css(brand.bg), fontFamily: font }}>
        <Title text={title} top={portrait ? height * 0.09 : height * 0.10} width={width} height={height} brand={brand} />
        {/* track */}
        <div
          style={{
            position: "absolute",
            top: lineY - Math.max(1.5, height / 720),
            left,
            width: span,
            height: Math.max(3, height / 360),
            background: css(accent, 0.18),
            borderRadius: 999,
          }}
        />
        {/* drawn line */}
        <div
          style={{
            position: "absolute",
            top: lineY - Math.max(1.5, height / 720),
            left,
            width: Math.max(4, span * drawT),
            height: Math.max(3, height / 360),
            background: css(accent),
            borderRadius: 999,
          }}
        />
        {events.map((e, i) => {
          const t = eventT(i);
          const x = xAt(i);
          const above = i % 2 === 0;
          const scale = 0.6 + 0.4 * easeOutCubic(t);
          // Wrap to ~2 lines, never truncate; clamp outer label blocks inside
          // the 8 % side padding.
          const labelBlockW = portrait ? width * 0.30 : width * 0.16;
          const blockLeft = Math.min(
            Math.max(x - labelBlockW / 2, width * 0.08),
            width * 0.92 - labelBlockW,
          );
          const { lines: labelLines, fontSize: labelFs } = wrapFitted(
            e.label,
            labelBlockW,
            labelSize,
            2,
            Math.max(40, 44 * ui),
          );
          const labelBlockH = whenSize * 1.1 + labelSize * 1.15 * labelLines.length + labelSize * 0.15;
          return (
            <React.Fragment key={i}>
              <div
                style={{
                  position: "absolute",
                  left: x - dotR,
                  top: lineY - dotR,
                  width: dotR * 2,
                  height: dotR * 2,
                  borderRadius: "50%",
                  background: css(accent),
                  opacity: t,
                  transform: `scale(${scale})`,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: blockLeft,
                  width: labelBlockW,
                  top: above
                    ? lineY - dotR - height * 0.012 - labelBlockH
                    : lineY + dotR + height * 0.014,
                  height: labelBlockH,
                  textAlign: "center",
                  opacity: t,
                  transform: `scale(${scale})`,
                  transformOrigin: above ? "bottom center" : "top center",
                }}
              >
                <div
                  style={{
                    fontSize: whenSize,
                    fontWeight: 800,
                    color: css(accent),
                    textShadow: darkStroke(whenSize),
                    whiteSpace: "nowrap",
                  }}
                >
                  {e.when}
                </div>
                <div
                  style={{
                    fontSize: labelFs,
                    fontWeight: 600,
                    color: "#e7eaf0",
                    lineHeight: 1.15,
                    marginTop: labelSize * 0.15,
                  }}
                >
                  {labelLines.map((ln, k) => (
                    <div key={k}>{ln}</div>
                  ))}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </AbsoluteFill>
    </PushIn>
  );
};
