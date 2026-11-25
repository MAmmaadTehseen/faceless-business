// Remotion config: teach the bundler to inline .geojson imports as JSON so
// Map.tsx can read the country outlines without a fetch or staticFile dance.
import { Config } from "@remotion/cli/config";

Config.overrideWebpackConfig((config) => {
  return {
    ...config,
    module: {
      ...config.module,
      rules: [
        ...(config.module?.rules ?? []),
        {
          test: /\.geojson$/,
          type: "json",
        },
      ],
    },
  };
});
