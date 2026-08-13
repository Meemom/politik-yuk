import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#17211b",
        paper: "#f7f4ed",
        civic: "#256f73",
        signal: "#b5442c",
        field: "#e8dfc7",
      },
    },
  },
  plugins: [],
};

export default config;
