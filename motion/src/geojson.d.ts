// Type declaration for the bundled geojson import in Map.tsx (resolveJsonModule
// types JSON as structural modules; this keeps the feature type narrow).
declare module "*.geojson" {
  const value: {
    type: string;
    features: {
      geometry: { type: string; coordinates: number[][][] | number[][][][] };
      properties: Record<string, string | undefined>;
    }[];
  };
  export default value;
}
