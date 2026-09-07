import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: {
          950: "#050609",
          900: "#0a0c12",
          800: "#12151d",
          700: "#1b1f2a",
          600: "#272c3a",
        },
        signal: {
          commander: "#f2e6c9",
          research: "#5eead4",
          analyst: "#a78bfa",
          creator: "#34d399",
          critic: "#fbbf24",
          guardian: "#fb7185",
          executor: "#93a0b8",
        },
        ok: "#3fd68f",
        warn: "#f5a524",
        danger: "#f0555a",
      },
      fontFamily: {
        display: [
          "var(--font-display)",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      letterSpacing: {
        widest2: "0.35em",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-slow": {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        scan: {
          "0%": { backgroundPosition: "0% 0%" },
          "100%": { backgroundPosition: "0% 100%" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.6s ease-out both",
        "fade-up": "fade-up 0.7s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-slow": "pulse-slow 3.2s ease-in-out infinite",
      },
      boxShadow: {
        glow: "0 0 40px -8px var(--tw-shadow-color)",
      },
    },
  },
  plugins: [],
};

export default config;
