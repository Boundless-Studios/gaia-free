// API configuration for Gaia frontend

// Determine if we're running in production (accessed via domain)
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';

// Use relative paths in production, absolute in development
const getBackendUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL !== undefined) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return isProduction ? '' : 'http://localhost:8000';
};

const normalizeWsBase = (rawValue) => {
  if (!rawValue) {
    return '';
  }

  let value = String(rawValue).trim();
  if (!value) {
    return '';
  }

  if (value.startsWith('//')) {
    value = `${window.location.protocol}${value}`;
  }

  try {
    const url = new URL(value, window.location.origin);
    if (url.protocol === 'http:') {
      url.protocol = 'ws:';
    } else if (url.protocol === 'https:') {
      url.protocol = 'wss:';
    }
    return url.toString().replace(/\/$/, '');
  } catch {
    if (value.startsWith('http://')) {
      return `ws://${value.slice('http://'.length).replace(/\/$/, '')}`;
    }
    if (value.startsWith('https://')) {
      return `wss://${value.slice('https://'.length).replace(/\/$/, '')}`;
    }
    return value.replace(/\/$/, '');
  }
};

const getWsUrl = () => {
  const explicitWs = import.meta.env.VITE_WS_BASE_URL;
  if (explicitWs) {
    return normalizeWsBase(explicitWs);
  }
  const apiBase = import.meta.env.VITE_API_BASE_URL;
  if (apiBase) {
    return normalizeWsBase(apiBase);
  }
  if (isProduction) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}`;
  }
  return 'ws://localhost:8000';
};

// STT service - always use /stt prefix (dev proxies to 8001, prod uses cloudflared)
const getSttUrl = () => {
  if (import.meta.env.VITE_STT_BASE_URL) {
    return import.meta.env.VITE_STT_BASE_URL;
  }
  // Always use /stt prefix - backend or cloudflared handles routing
  // Note: The /stt prefix is required for all endpoints
  return isProduction ? '' : 'http://localhost:8001/stt';
};

export const API_CONFIG = {
  // Base URLs
  BACKEND_URL: getBackendUrl(),
  WS_BASE_URL: getWsUrl(),
  STT_BASE_URL: getSttUrl(),
  
  // API endpoints
  get HEALTH_ENDPOINT() {
    return `${this.BACKEND_URL}/api/health`;
  },
  
  get CHAT_ENDPOINT() {
    return `${this.BACKEND_URL}/api/chat`;
  },
  
  get TEST_ENDPOINT() {
    return `${this.BACKEND_URL}/api/test`;
  },
  
  get TTS_ENDPOINT() {
    return `${this.BACKEND_URL}/api/tts`;
  },
  
  get CAMPAIGNS_ENDPOINT() {
    return `${this.BACKEND_URL}/api/campaigns`;
  },
  
  get IMAGES_ENDPOINT() {
    return `${this.BACKEND_URL}/api/images`;
  },
  
  // WebSocket endpoints
  get WS_CHAT_STREAM() {
    return `${this.WS_BASE_URL}/api/chat/stream`;
  },
  
  get VOICE_ACTIVITY_ENDPOINT() {
    // STT voice activity endpoint - fixed path without double /stt
    return isProduction ? '/stt/voice-activity' : 'http://localhost:8001/stt/voice-activity';
  },
  
  // Configuration options
  REQUEST_TIMEOUT: 30000, // 30 seconds
  WS_RECONNECT_DELAY: 5000, // 5 seconds
  MAX_RETRIES: 3,
  
  // Feature flags
  ENABLE_AUDIO: import.meta.env.VITE_ENABLE_AUDIO !== 'false',
  USE_OPENAPI: true,  // Always use OpenAPI now that protobuf is removed
  
  // Debug mode
  DEBUG: import.meta.env.VITE_DEBUG === 'true' || import.meta.env.MODE === 'development'
};
