/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        heading: ['Outfit', 'sans-serif'],
      },
      colors: {
        primary: '#2563eb',
        'primary-dark': '#3b82f6',
        'primary-light': '#60a5fa',
      },
      boxShadow: {
        'glass-light': '0 4px 30px rgba(0, 0, 0, 0.05)',
        'glass-dark': '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
      }
    }
  },
  plugins: [],
}
