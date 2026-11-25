// Root: registers all compositions. Every composition reads width/height/seconds
// from input props via calculateMetadata, so one composition renders portrait
// 1080x1920 and landscape 1920x1080. Defaults make `npx remotion studio` work.
import React from "react";
import { Composition, registerRoot } from "remotion";
import { Chart } from "./Chart";
import { Map } from "./Map";
import { KineticText } from "./KineticText";
import { Timeline } from "./Timeline";
import { Scale } from "./Scale";
import { Orbit } from "./Orbit";
import { WordReveal } from "./WordReveal";
import { Brand, FPS } from "./lib";

const BRAND_TW: Brand = { accent: [231, 196, 122], bg: [14, 18, 26] };
const BRAND_EV: Brand = { accent: [34, 211, 238], bg: [10, 14, 24] };
const BRAND_TT: Brand = { accent: [167, 139, 250], bg: [20, 14, 36] };

interface DimensionsProps {
  width?: number;
  height?: number;
  seconds?: number;
}

/** Portrait 1080x1920 by default; the Python wrapper always passes explicit props. */
const calcMeta = <P extends DimensionsProps>(
  props: P,
): { width: number; height: number; durationInFrames: number } => ({
  width: props.width ?? 1080,
  height: props.height ?? 1920,
  durationInFrames: Math.max(1, Math.round((props.seconds ?? 3) * FPS)),
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Chart"
        component={Chart}
        schema={undefined}
        fps={FPS}
        defaultProps={{
          title: "War risk premium, % of ship value",
          items: [
            { label: "Before", value: 0.05, shown: "0.05%" },
            { label: "After", value: 0.5, shown: "0.5%" },
          ],
          brand: BRAND_TW,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
      <Composition
        id="Map"
        component={Map}
        fps={FPS}
        defaultProps={{
          countries: ["Iran", "Oman", "United Arab Emirates"],
          label: "Strait of Hormuz",
          brand: BRAND_TW,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
      <Composition
        id="KineticText"
        component={KineticText}
        fps={FPS}
        defaultProps={{
          text: "Watch the insurers, not the navies",
          brand: BRAND_TW,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
      <Composition
        id="Timeline"
        component={Timeline}
        fps={FPS}
        defaultProps={{
          title: "Voyager",
          events: [
            { when: "1977", label: "Launch" },
            { when: "1979", label: "Jupiter" },
            { when: "1980", label: "Saturn" },
            { when: "1990", label: "Pale Blue Dot" },
            { when: "2012", label: "Interstellar space" },
          ],
          brand: BRAND_EV,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
      <Composition
        id="Scale"
        component={Scale}
        fps={FPS}
        defaultProps={{
          title: "Earth vs Jupiter",
          items: [
            { label: "Earth", value: 12742, shown: "12,742 km" },
            { label: "Jupiter", value: 139820, shown: "139,820 km" },
          ],
          brand: BRAND_EV,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
      <Composition
        id="Orbit"
        component={Orbit}
        fps={FPS}
        defaultProps={{
          bodies: ["Earth", "Mars"],
          label: "Transfer to Mars",
          brand: BRAND_EV,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
      <Composition
        id="WordReveal"
        component={WordReveal}
        fps={FPS}
        defaultProps={{
          native: "水",
          romanisation: "shuǐ",
          language: "Chinese",
          script: "cjk",
          direction: "ltr",
          brand: BRAND_TT,
          width: 1080,
          height: 1920,
          seconds: 3,
        }}
        calculateMetadata={({ props }) => calcMeta(props)}
      />
    </>
  );
};

registerRoot(RemotionRoot);
