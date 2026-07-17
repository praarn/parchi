import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12232B",
        paper: "#FBF8F2",
        teal: {
          DEFAULT: "#0F5257",
          dark: "#0A3B3F",
        },
        amber: {
          DEFAULT: "#E8A33D",
          dark: "#C9852A",
        },
      },
      fontFamily: {
        display: ["'Fraunces'", "serif"],
        body: ["'Inter'", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;