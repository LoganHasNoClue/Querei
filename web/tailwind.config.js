/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#000000", // page background
        panel: "#0e0e11", // assistant bubble
        user: "#15202e", // user bubble (blue-tinted, like the reference)
        edge: "#1c1c22", // hairline borders
        link: "#6aa8e0", // entity / link blue
        glow: "#8b5cf6", // accent (toggle "live")
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Text",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        auroraShift: {
          "0%,100%": { transform: "translateX(-4%) scale(1)", opacity: "0.9" },
          "50%": { transform: "translateX(4%) scale(1.08)", opacity: "1" },
        },
      },
      animation: {
        fadeUp: "fadeUp 0.25s ease-out",
        aurora: "auroraShift 14s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
