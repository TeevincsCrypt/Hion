import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Restrained monochrome foundation. Every screen is built from these
        // five neutrals; color is reserved for the two semantic exceptions
        // below (accent, risk) - never used decoratively.
        paper: {
          DEFAULT: "#F7F7F5",
          dim: "#F0F0EE",
        },
        surface: "#FFFFFF",
        ink: {
          900: "#111111",
          600: "#3F3F3D",
          500: "#6B6B6B",
          300: "#A0A0A0",
          200: "#CFCFCB",
        },
        line: {
          DEFAULT: "#E5E5E3",
          strong: "#D2D2CE",
        },
        // The one accent: what is currently active or requires attention.
        // Never decorative, never a gradient partner.
        accent: {
          DEFAULT: "#B8814A",
          soft: "#E4D2BC",
          dim: "#8C6136",
        },
        // Risk escalation reuses ink/accent for LOW/MEDIUM and introduces the
        // single semantic red for HIGH/failure - functional signaling, not
        // decoration, and used nowhere else in the interface.
        risk: {
          high: "#B23B3B",
          highSoft: "#EBD3D3",
        },
        ok: "#3F6B4F",
      },
      fontFamily: {
        display: [
          "var(--font-display)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
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
        wide2: "0.08em",
        widest2: "0.22em",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-slow": {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.7s cubic-bezier(0.16,1,0.3,1) both",
        "fade-up": "fade-up 0.8s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-slow": "pulse-slow 2.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
