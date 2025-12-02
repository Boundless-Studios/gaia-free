/**
 * Sound Effects Service
 *
 * Handles API calls for ElevenLabs sound effect generation.
 * Provides methods for generating sound effects and checking service availability.
 */

import { API_CONFIG } from '../config/api.js';

class SFXService {
  constructor() {
    this.baseUrl = API_CONFIG.BACKEND_URL || '';
    this.getAccessToken = null;
  }

  /**
   * Set the access token getter function (called by App initialization)
   * @param {Function} tokenGetter - Async function that returns the access token
   */
  setAccessTokenGetter(tokenGetter) {
    this.getAccessToken = tokenGetter;
  }

  /**
   * Get authorization headers with optional auth token
   * @returns {Promise<Object>} Headers object
   */
  async getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };

    if (this.getAccessToken) {
      try {
        const accessToken = await this.getAccessToken();
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
      } catch (error) {
        console.warn('[SFX_SERVICE] Failed to get access token:', error);
      }
    }

    return headers;
  }

  /**
   * Map audio payload URLs to absolute URLs
   * @param {Object} audio - Audio payload from API
   * @param {string} sessionId - Session ID for URL mapping
   * @returns {Object} Mapped audio payload
   */
  mapAudioPayload(audio, sessionId) {
    if (!audio) return audio;

    const mapped = { ...audio };

    // Ensure URL is absolute
    if (mapped.url && !mapped.url.startsWith('http') && !mapped.url.startsWith('data:')) {
      const baseUrl = this.baseUrl || '';
      mapped.url = mapped.url.startsWith('/')
        ? `${baseUrl}${mapped.url}`
        : `${baseUrl}/${mapped.url}`;
    }

    // Add session_id if not present
    if (sessionId && !mapped.session_id) {
      mapped.session_id = sessionId;
    }

    return mapped;
  }

  /**
   * Generate a sound effect from text description
   * @param {Object} sfxData - Sound effect generation data
   * @param {string} sfxData.text - Description of the sound effect
   * @param {number} [sfxData.duration_seconds] - Optional duration (0.5-22 seconds)
   * @param {number} [sfxData.prompt_influence] - How closely to follow prompt (0-1)
   * @param {string} [sessionId] - Campaign/session ID for broadcasting
   * @returns {Promise<Object>} Generated sound effect with audio payload
   */
  async generateSoundEffect(sfxData, sessionId = null) {
    const headers = await this.getAuthHeaders();

    const payload = { ...sfxData };
    if (sessionId && !payload.session_id) {
      payload.session_id = sessionId;
    }

    const response = await fetch(`${this.baseUrl}/api/sfx/generate`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const sessionForPayload = payload.session_id || sessionId;

    if (data?.audio) {
      data.audio = this.mapAudioPayload(data.audio, sessionForPayload);
    }

    return data;
  }

  /**
   * Check if sound effects service is available
   * @returns {Promise<Object>} SFX availability info
   */
  async getAvailability() {
    const headers = await this.getAuthHeaders();

    const response = await fetch(`${this.baseUrl}/api/sfx/availability`, { headers });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }
}

// Singleton instance
const sfxService = new SFXService();

export default sfxService;
