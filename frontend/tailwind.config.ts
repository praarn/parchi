import type { Config } from "tailwindcss";

/**
 * The warm "civic paper" identity, kept and tightened: a bone-paper ground,
 * deep teal as the primary, warm amber as the accent, plus a proper set of
 * ink / paper shades so surfaces can layer without new hues.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#12232B",
          soft: "#3A4A52",
          muted: "#6B7A80",
        },
        paper: {
          DEFAULT: "#FBF8F2",
          raised: "#FFFFFF",
          sunk: "#F3EEE3",
        },
        line: "#E7E0D2",
        teal: {
          DEFAULT: "#0F5257",
          dark: "#0A3B3F",
          light: "#12696F",
          wash: "#E7F0EF",
        },
        amber: {
          DEFAULT: "#E8A33D",
          dark: "#C9852A",
          wash: "#FBEFD9",
        },
        success: "#2F7D4F",
        danger: "#C0392B",
      },
      fontFamily: {
        display: ["var(--font-display)", "Fraunces", "Georgia", "serif"],
        body: ["var(--font-body)", "Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "1.25rem",
        pill: "999px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(18,35,43,.04), 0 8px 24px -12px rgba(18,35,43,.12)",
        lift: "0 2px 6px rgba(18,35,43,.06), 0 18px 40px -16px rgba(18,35,43,.22)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up .35s ease both",
      },
    },
  },
  plugins: [],
};
export default config;
