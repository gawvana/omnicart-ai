/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "#000000",
        surface: "#0A0A0C",
        "surface-raised": "#121216",
        "surface-elevated": "#1A1A20",
        "surface-overlay": "rgba(255, 255, 255, 0.04)",
        "ios-border": "rgba(255, 255, 255, 0.08)",
        "ios-border-active": "rgba(255, 255, 255, 0.18)",
        zinc: {
          900: "#0F0F12",
          800: "#1A1A20",
          700: "#272730",
          600: "#3F3F4A",
          500: "#71717A",
          400: "#A1A1AA",
          300: "#D4D4D8",
          200: "#E4E4E7",
          100: "#F4F4F5",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
      },
      borderRadius: {
        "ios": "1.25rem",
        "ios-lg": "1.75rem",
        "ios-xl": "2.25rem",
      },
      backdropBlur: {
        "ios": "24px",
      },
    },
  },
  plugins: [],
};
