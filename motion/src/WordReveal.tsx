// WordReveal (Ten Tongues): the native word is revealed like handwriting by an
// animated mask wiping in the writing direction (right to left for rtl) over
// ~1.2 s, then the romanisation fades in below. System Noto fonts by family;
// nastaliq/arabic also load a bundled Nastaliq face (see lib.tsx).
import React from "react";
import {
  AbsoluteFill,
  Brand,
  PushIn,
  clamp01,
  css,
  ensureNastaliqFont,
  fontFamilyFor,
} from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";

const REVEAL_FRAMES = 36; // ~1.2 s wipe
const ROMAN_FRAMES = 12;

/** Scripts whose glyphs hang far below the baseline (Nastaliq stacks its
 * diacritic dots deep under the letters; Naskh vowel marks do the same), so
 * the default 1.9 x clip box would cut them off. */
const TALL_SCRIPTS = new Set(["nastaliq", "arabic"]);

export const WordReveal: React.FC<{
  native: string;
  romanisation: string;
  language: string;
  script: string;
  direction: "ltr" | "rtl";
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ native, romanisation, language, script, direction, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const rtl = direction === "rtl";
  const font = fontFamilyFor(brand, script);
  const accent = brand.accent;

  const revealT = clamp01(frame / REVEAL_FRAMES);
  const eased = 1 - Math.pow(1 - revealT, 2.2); // soft ease like a pen stroke
  const romanT = clamp01((frame - REVEAL_FRAMES) / ROMAN_FRAMES);

  const nativeSize = portrait ? width * 0.26 : height * 0.22;
  const romanSize = portrait ? width * 0.060 : height * 0.052;

  // Tall scripts get a deeper clip box (3.0 x nativeSize, lineHeight 2.0) so
  // Nastaliq's low-hanging dots are never cropped; everything else keeps the
  // original 1.9 x box. The taller box is centred on the original box's centre
  // so the baseline - and therefore the word's visual position - stays put.
  const tall = TALL_SCRIPTS.has(script);
  const nativeBoxH = nativeSize * (tall ? 3.0 : 1.9);
  const nativeLineHeight = tall ? 2.0 : 1.3;

  // Wipe mask: clip grows from the leading edge in the writing direction.
  const clipStyle: React.CSSProperties = rtl
    ? { clipPath: `inset(0px 0px 0px ${100 - eased * 100}%)` }
    : { clipPath: `inset(0px ${100 - eased * 100}% 0px 0px)` };

  const nativeTop = portrait ? height * 0.30 : height * 0.33;
  // Centre the (possibly taller) clip box on the original box's centre: the
  // baseline sits a fixed offset below the line-box centre ((asc+desc)/2, a
  // font property independent of lineHeight), so the word does not move.
  const nativeBoxTop = nativeTop + (nativeSize * 1.9 - nativeBoxH) / 2;
  const langOpacity = clamp01(frame / 10);
  // The nastaliq stack references the bundled local face (see lib.tsx).
  if (script === "nastaliq") ensureNastaliqFont();

  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: css(brand.bg), fontFamily: font }}>
        {/* language tag */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: portrait ? height * 0.115 : height * 0.15,
            textAlign: "center",
            fontSize: portrait ? width * 0.033 : height * 0.030,
            letterSpacing: "0.24em",
            textTransform: "uppercase",
            color: css(accent, 0.9),
            fontWeight: 700,
            opacity: langOpacity,
          }}
        >
          {language}
        </div>
        {/* native word, wiped in like handwriting */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: nativeBoxTop,
            height: nativeBoxH,
            ...clipStyle,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: nativeSize,
              fontWeight: 600,
              color: "#fff",
              lineHeight: nativeLineHeight,
              textShadow: "0 6px 30px rgba(0,0,0,0.55)",
              direction: rtl ? "rtl" : "ltr",
            }}
          >
            {native}
          </div>
        </div>
        {/* romanisation fades in below; anchored to the clip box bottom minus
         * the original 0.15 x gap, so tall scripts (deeper box) push it down
         * clear of the low Nastaliq descenders and everything else is
         * pixel-identical to the previous layout */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: nativeBoxTop + nativeBoxH - nativeSize * 0.15,
            textAlign: "center",
            fontSize: romanSize,
            color: css(accent),
            fontWeight: 700,
            letterSpacing: "0.04em",
            opacity: romanT,
          }}
        >
          {romanisation}
        </div>
      </AbsoluteFill>
    </PushIn>
  );
};
