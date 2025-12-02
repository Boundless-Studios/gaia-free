/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'gaia-dark': '#0a0a0a',
        'gaia-darker': '#050505',
        'gaia-light': '#1a1a1a',
        'gaia-border': '#2a2a2a',
        'gaia-text': '#e0e0e0',
        'gaia-text-dim': '#a0a0a0',
        'gaia-accent': '#8b5cf6',
        'gaia-accent-hover': '#7c3aed',
        'gaia-success': '#10b981',
        'gaia-error': '#ef4444',
        'gaia-warning': '#f59e0b',
        'gaia-info': '#3b82f6',
      },
      fontFamily: {
        'medieval': ['Cinzel', 'serif'],
        'body': ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slideInFade': 'slideInFade 0.5s ease-out',
        'pulse-custom': 'pulseCustom 1.5s infinite',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(139, 92, 246, 0.5)' },
          '100%': { boxShadow: '0 0 20px rgba(139, 92, 246, 0.8)' },
        },
        slideInFade: {
          from: {
            opacity: '0',
            transform: 'translateY(20px)'
          },
          to: {
            opacity: '1',
            transform: 'translateY(0)'
          }
        },
        pulseCustom: {
          '0%': {
            boxShadow: '0 0 0 0 rgba(255, 255, 255, 0.4)'
          },
          '50%': {
            boxShadow: '0 0 0 10px rgba(255, 255, 255, 0)'
          },
          '100%': {
            boxShadow: '0 0 0 0 rgba(255, 255, 255, 0)'
          }
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
}