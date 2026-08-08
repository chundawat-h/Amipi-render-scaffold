/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14151a",       // near-black, not pure black — for a jeweler's velvet-tray feel
        paper: "#F7F5F1",     // warm off-white, not stark white
        gold: {
          DEFAULT: "#C9A24B",
          soft: "#E4D3A6",
          deep: "#8C6D2A",
        },
        line: "#2A2C33",
      },
      fontFamily: {
        display: ["'Cormorant Garamond'", "serif"],
        body: ["'Inter'", "sans-serif"],
      },
    },
  },
  plugins: [],
}
