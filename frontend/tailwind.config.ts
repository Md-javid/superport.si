import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        prussian: {
          DEFAULT: "#031130",
          950: "#020A20",
          900: "#031130",
          800: "#07204F",
          700: "#0C2F73",
          600: "#133F94",
          500: "#2B5BB5",
          300: "#8FA6D1",
          200: "#BCC9E3",
        },
        port: {
          DEFAULT: "#185DF1",
          50: "#EAF1FE",
          100: "#D6E4FD",
          200: "#B0CBFB",
          300: "#82ABF8",
          400: "#4F86F6",
          500: "#185DF1",
          600: "#124BC4",
          700: "#0E3A9A",
        },
        alice: { DEFAULT: "#F3F7FE", 100: "#E8EFFC", 200: "#D9E4F8" },
        signal: { green: "#12B76A", amber: "#F79009", red: "#F04438" },
        ink: { DEFAULT: "#0B1B3A", soft: "#4A5B7C", faint: "#7C8BA8" },
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans Variable"', "system-ui", "sans-serif"],
        sans: ['"Inter Variable"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(24,93,241,.12), 0 12px 40px -12px rgba(24,93,241,.45)",
        card: "0 1px 2px rgba(3,17,48,.04), 0 8px 28px -14px rgba(3,17,48,.18)",
        lift: "0 2px 4px rgba(3,17,48,.05), 0 18px 40px -18px rgba(24,93,241,.35)",
      },
      keyframes: {
        aurora: {
          "0%,100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(6%,-5%,0) scale(1.15)" },
        },
        waveSlide: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        bob: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-10px)" } },
        dashFlow: { to: { strokeDashoffset: "-48" } },
        pulseRing: { "0%": { transform: "scale(.6)", opacity: ".7" }, "100%": { transform: "scale(2.4)", opacity: "0" } },
        shimmer: { "0%": { transform: "translateX(-120%)" }, "100%": { transform: "translateX(120%)" } },
        gradientShift: { "0%,100%": { backgroundPosition: "0% 50%" }, "50%": { backgroundPosition: "100% 50%" } },
      },
      animation: {
        aurora: "aurora 16s ease-in-out infinite",
        "aurora-slow": "aurora 24s ease-in-out infinite reverse",
        wave: "waveSlide 22s linear infinite",
        "wave-slow": "waveSlide 36s linear infinite",
        bob: "bob 7s ease-in-out infinite",
        dash: "dashFlow 2.2s linear infinite",
        ring: "pulseRing 2.6s ease-out infinite",
        shimmer: "shimmer 2.8s ease-in-out infinite",
        gradient: "gradientShift 12s ease infinite",
      },
    },
  },
  plugins: [],
};
export default config;
