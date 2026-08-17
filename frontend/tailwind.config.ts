import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202A",
        mist: "#F5F7FA",
        line: "#D8DEE6",
        brand: "#2266A5",
        success: "#287A52",
        danger: "#B33A3A"
      }
    }
  },
  plugins: []
};

export default config;

