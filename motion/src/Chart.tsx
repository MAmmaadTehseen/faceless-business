// Chart: bars grow with an eased spring (~0.9 s), value labels count up from 0
// to the final value formatted like `shown`. Last bar accented, others dimmed.
// Portrait: title in the top 30 %, bars only in the 64-94 % band (captions own 36-60 %).
// Landscape: vertical bars.
import React from "react";
import {
  AbsoluteFill,
  Brand,
  ChartItem,
  PushIn,
  Title,
  clamp01,
  css,
  darkStroke,
  dim,
  easeOutCubic,
  fontFamilyFor,
  formatCount,
  uiScale,
  wrapWords,
} from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";

const GROW_FRAMES = 27; // ~0.9 s at 30 fps
const COUNT_FRAMES = 27;
const STAGGER = 3; // frames between bar starts

/** Eased spring: ease-out-back with a small overshoot. */
const springGrow = (t: number): number => {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  const c1 = 1.70158;
  const c3 = c1 + 1;
  const base = 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  return Math.max(0, base);
};

export const Chart: React.FC<{
  title: string;
  items: ChartItem[];
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ title, items, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const font = fontFamilyFor(brand);
  const accent = brand.accent;
  const max = Math.max(...items.map((i) => i.value), 1e-9);

  const growth = (i: number) =>
    springGrow(clamp01((frame - i * STAGGER) / GROW_FRAMES));
  const countAt = (item: ChartItem, i: number) =>
    formatCount(item.shown, clamp01((frame - i * STAGGER) / COUNT_FRAMES));

  // ---- portrait: horizontal bars in the 64-94 % band ----
  if (portrait) {
    const ui = uiScale(width, height);
    const labelSize = Math.max(44, 45 * ui);
    const valueSize = Math.max(64, 66 * ui);
    const bandTop = height * 0.64;
    const bandH = height * 0.94 - bandTop;
    const rowH = bandH / items.length;
    const labelX = width * 0.05;
    const labelW = width * 0.26;
    const barX = labelX + labelW + width * 0.02;
    // Reserve room after the widest bar so its 64 px+ count-up label stays
    // on-frame (a 6-8 character value at 66 px bold is ~330 px).
    const barMaxW = width * 0.94 - barX - width * 0.20;
    // Smallest bar keeps 6 % of the max bar length so tiny values stay visible.
    const minBarW = barMaxW * 0.06;
    const barLen = (item: ChartItem) =>
      minBarW + ((item.value / max) * (barMaxW - minBarW));
    return (
      <PushIn frame={frame} durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ background: css(brand.bg), fontFamily: font }}>
          <Title text={title} top={height * 0.09} width={width} height={height} brand={brand} />
          {items.map((item, i) => {
            const g = growth(i);
            const w = barLen(item) * g;
            const isLast = i === items.length - 1;
            const rowTop = bandTop + i * rowH;
            const barH = Math.max(24 * ui, rowH * 0.32);
            const labelLines = wrapWords(item.label, labelW, labelSize);
            const shown = countAt(item, i);
            return (
              <React.Fragment key={i}>
                <div
                  style={{
                    position: "absolute",
                    left: labelX,
                    width: labelW,
                    top: rowTop + rowH * 0.5 - (labelLines.length * labelSize * 1.15) / 2,
                    fontSize: labelSize,
                    fontWeight: 700,
                    lineHeight: 1.15,
                    color: "#e7eaf0",
                  }}
                >
                  {labelLines.map((ln, k) => (
                    <div key={k}>{ln}</div>
                  ))}
                </div>
                <div
                  style={{
                    position: "absolute",
                    left: barX,
                    width: Math.max(4, w),
                    top: rowTop + rowH * 0.5 - barH / 2,
                    height: barH,
                    background: isLast ? css(accent) : css(dim(accent)),
                    borderRadius: `${barH * 0.5}px`,
                    borderTopLeftRadius: 0,
                    borderBottomLeftRadius: 0,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: barX + Math.max(4, w) + width * 0.018,
                    top: rowTop + rowH * 0.5 - valueSize * 0.62,
                    fontSize: valueSize,
                    fontWeight: 800,
                    color: isLast ? css(accent) : "#ffffff",
                    textShadow: darkStroke(valueSize),
                    whiteSpace: "nowrap",
                  }}
                >
                  {shown}
                </div>
              </React.Fragment>
            );
          })}
        </AbsoluteFill>
      </PushIn>
    );
  }

  // ---- landscape: vertical bars ----
  const ui = uiScale(width, height);
  const labelSize = Math.max(44, 44 * ui);
  const valueSize = Math.max(64, 64 * ui);
  const baseY = height * 0.82;
  const topY = height * 0.24;
  const maxH = baseY - topY;
  const pad = width * 0.09;
  const slot = (width - pad * 2) / items.length;
  const barW = Math.min(slot * 0.5, width * 0.14);
  const minBarH = maxH * 0.06;
  const barHeight = (item: ChartItem) =>
    minBarH + (item.value / max) * (maxH - minBarH);
  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: css(brand.bg), fontFamily: font }}>
        <Title text={title} top={height * 0.055} width={width} height={height} brand={brand} />
        {items.map((item, i) => {
          const g = growth(i);
          const h = barHeight(item) * g;
          const x = pad + slot * i + (slot - barW) / 2;
          const isLast = i === items.length - 1;
          return (
            <React.Fragment key={i}>
              <div
                style={{
                  position: "absolute",
                  left: x,
                  width: barW,
                  top: baseY - Math.max(4, h),
                  height: Math.max(4, h),
                  background: isLast ? css(accent) : css(dim(accent)),
                  borderRadius: `${barW * 0.14}px ${barW * 0.14}px 0 0`,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: x - slot * 0.2,
                  width: barW + slot * 0.4,
                  top: baseY - Math.max(4, h) - valueSize * 1.15,
                  textAlign: "center",
                  fontSize: valueSize,
                  fontWeight: 800,
                  color: isLast ? css(accent) : "#ffffff",
                  textShadow: darkStroke(valueSize),
                  whiteSpace: "nowrap",
                }}
              >
                {countAt(item, i)}
              </div>
              <div
                style={{
                  position: "absolute",
                  left: x - slot * 0.2,
                  width: barW + slot * 0.4,
                  top: baseY + height * 0.022,
                  textAlign: "center",
                  fontSize: labelSize,
                  fontWeight: 700,
                  lineHeight: 1.12,
                  color: "#e7eaf0",
                  opacity: 0.95,
                }}
              >
                {item.label}
              </div>
            </React.Fragment>
          );
        })}
        <div
          style={{
            position: "absolute",
            left: pad,
            right: pad,
            top: baseY,
            height: 2,
            background: css(accent, 0.3),
          }}
        />
      </AbsoluteFill>
    </PushIn>
  );
};

void easeOutCubic;
