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
          DEFAULT: 'var(--color-primary)',
          light: 'var(--color-primary-light)',
          dark: 'var(--color-primary-dark)',
          50: '#e6f7ed',
          100: '#ccefdb',
          200: '#99dfb7',
          300: '#66cf93',
          400: '#33bf6f',
          500: 'var(--color-primary-light)',
          600: 'var(--color-primary)',
          700: 'var(--color-primary)',
          800: 'var(--color-primary-dark)',
          900: '#003619',
        },
        secondary: 'var(--color-secondary)',
        accent: 'var(--color-accent)',
        jra: {
          green: 'var(--color-primary)',
          'green-light': 'var(--color-primary-light)',
          'green-dark': 'var(--color-primary-dark)',
        },
      },
    },
  },
  plugins: [],
}
