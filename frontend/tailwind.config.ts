import type { Config } from "tailwindcss";

// Tier palette kept in sync with dashboard/app.py TIER_COLORS and lib/colors.ts.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        tier: {
          cache: "#4E79A7",
          simple: "#59A14F",
          medium: "#F28E2B",
          complex: "#E15759",
        },
        ink: "#0f172a",
        panel: "#ffffff",
        canvas: "#f1f5f9",
      },
      boxShadow: {
        card: "0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
