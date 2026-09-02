/** Tailwind build config — mirrors the theme previously set up via the Play CDN. */
module.exports = {
  content: ["./index.html", "./templates/**/*.html"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        display: ["Orbitron", "sans-serif"],
        tech: ["Rajdhani", "sans-serif"],
      },
      colors: {
        cyber: {
          black: "#07080d",
          dark: "#0e111a",
          card: "#141724",
          border: "#23283e",
          cyan: "#00f0ff",
          magenta: "#ff0055",
          yellow: "#ffcc00",
          purple: "#9d4edd",
        },
      },
      boxShadow: {
        "glow-cyan": "0 0 25px rgba(0, 240, 255, 0.35)",
        "glow-magenta": "0 0 25px rgba(255, 0, 85, 0.35)",
        "glow-yellow": "0 0 25px rgba(255, 204, 0, 0.35)",
      },
    },
  },
  plugins: [],
};
