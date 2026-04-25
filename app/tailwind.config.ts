import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg:        "hsl(var(--bg))",
        surface:   "hsl(var(--surface))",
        muted:     "hsl(var(--muted))",
        border:    "hsl(var(--border))",
        text:      "hsl(var(--text))",
        subtle:    "hsl(var(--subtle))",
        accent:    "hsl(var(--accent))",
        positive:  "hsl(var(--positive))",
        warning:   "hsl(var(--warning))",
        negative:  "hsl(var(--negative))",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Inter", "sans-serif"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};

export default config;
