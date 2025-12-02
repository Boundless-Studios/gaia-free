/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// import { resolve } from 'path' // Not used currently
import { fileURLToPath, URL } from 'node:url'
import { existsSync } from 'node:fs'

const isRunningInDocker = () => {
  if (process.env.DOCKER === 'true' || process.env.CONTAINER === 'docker') {
    return true
  }
  try {
    return existsSync('/.dockerenv')
  } catch {
    return false
  }
}

const isLocalhostUrl = (value) => {
  if (!value) {
    return false
  }

  try {
    const parsed = new URL(value)
    return ['localhost', '127.0.0.1', '0.0.0.0'].includes(parsed.hostname)
  } catch {
    return (
      value.includes('localhost') ||
      value.includes('127.0.0.1') ||
      value.includes('0.0.0.0')
    )
  }
}

const toWsUrl = (value) => {
  if (!value) {
    return value
  }
  if (value.startsWith('http://')) {
    return value.replace('http://', 'ws://')
  }
  if (value.startsWith('https://')) {
    return value.replace('https://', 'wss://')
  }
  return value
}

const backendPort = process.env.BACKEND_PORT || '8000'
const dockerAwareFallbackHost = isRunningInDocker() ? 'host.docker.internal' : 'localhost'
const fallbackHttpProxyTarget = `http://${dockerAwareFallbackHost}:${backendPort}`

const rawConfiguredProxy =
  process.env.DEV_SERVER_PROXY_TARGET ||
  process.env.VITE_INTERNAL_API_BASE_URL ||
  process.env.VITE_API_BASE_URL

const httpProxyTarget =
  rawConfiguredProxy && !isLocalhostUrl(rawConfiguredProxy)
    ? rawConfiguredProxy
    : fallbackHttpProxyTarget
const wsProxyTarget =
  process.env.DEV_SERVER_WS_PROXY_TARGET ||
  toWsUrl(httpProxyTarget)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@components': fileURLToPath(new URL('./src/components', import.meta.url)),
      '@pages': fileURLToPath(new URL('./src/pages', import.meta.url)),
      '@hooks': fileURLToPath(new URL('./src/hooks', import.meta.url)),
      '@services': fileURLToPath(new URL('./src/services', import.meta.url)),
      '@utils': fileURLToPath(new URL('./src/utils', import.meta.url)),
      '@stores': fileURLToPath(new URL('./src/stores', import.meta.url)),
      '@types': fileURLToPath(new URL('./src/types', import.meta.url)),
      '@assets': fileURLToPath(new URL('./src/assets', import.meta.url)),
      '@styles': fileURLToPath(new URL('./src/styles', import.meta.url)),
      '@config': fileURLToPath(new URL('./src/config', import.meta.url))
    }
  },
  server: {
    port: parseInt(process.env.FRONTEND_PORT || '3000', 10),
    host: '0.0.0.0',
    strictPort: true,
    allowedHosts: [
      'localhost',
      'gaia-frontend-dev', // Docker container name
      // Additional hosts from environment (comma-separated)
      ...(process.env.VITE_ALLOWED_HOSTS?.split(',').filter(Boolean) || [])
    ],
    proxy: {
      '/api': {
        target: httpProxyTarget,
        changeOrigin: true
      },
      '/ws': {
        target: wsProxyTarget,
        ws: true,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom']
        }
      }
    }
  },
  define: {
    'process.env.VITE_BACKEND_URL': JSON.stringify(process.env.VITE_BACKEND_URL || process.env.VITE_API_BASE_URL || `http://localhost:${process.env.BACKEND_PORT || '8000'}`),
    'process.env.VITE_IS_WSL': JSON.stringify(process.env.VITE_IS_WSL || 'false'),
    'process.env.VITE_STT_BASE_URL': JSON.stringify(process.env.VITE_STT_BASE_URL || `ws://localhost:${process.env.STT_PORT || '8001'}`),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    exclude: ['node_modules', 'dist', '.idea', '.git', '.cache'],
    testTimeout: 10000, // 10 seconds timeout for individual tests
    hookTimeout: 10000, // 10 seconds timeout for hooks
    teardownTimeout: 1000, // 1 second for teardown
    pool: 'forks', // Use forks for better isolation
    poolOptions: {
      forks: {
        singleFork: true // Run tests sequentially in a single fork
      }
    },
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.config.js',
        '**/*.config.ts',
        '**/coverage/**',
        '**/dist/**'
      ],
      reportsDirectory: './coverage',
      cleanOnRerun: false, // Prevent cleaning coverage directory on rerun
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80
        }
      }
    }
  }
})
