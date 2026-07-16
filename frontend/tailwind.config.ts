import type { Config } from "tailwindcss";

// Dark "cost console" theme. Tier palette matches the spec and the Streamlit
// dashboard's intent (same semantic mapping: cache/simple green, medium violet,
// complex amber, fallback gray).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { page: "#0A0D12", card: "#10151C", border: "#1B2129" },
        text: { primary: "#E8EDF2", secondary: "#8B96A3", muted: "#5F6A76" },
        tier: {
          // cache and simple share the teal family
          cache: "#5DCAA5",
          "cache-bg": "#04342C",
          "cache-border": "#1D9E75",
          simple: "#5DCAA5",
          "simple-bg": "#04342C",
          "simple-border": "#1D9E75",
          medium: "#AFA9EC",
          "medium-bg": "#26215C",
          "medium-border": "#7F77DD",
          complex: "#EF9F27",
          "complex-bg": "#412402",
          "complex-border": "#BA7517",
          fallback: "#8B96A3",
          "fallback-bg": "#1B222B",
          "fallback-border": "#5F6A76",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-space-grotesk)", "ui-sans-serif", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
