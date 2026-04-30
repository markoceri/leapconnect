/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        lm: {
          bg: '#090b12',
          bg2: '#0d1018',
          card: '#111420',
          border: '#1c2135',
          border2: '#1a1f30',
          elevated: '#161b2a',
          input: '#0e1220',
          text: '#e2e6f0',
          muted: '#4a5468',
          muted2: '#3a4458',
          muted3: '#5c6478',
          label: '#6a748a',
          heading: '#c8cfe0',
          sub: '#8892a8',
          cyan: '#00d4ff',
          green: '#00e676',
          amber: '#ffab40',
          red: '#ff5252',
          purple: '#7c6aff',
          orange: '#ff7043',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}

