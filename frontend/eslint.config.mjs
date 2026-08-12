import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Standard async data-fetching pattern: useEffect calls async load()
      // which internally calls setState. This is valid for fetch-on-mount patterns.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
