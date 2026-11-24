import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0f1e2e",
        paper: "#f5f0e6",
        white: "#fffdf9",
        greenbrand: "#1f6b52",
        greenbg: "#e4efe8",
        amberbrand: "#9a6414",
        amberbg: "#f8eed8",
        redbrand: "#a9362d",
        redbg: "#f7e7e4",
        terra: "#c2603a",
        muted: "#66717b",
        line: "#dcd6cb",
        // Alias historiques conservés
        emerald: "#1f6b52",
        emeraldbg: "#e4efe8",
        gold: "#9a6414",
        goldbg: "#f8eed8",
        crimson: "#a9362d",
        crimsonbg: "#f7e7e4",
        slate: "#66717b",
        night: "#0a1722",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        body: ["Inter", "Arial", "sans-serif"],
        arabic: ["IBM Plex Sans Arabic", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 40px rgba(31, 107, 82, 0.15)",
        card: "0 8px 30px rgba(15, 30, 46, 0.08)",
        premium: "0 20px 60px rgba(15, 30, 46, 0.12)",
      },
      animation: {
        "fade-up": "fadeUp 0.5s ease-out forwards",
        float: "float 6s ease-in-out infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
