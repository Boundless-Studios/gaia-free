import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers)

// Cleanup after each test case (e.g. clearing jsdom)
afterEach(() => {
  cleanup()
})

// Mock environment variables for testing
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_BASE_URL: 'http://test-mock-server:8000', // Use fake URL to catch unmocked requests
    VITE_WS_BASE_URL: 'ws://test-mock-server:8000',
    VITE_ENABLE_AUDIO: 'false', // Disable audio in tests
    VITE_USE_OPENAPI: 'true', // Always use OpenAPI
    VITE_DEBUG: 'false',
    DEV: false,
    PROD: false,
    MODE: 'test'
  },
  writable: true
})

// Mock WebSocket for tests
globalThis.WebSocket = class MockWebSocket {
  constructor(url) {
    this.url = url
    this.readyState = 1
    this.onopen = null
    this.onclose = null
    this.onmessage = null
    this.onerror = null
    
    // Simulate connection
    setTimeout(() => {
      if (this.onopen) this.onopen()
    }, 0)
  }
  
  send() {
    // Mock send - do nothing in tests
  }
  
  close() {
    this.readyState = 3
    if (this.onclose) this.onclose()
  }
}

// Mock audio context for audio tests
globalThis.AudioContext = class MockAudioContext {
  constructor() {
    this.state = 'running'
  }
  
  close() {
    this.state = 'closed'
    return Promise.resolve()
  }
  
  createMediaStreamSource() {
    return {
      connect: () => {},
      disconnect: () => {}
    }
  }
  
  createAnalyser() {
    return {
      fftSize: 256,
      frequencyBinCount: 128,
      getByteFrequencyData: () => {},
      connect: () => {},
      disconnect: () => {}
    }
  }
}

// Mock getUserMedia
globalThis.navigator.mediaDevices = {
  getUserMedia: () => Promise.resolve({
    getTracks: () => [],
    addTrack: () => {},
    removeTrack: () => {}
  })
}

// Mock fetch for API tests - ensure it never makes real network requests
globalThis.fetch = vi.fn().mockImplementation((url) => {
  // Only warn for unexpected fetch calls that aren't properly mocked in individual tests
  if (import.meta.env.MODE !== 'test' || import.meta.env.VITE_DEBUG === 'true') {
    console.warn('Unmocked fetch call detected in tests:', url)
  }
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ status: 'mocked' })
  })
})

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
globalThis.localStorage = localStorageMock

// Mock console methods to reduce noise in tests  
globalThis.console = {
  ...console,
  log: vi.fn(),
  debug: vi.fn(),
  info: vi.fn(),
  warn: import.meta.env.VITE_DEBUG === 'true' ? console.warn : vi.fn(),
  error: import.meta.env.VITE_DEBUG === 'true' ? console.error : vi.fn(),
}

// Suppress uncaught network errors that don't affect test functionality
process.on('uncaughtException', (error) => {
  if (error.message?.includes('AggregateError') || 
      error.code === 'ENOTFOUND' || 
      error.code === 'ECONNREFUSED') {
    // Silently ignore network-related errors in tests
    return;
  }
  throw error;
});

process.on('unhandledRejection', (reason) => {
  if (reason?.message?.includes('AggregateError') ||
      reason?.code === 'ENOTFOUND' ||
      reason?.code === 'ECONNREFUSED') {
    // Silently ignore network-related promise rejections in tests  
    return;
  }
  throw reason;
});

// Mock scrollIntoView for jsdom
Element.prototype.scrollIntoView = vi.fn()

// Global API_CONFIG mock to prevent network requests in all tests
vi.mock('../src/config/api.js', () => ({
  API_CONFIG: {
    BACKEND_URL: 'http://test-mock-server:8000',
    WS_BASE_URL: 'ws://test-mock-server:8000',
    
    get HEALTH_ENDPOINT() {
      return `${this.BACKEND_URL}/api/health`;
    },
    
    get TTS_ENDPOINT() {
      return `${this.BACKEND_URL}/api/tts`;
    },
    
    get IMAGES_ENDPOINT() {
      return `${this.BACKEND_URL}/api/images`;
    },
    
    get CAMPAIGNS_ENDPOINT() {
      return `${this.BACKEND_URL}/api/campaigns`;
    },
    
    get TEST_ENDPOINT() {
      return `${this.BACKEND_URL}/api/test`;
    },
    
    get CHAT_ENDPOINT() {
      return `${this.BACKEND_URL}/api/chat`;
    },
    
    get WS_CHAT_STREAM() {
      return `${this.WS_BASE_URL}/api/chat/stream`;
    },
    
    REQUEST_TIMEOUT: 30000,
    WS_RECONNECT_DELAY: 5000,
    MAX_RETRIES: 3,
    ENABLE_AUDIO: false,
    USE_OPENAPI: true,
    DEBUG: false
  }
}))