// Orbit: Sun at centre, circular orbits for the known planets on a sqrt scale
// so they fit; each planet is a >= 26 px disc with a following >= 40 px name
// label, moving along its orbit with angular speed proportional to r^-1.5
// (sped up for visibility). Orbit lines are 2-3 px at 50 % white. With two
// planets also draw a dashed transfer ellipse with a bright travelling dot.
// Earth+Moon only: centre on Earth with the Moon orbiting. No numbers shown.
// Portrait: the diagram fills most of the 64-94 % band (captions own 36-60 %).
import React from "react";
import { AbsoluteFill, Brand, PushIn, clamp01, css, fontFamilyFor, uiScale } from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";

// Semi-major axes in AU.
const AU: Record<string, number> = {
  mercury: 0.39,
  venus: 0.72,
  earth: 1,
  mars: 1.52,
  jupiter: 5.2,
  saturn: 9.58,
  uranus: 19.2,
  neptune: 30.1,
};
const MOON = "moon";

// Relative display dot radius per planet (floored at 13 px at a 1080 px short
// side so every planet stays a >= 26 px disc on phones).
const DOT_R: Record<string, number> = {
  mercury: 8, venus: 11, earth: 13, mars: 10, jupiter: 26, saturn: 22, uranus: 17, neptune: 16,
  [MOON]: 9,
};

// Angular speed constant: omega = K * r_AU^-1.5, sped up ~3 orders of magnitude.
const OMEGA_K = 2.0; // rad per second at 1 AU

const titleCase = (n: string): string =>
  n === MOON ? "Moon" : n.charAt(0).toUpperCase() + n.slice(1);

