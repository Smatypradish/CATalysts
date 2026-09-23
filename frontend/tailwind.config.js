/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cat: {
          yellow: '#FFCD11',
          amber: '#F5B700',
          black: '#111111',
          steel: '#1c1c1e',
          panel: '#232326',
          line: '#3a3a3f',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
