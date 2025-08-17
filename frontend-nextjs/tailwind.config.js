/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#4a90e2',
        'primary-hover': '#357abd',
        background: '#444444',
        card: '#222222',
        'card-header': '#333333',
        'card-content': '#2a2a2a',
        text: '#ffffff',
        'text-secondary': '#cccccc',
        error: '#ff6b6b',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
} 