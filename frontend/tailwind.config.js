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
        // Surface tokens (reference CSS vars from index.css)
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        "surface-elevated": "var(--color-surface-elevated)",
        "surface-pressed": "var(--color-surface-pressed)",
        "surface-overlay": "var(--color-surface-overlay)",

        // Text tokens
        primary: "var(--color-text)",
        secondary: "var(--color-text-secondary)",
        tertiary: "var(--color-text-tertiary)",
        muted: "var(--color-text-muted)",

        // Semantic tokens
        accent: {
          DEFAULT: "var(--color-accent)",
          soft: "var(--color-accent-soft)",
          hover: "var(--color-accent-hover)",
        },
        destructive: {
          DEFAULT: "var(--color-destructive)",
          soft: "var(--color-destructive-soft)",
        },
        warning: "var(--color-warning)",
        info: "var(--color-info)",

        // Border tokens
        "border-default": "var(--color-border)",
        "border-strong": "var(--color-border-strong)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "system-ui",
          "sans-serif",
        ],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        full: "var(--radius-full)",
      },
      spacing: {
        "safe-t": "var(--sat)",
        "safe-b": "var(--sab)",
      },
      backdropBlur: {
        ios: "24px",
      },
      transitionTimingFunction: {
        default: "var(--ease-default)",
        spring: "var(--ease-spring)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        normal: "var(--duration-normal)",
        slow: "var(--duration-slow)",
      },
    },
  },
  plugins: [],
};
