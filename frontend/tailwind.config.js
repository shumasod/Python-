/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#e6f7ed',
          100: '#ccefdb',
          200: '#99dfb7',
          300: '#66cf93',
          400: '#33bf6f',
          500: '#00a968',
          600: '#008c56',
          700: '#006937',
          800: '#005028',
          900: '#003619',
        },
        jra: {
          green: '#006937',
          'green-light': '#00a968',
          'green-dark': '#005028',
        },
      },
    },
  },
  plugins: [],
}
