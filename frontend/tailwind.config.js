/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0c10",
          900: "#0e1117",
          850: "#131722",
          800: "#1a1f2e",
          700: "#252c3f",
          600: "#33405c",
        },
        line: "rgba(148,163,184,0.10)",
      },
      fontFamily: {
        sans: ["'Inter Variable'", "Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
        glow: "0 0 12px 2px currentColor",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.45", transform: "scale(0.82)" },
        },
        tickFlash: {
          "0%": { borderColor: "rgba(56,189,248,0.55)" },
          "100%": { borderColor: "rgba(148,163,184,0.10)" },
        },
      },
      animation: {
        pulseDot: "pulseDot 1.6s ease-in-out infinite",
        tickFlash: "tickFlash 0.9s ease-out forwards",
      },
    },
  },
  plugins: [],
};
