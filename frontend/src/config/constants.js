// Application constants
export const APP_CONFIG = {
  NAME: 'Gaia D&D Frontend',
  VERSION: '1.0.0',
  DESCRIPTION: 'Interactive D&D game interface with AI-powered storytelling'
};

// Message types
export const MESSAGE_TYPES = {
  USER: 'user',
  DM: 'dm',
  SYSTEM: 'system',
  ERROR: 'error'
};

// Campaign states
export const CAMPAIGN_STATES = {
  IDLE: 'idle',
  ACTIVE: 'active',
  LOADING: 'loading',
  ERROR: 'error'
};

// Audio states
export const AUDIO_STATES = {
  IDLE: 'idle',
  RECORDING: 'recording',
  PROCESSING: 'processing',
  PLAYING: 'playing'
};

// Image types
export const IMAGE_TYPES = {
  SCENE: 'scene',
  CHARACTER: 'character',
  ITEM: 'item',
  BEAST: 'beast',
  MOMENT: 'moment'
};

// Keyboard shortcuts
export const KEYBOARD_SHORTCUTS = {
  GENERATE_IMAGE: 'Ctrl+G',
  TOGGLE_RECORDING: 'Ctrl+/',
  SEND_MESSAGE: 'Enter',
  HELP: 'F1'
};

// Local storage keys
export const STORAGE_KEYS = {
  LAST_CAMPAIGN_ID: 'lastCampaignId',
  USER_PREFERENCES: 'userPreferences',
  VOICE_SETTINGS: 'voiceSettings'
};

// Error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network connection failed',
  INVALID_CAMPAIGN: 'Invalid campaign ID',
  AUDIO_NOT_SUPPORTED: 'Audio features not supported in this browser',
  WEBSOCKET_FAILED: 'WebSocket connection failed'
};