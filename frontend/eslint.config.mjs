import next from "eslint-config-next/core-web-vitals";

/** Flat ESLint config (ESLint 9 / Next 16). */
const config = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...next,
  {
    rules: {
      "@next/next/no-img-element": "off",
      // We read auth state / load a document's data on mount from the API and
      // localStorage (neither exists during SSR), which necessarily means
      // setState inside an effect. Keep it visible as a warning, not an error.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default config;
