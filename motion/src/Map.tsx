// Map: equirectangular world SVG. Starts at a wide world view, zooms over
// ~1.2 s to the highlighted countries' bounding box (min 30 deg wide); the
// highlighted countries fade from land grey to the accent. Portrait puts the
// focus at 74 % of the height with the label at 88 %; landscape is centred.
import React from "react";
import { AbsoluteFill, Brand, PushIn, SEA, LAND, clamp01, css, fontFamilyFor } from "./lib";
import { useCurrentFrame, useVideoConfig } from "remotion";
import geo from "../public/ne_110m_countries.geojson";

const ALIASES: Record<string, string> = {
  us: "united states of america",
  usa: "united states of america",
  "united states": "united states of america",
  america: "united states of america",
  uk: "united kingdom",
  britain: "united kingdom",
  "great britain": "united kingdom",
  england: "united kingdom",
  korea: "south korea",
  uae: "united arab emirates",
  emirates: "united arab emirates",
  congo: "dem. rep. congo",
  drc: "dem. rep. congo",
  "czech republic": "czechia",
  holland: "netherlands",
  "the netherlands": "netherlands",
  "ivory coast": "côte d'ivoire",
};

const EU = [
  "austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia", "denmark",
  "estonia", "finland", "france", "germany", "greece", "hungary", "ireland",
  "italy", "latvia", "lithuania", "luxembourg", "netherlands", "poland",
  "portugal", "romania", "slovakia", "slovenia", "spain", "sweden",
];

interface Feature {
  geometry: { type: string; coordinates: number[][][] | number[][][][] };
  properties: Record<string, string | undefined>;
}

const features = (geo as unknown as { features: Feature[] }).features;

const namesOf = (f: Feature): Set<string> => {
  const p = f.properties || {};
  const out = new Set<string>();
  for (const k of ["NAME", "NAME_LONG", "ADMIN", "NAME_EN", "ISO_A3"]) {
    const v = p[k];
    if (v) out.add(String(v).toLowerCase());
  }
  return out;
};

const ringsOf = (f: Feature): [number, number][][] => {
  const g = f.geometry;
  if (g.type === "Polygon") return [g.coordinates[0] as [number, number][]];
  return (g.coordinates as number[][][][]).map((poly) => poly[0] as [number, number][]);
};

const matchCountries = (countries: string[]): Set<Feature> => {
  const wanted = new Set<string>();
  for (const raw of countries) {
    const c = (raw || "").trim().toLowerCase();
    if (!c) continue;
    if (c === "eu" || c === "european union" || c === "europe") {
      EU.forEach((e) => wanted.add(e));
    } else {
      wanted.add(ALIASES[c] ?? c);
    }
  }
  const hits = new Set<Feature>();
  for (const f of features) {
    const names = namesOf(f);
    for (const w of wanted) {
      if (names.has(w)) {
        hits.add(f);
        break;
      }
    }
  }
  return hits;
};

// Wide world view with a little padding.
const WORLD: [number, number, number, number] = [-175, -58, 180, 82];

const ZOOM_FRAMES = 36; // ~1.2 s

type Box = [number, number, number, number]; // lon0, lat0, lon1, lat1

export const Map: React.FC<{
  countries: string[];
  label: string;
  brand: Brand;
  width?: number;
  height?: number;
  seconds?: number;
}> = ({ countries, label, brand }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const portrait = height > width;
  const font = fontFamilyFor(brand);
  const accent = brand.accent;

  const hits = matchCountries(countries);
  const zoomT = 1 - Math.pow(1 - clamp01(frame / ZOOM_FRAMES), 3);

  // Target view: bbox of the highlighted countries (min 30 deg wide), aspect-fit.
  let target: Box = WORLD;
  const xs: number[] = [];
  const ys: number[] = [];
  hits.forEach((f) => {
    for (const ring of ringsOf(f)) {
      for (const [lon, lat] of ring) {
        if (lon < -170 || lon > 179) continue; // antimeridian slivers
        xs.push(lon);
        ys.push(lat);
      }
    }
  });
  if (xs.length) {
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const spanX = Math.max(Math.max(...xs) - Math.min(...xs), 30);
    const spanY = Math.max(Math.max(...ys) - Math.min(...ys), 30 * (height / width));
    const ratio = width / height;
    let sx = spanX * 1.5;
    let sy = spanY * 1.5;
    if (sx / sy > ratio) sy = sx / ratio;
    else sx = sy * ratio;
    target = [cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2];
  }

  const mix = (a: number, b: number): number => a + (b - a) * zoomT;
  const cur: Box = [
    mix(WORLD[0], target[0]),
    mix(WORLD[1], target[1]),
    mix(WORLD[2], target[2]),
    mix(WORLD[3], target[3]),
  ];
  const spanLon = cur[2] - cur[0];
  const spanLat = cur[3] - cur[1];

  // Focus point: centre of the target bbox.
  const fx = (target[0] + target[2]) / 2;
  const fy = (target[1] + target[3]) / 2;

  // Portrait: focus lands at 74 % of the height, landscape: 50 %.
  const focusYFrac = portrait ? 0.74 : 0.5;
  // lon0/lat1 such that (fx, fy) projects to (50 %, focusYFrac).
  const lon0 = fx - spanLon / 2;
  const lat1 = fy + spanLat * (1 - focusYFrac);

  const proj = (lon: number, lat: number): [number, number] => [
    ((lon - lon0) / spanLon) * width,
    ((lat1 - lat) / spanLat) * height,
  ];

  const seaFill = css(SEA);
  const landFill = css(LAND);
  // Highlighted countries fade from land grey to accent as the zoom lands.
  const mixc = (a: number, b: number, t: number) => a + (b - a) * t;
  const hl = LAND.map((v, i) => mixc(v, accent[i], Math.min(1, 0.15 + 0.85 * zoomT))) as [
    number,
    number,
    number,
  ];
  const highlightFill = css(hl);

  const labelOpacity = clamp01((frame - ZOOM_FRAMES) / 15);
  const text = label || countries.join(", ");

  return (
    <PushIn frame={frame} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ background: seaFill }}>
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          style={{ position: "absolute", top: 0, left: 0 }}
        >
          {features.map((f, fi) => {
            const isHit = hits.has(f);
            return (
              <g key={fi}>
                {ringsOf(f).map((ring, ri) => {
                  const pts = ring
                    .map(([lon, lat]) => proj(lon, lat).join(","))
                    .join(" ");
                  return (
                    <polygon
                      key={ri}
                      points={pts}
                      fill={isHit ? highlightFill : landFill}
                      stroke={
                        isHit
                          ? css(accent, 0.85)
                          : css([96, 110, 136])
                      }
                      strokeWidth={isHit ? Math.max(1.5, width / 540) : 0.7}
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
        <div
          style={{
            position: "absolute",
            left: width * 0.06,
            right: width * 0.06,
            top: portrait ? undefined : height * 0.05,
            bottom: portrait ? height * 0.115 : undefined,
            textAlign: "center",
            fontSize: portrait ? width * 0.055 : height * 0.05,
            fontWeight: 800,
            color: "#fff",
            textShadow: "0 2px 14px rgba(0,0,0,0.7)",
            fontFamily: font,
            opacity: labelOpacity,
          }}
        >
          {text}
        </div>
      </AbsoluteFill>
    </PushIn>
  );
};
