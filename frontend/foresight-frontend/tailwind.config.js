/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ["Geist", "system-ui", "sans-serif"],
      },
      colors: {
        // Dark mode surface tokens
        "dark-surface": "#2d3166",
        "dark-surface-elevated": "#3d4176",
        "dark-surface-hover": "#4d5186",
        "dark-surface-deep": "#1a1d40",
        // City of Austin Brand Colors
        brand: {
          blue: "#44499C", // Logo Blue - primary
          green: "#009F4D", // Logo Green - accent/success
          "faded-white": "#f7f6f5", // Background
          "dark-blue": "#22254E", // Dark mode bg, dark text
          "dark-green": "#005027", // Supporting
          "light-blue": "#dcf2fd", // Light accent
          "light-green": "#dff0e3", // Light success
          "compliant-green": "#008743", // Supporting
        },
        // Extended palette for data visualization
        extended: {
          red: "#F83125",
          orange: "#FF8F00",
          yellow: "#FFC600",
          cyan: "#009CDE",
          purple: "#9F3CC9",
          brown: "#8F5201",
        },
        // Semantic mappings
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "#44499C",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "#009F4D",
          foreground: "hsl(var(--secondary-foreground))",
        },
        accent: {
          DEFAULT: "#dcf2fd",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "#F83125",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: 0 },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: 0 },
        },
        "slide-up-fade-in": {
          from: { opacity: 0, transform: "translateY(8px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        "smooth-pulse": {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.4 },
        },
        "fade-in": {
          from: { opacity: 0 },
          to: { opacity: 1 },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "slide-up-fade-in":
          "slide-up-fade-in 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) both",
        "smooth-pulse": "smooth-pulse 1.5s ease-in-out infinite",
        "fade-in-chat": "fade-in 0.3s ease-out both",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    // Touch-action utilities for mobile optimization
    function ({ addUtilities }) {
      addUtilities({
        ".touch-none": {
          "touch-action": "none",
        },
        ".touch-auto": {
          "touch-action": "auto",
        },
        ".touch-pan-x": {
          "touch-action": "pan-x",
        },
        ".touch-pan-y": {
          "touch-action": "pan-y",
        },
        ".touch-pan-left": {
          "touch-action": "pan-left",
        },
        ".touch-pan-right": {
          "touch-action": "pan-right",
        },
        ".touch-pan-up": {
          "touch-action": "pan-up",
        },
        ".touch-pan-down": {
          "touch-action": "pan-down",
        },
        ".touch-pinch-zoom": {
          "touch-action": "pinch-zoom",
        },
        ".touch-manipulation": {
          "touch-action": "manipulation",
        },
      });
    },
  ],
};