export const Orbit: React.FC<{
  bodies: string[];
  label: string;
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ bodies, label, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const accent = brand.accent;
  const font = fontFamilyFor(brand);
  const ui = uiScale(width, height);

  const names = bodies.map((b) => (b || "").trim().toLowerCase()).filter(Boolean);
  const earthMoonOnly = names.length === 2 && names.includes("earth") && names.includes(MOON);

  // Portrait: the label sits in the top title zone (like every other
  // composition) so the diagram alone owns the 64-94 % band; landscape: top.
  const cx = width / 2;
  const cy = portrait ? height * 0.7875 : height * 0.55;
  const maxR = portrait
    ? Math.min(width * 0.44, height * 0.135)
    : Math.min(width * 0.42, height * 0.36);

  // Orbit radii: sqrt scale of AU so outer planets fit.
  const auOf = (n: string): number | undefined =>
    n === MOON ? undefined : AU[n];

  const planetNames = names.filter((n) => AU[n] !== undefined);
  const maxAu = Math.max(1, ...planetNames.map((n) => AU[n]));
  const orbitR = (au: number) => (Math.sqrt(au) / Math.sqrt(maxAu)) * maxR;

  // Earth+Moon mode: centre on Earth (a big dot, no Sun), Moon on a local orbit.
  const moonOrbitR = Math.max(72, maxR * 0.32);
  const earthDotR = Math.max(30, maxR * 0.16);

  const orbits = names.map((n) => {
    if (earthMoonOnly && n === MOON) return { name: n, r: moonOrbitR, au: 0, isMoon: true };
    const au = auOf(n);
    if (au === undefined) return null;
    return { name: n, r: orbitR(au), au, isMoon: false };
  }).filter(
    (o): o is { name: string; r: number; au: number; isMoon: boolean } => o !== null,
  );

  // Angle: omega proportional to r_AU^-1.5 (Kepler's third law), sped up for
  // visibility. The Moon uses its real ratio (0.00257 AU) with a display floor
  // so it visibly circles Earth several times per clip.
  const angleAt = (o: { name: string; r: number; au: number; isMoon: boolean }, i: number): number => {
    if (o.isMoon) {
      const omegaMoon = OMEGA_K * Math.pow(0.00257, -1.5) * 0.0009; // readable speed
      return omegaMoon * (frame / 30);
    }
    const omega = OMEGA_K * Math.pow(o.au, -1.5);
    return omega * (frame / 30) + i * 2.1;
  };

  // Transfer ellipse for two planets: periapsis on the inner orbit, apoapsis on
  // the outer. The dot departs the inner body's position and sweeps 180 deg.
  const transfer = (() => {
    if (names.length !== 2 || earthMoonOnly) return null;
    const [a, b] = orbits;
    if (!a || !b) return null;
    const r1 = Math.min(a.r, b.r);
    const r2 = Math.max(a.r, b.r);
    const aEll = (r1 + r2) / 2;
    const bEll = Math.sqrt(r1 * r2);
    const startF = 26;
    const travelF = 50;
    const tt = clamp01((frame - startF) / travelF);
    const inner = a.r <= b.r ? a : b;
    const theta0 = angleAt(inner, 0);
    // Ellipse with focus at the Sun; polar form r(theta) about the focus.
    const rel = tt * Math.PI; // half transfer
    const c = Math.sqrt(aEll * aEll - bEll * bEll); // focus offset
    const ex = aEll * Math.cos(rel) - c;
    const ey = bEll * Math.sin(rel);
    const rr = Math.sqrt(ex * ex + ey * ey);
    const theta = theta0 + Math.atan2(ey, ex);
    return { aEll, bEll, theta0, tt, rr, theta, c };
  })();

  const fadeIn = clamp01(frame / 12);
  const labelOpacity = clamp01((frame - 14) / 14);
  // Orbit lines: 2-3 px white at 50 % opacity.
  const lineW = Math.min(3, Math.max(2, ui * 2.4));
  // Sun: a large glowing accent disc (solid core + three halo rings).
  const sunR = Math.max(34, maxR * 0.17);
  // Planets: >= 26 px discs with >= 40 px name labels.
  const nameSize = Math.max(40, 44 * ui);
  const dotR = (n: string) => Math.max(13, (DOT_R[n] ?? 9) * ui);
  const labelSize = Math.max(72, 78 * ui);
  const textStroke = {
    stroke: "rgba(3, 5, 10, 0.85)",
    strokeWidth: nameSize * 0.14,
    paintOrder: "stroke" as const,
    strokeLinejoin: "round" as const,
  };

  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: css(brand.bg), fontFamily: font }}>
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          style={{ position: "absolute", top: 0, left: 0 }}
        >
          {/* orbit circles: 2-3 px, 50 % white */}
          {orbits.map((o) => (
            <circle
              key={o.name}
              cx={cx}
              cy={cy}
              r={o.r}
              fill="none"
              stroke="#ffffff"
              strokeOpacity={0.5 * fadeIn}
              strokeWidth={lineW}
            />
          ))}
          {/* transfer ellipse: dashed accent */}
          {transfer && (
            <ellipse
              cx={cx - transfer.c * Math.cos(transfer.theta0)}
              cy={cy - transfer.c * Math.sin(transfer.theta0)}
              rx={transfer.aEll}
              ry={transfer.bEll}
              fill="none"
              stroke={css(accent, 0.85)}
              strokeWidth={Math.max(2.5, ui * 3)}
              strokeDasharray={`${Math.max(10, transfer.aEll * 0.14)} ${Math.max(8, transfer.aEll * 0.10)}`}
              transform={`rotate(${(transfer.theta0 * 180) / Math.PI} ${cx - transfer.c * Math.cos(transfer.theta0)} ${cy - transfer.c * Math.sin(transfer.theta0)})`}
              opacity={clamp01((frame - 20) / 12)}
            />
          )}
          {/* the Sun (skipped in Earth+Moon mode: Earth is the central body) */}
          {!earthMoonOnly && (
            <>
              <circle cx={cx} cy={cy} r={sunR * 2.6} fill={css(accent, 0.08 * fadeIn)} />
              <circle cx={cx} cy={cy} r={sunR * 1.85} fill={css(accent, 0.14 * fadeIn)} />
              <circle cx={cx} cy={cy} r={sunR * 1.3} fill={css(accent, 0.22 * fadeIn)} />
              <circle cx={cx} cy={cy} r={sunR} fill={css(accent)} />
              <circle cx={cx} cy={cy} r={sunR * 0.72} fill={css(accent, 0.55)} />
            </>
          )}
          {earthMoonOnly && (
            <>
              <circle cx={cx} cy={cy} r={earthDotR * 2.0} fill={css(accent, 0.10 * fadeIn)} />
              <circle cx={cx} cy={cy} r={earthDotR * 1.4} fill={css(accent, 0.18 * fadeIn)} />
              <circle cx={cx} cy={cy} r={earthDotR} fill="#fff" />
              <circle cx={cx} cy={cy} r={earthDotR * 0.7} fill={css(accent, 0.85)} />
              <text
                x={cx}
                y={cy - earthDotR - nameSize * 0.35}
                textAnchor="middle"
                fill="#fff"
                fontSize={nameSize}
                fontWeight={700}
                opacity={fadeIn}
                fontFamily="'Noto Sans', 'DejaVu Sans', sans-serif"
                {...textStroke}
              >
                Earth
              </text>
            </>
          )}
          {/* planets / moon: discs + following name labels */}
          {orbits.map((o, i) => {
            const th = angleAt(o, i);
            const px = cx + o.r * Math.cos(th);
            const py = cy + o.r * Math.sin(th);
            const d = dotR(o.name);
            const appear = clamp01((frame - 4 - i * 3) / 10);
            const flip = px > width * 0.72;
            return (
              <g key={o.name} opacity={appear}>
                <circle cx={px} cy={py} r={d * 1.9} fill={css(accent, 0.25)} />
                <circle cx={px} cy={py} r={d} fill="#fff" />
                <circle cx={px} cy={py} r={d * 0.55} fill={css(accent, 0.9)} />
                <text
                  x={flip ? px - d - nameSize * 0.22 : px + d + nameSize * 0.22}
                  y={py + nameSize * 0.35}
                  textAnchor={flip ? "end" : "start"}
                  fill="#fff"
                  fontSize={nameSize}
                  fontWeight={700}
                  fontFamily="'Noto Sans', 'DejaVu Sans', sans-serif"
                  {...textStroke}
                >
                  {titleCase(o.name)}
                </text>
              </g>
            );
          })}
          {/* transfer dot: bright, travels the dashed ellipse */}
          {transfer && transfer.tt > 0 && transfer.tt < 1 && (
            <>
              <circle
                cx={cx + transfer.rr * Math.cos(transfer.theta)}
                cy={cy + transfer.rr * Math.sin(transfer.theta)}
                r={Math.max(9, ui * 11)}
                fill={css(accent, 0.35)}
              />
              <circle
                cx={cx + transfer.rr * Math.cos(transfer.theta)}
                cy={cy + transfer.rr * Math.sin(transfer.theta)}
                r={Math.max(6, ui * 7)}
                fill="#fff"
                stroke={css(accent)}
                strokeWidth={Math.max(2, ui * 2.5)}
              />
            </>
          )}
          {/* label (no numbers) */}
          <text
            x={width / 2}
            y={portrait ? height * 0.15 : height * 0.105}
            textAnchor="middle"
            fill="#fff"
            fontSize={labelSize}
            fontWeight={800}
            opacity={labelOpacity}
            fontFamily="'Noto Sans', 'DejaVu Sans', sans-serif"
            stroke="rgba(3, 5, 10, 0.85)"
            strokeWidth={labelSize * 0.12}
            paintOrder="stroke"
            strokeLinejoin="round"
          >
            {label}
          </text>
        </svg>
      </AbsoluteFill>
    </PushIn>
  );
};
