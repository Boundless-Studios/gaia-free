/**
 * API Service - Handles JSON/OpenAPI communication with the backend
 * This replaces the protobuf-based communication with simpler JSON
 */

import { API_CONFIG } from '../config/api.js';

class ApiService {
  constructor() {
    this.baseUrl = API_CONFIG.BACKEND_URL;
    // All endpoints now consolidated under /api prefix
    this.v2Prefix = '/api/v2';  // New OpenAPI endpoints
    this.getAccessToken = null; // Will be set from App.jsx
    this.onAuthError = null; // Callback for auth failures
    // Map of in-flight requests for deduping identical concurrent calls
    this.inflight = new Map();
    this.tokenProviderVersion = 0;
    this.tokenProviderListeners = new Set();
  }

  /**
   * Small helper to sleep for a given number of milliseconds.
   */
  sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Parse Retry-After header value (seconds or HTTP-date) into milliseconds.
   */
  parseRetryAfter(retryAfterValue) {
    if (!retryAfterValue) return null;
    const s = parseInt(retryAfterValue, 10);
    if (!Number.isNaN(s)) {
      return Math.max(0, s * 1000);
    }
    const dateMs = Date.parse(retryAfterValue);
    if (!Number.isNaN(dateMs)) {
      return Math.max(0, dateMs - Date.now());
    }
    return null;
  }

  /**
   * Fetch JSON with in-flight deduplication and 429 Retry-After handling.
   * - Dedupes identical concurrent requests by method+url+body.
   * - On 429 (or 503 with Retry-After), waits per Retry-After or exponential backoff, then retries.
   */
  async fetchJsonWithDedupe(url, options = {}, retryOptions = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const bodyKey = options.body
      ? (typeof options.body === 'string' ? options.body : JSON.stringify(options.body))
      : '';
    const dedupeKey = `${method} ${url} ${bodyKey}`;

    if (this.inflight.has(dedupeKey)) {
      return this.inflight.get(dedupeKey);
    }

    const attemptFetch = async () => {
      const {
        maxAttempts = 3,
        baseDelayMs = 1000,
        jitterMs = 300,
      } = retryOptions || {};

      // Merge headers and attach Authorization if available
      const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
      if (!headers.Authorization && this.getAccessToken) {
        try {
          const token = await this.getAccessToken();
          if (token) {
            headers.Authorization = `Bearer ${token}`;
          }
        } catch (e) {
          // Non-fatal; proceed unauthenticated
        }
      }

      let lastError = null;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          const requestOptions = {
            ...options,
            method,
            headers,
          };
          if (!('credentials' in requestOptions)) {
            requestOptions.credentials = 'include';
          }

          const response = await fetch(url, requestOptions);

          if (response.status === 429 || (response.status === 503 && response.headers.has('retry-after'))) {
            // Rate limited or unavailable with guidance to retry
            const retryAfterHeader = response.headers.get('retry-after');
            const retryMsFromHeader = this.parseRetryAfter(retryAfterHeader);
            const backoffMs = retryMsFromHeader ?? (baseDelayMs * Math.pow(2, attempt - 1));
            const jitter = Math.floor(Math.random() * jitterMs);
            if (attempt < maxAttempts) {
              await this.sleep(backoffMs + jitter);
              continue;
            }
          }

          if (!response.ok) {
            // Try to parse response JSON error body but fall back to text
            let errPayload = null;
            try { errPayload = await response.json(); } catch (_) { /* ignore */ }
            const errMsg = errPayload?.detail || errPayload?.message || `HTTP error! status: ${response.status}`;
            const err = new Error(errMsg);
            err.status = response.status;
            throw err;
          }

          // Success
          return await response.json();
        } catch (err) {
          lastError = err;
          // On network errors or other transient failures, backoff and retry
          if (attempt < maxAttempts) {
            const backoffMs = baseDelayMs * Math.pow(2, attempt - 1);
            const jitter = Math.floor(Math.random() * jitterMs);
            await this.sleep(backoffMs + jitter);
            continue;
          }
          throw err;
        }
      }

      // If all attempts failed, throw the last error
      throw lastError || new Error('Request failed');
    };

    const promise = attemptFetch()
      .finally(() => {
        // Ensure we clear the inflight entry regardless of outcome
        this.inflight.delete(dedupeKey);
      });

    this.inflight.set(dedupeKey, promise);
    return promise;
  }

  /**
   * Encode a value for safe use in URL path segments.
   * @param {string|number} segment - Raw segment value
   * @returns {string} URL-safe segment
   */
  encodePathSegment(segment) {
    if (segment === undefined || segment === null) {
      return '';
    }
    return encodeURIComponent(String(segment));
  }

  isAbsoluteUrl(url) {
    return /^https?:\/\//i.test(url);
  }

  isSpecialScheme(url) {
    return /^(?:data:|blob:|file:)/i.test(url || '');
  }

  buildAbsoluteUrl(rawUrl) {
    if (!rawUrl || this.isAbsoluteUrl(rawUrl) || this.isSpecialScheme(rawUrl)) {
      return rawUrl || null;
    }

    if (rawUrl.startsWith('//')) {
      const protocol = typeof window !== 'undefined' ? window.location.protocol : 'https:';
      return `${protocol}${rawUrl}`;
    }

    const base =
      this.baseUrl ||
      (typeof window !== 'undefined' ? window.location.origin : '');

    if (!base) {
      return rawUrl;
    }

    try {
      const absolute = new URL(rawUrl, base);
      return absolute.toString();
    } catch (error) {
      console.warn('Failed to resolve absolute URL:', rawUrl, error);
      if (rawUrl.startsWith('/')) {
        return `${base.replace(/\/$/, '')}${rawUrl}`;
      }
      return rawUrl;
    }
  }

  async fetchMediaAsObjectUrl(absoluteUrl) {
    if (typeof window === 'undefined' || !window.URL || typeof window.URL.createObjectURL !== 'function') {
      return absoluteUrl;
    }

    const headers = {};
    if (this.getAccessToken) {
      try {
        const token = await this.getAccessToken();
        if (token) {
          headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.warn('Failed to obtain auth token for media fetch:', error);
      }
    }

    const response = await fetch(absoluteUrl, {
      method: 'GET',
      headers,
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      const error = new Error(`Media request unauthorized (status ${response.status})`);
      if (this.onAuthError) {
        this.onAuthError(error);
      }
      throw error;
    }

    if (!response.ok) {
      throw new Error(`Media request failed: ${response.status}`);
    }

    const blob = await response.blob();
    return window.URL.createObjectURL(blob);
  }

  async buildAuthorizedMediaUrl(rawUrl) {
    if (!rawUrl) {
      return null;
    }

    const absoluteUrl = this.buildAbsoluteUrl(rawUrl);
    if (!absoluteUrl) {
      return null;
    }

    const needsAuth = absoluteUrl.includes('/api/media/');
    if (!needsAuth) {
      return absoluteUrl;
    }

    if (absoluteUrl.startsWith('blob:') || absoluteUrl.startsWith('data:')) {
      return absoluteUrl;
    }

    try {
      return await this.fetchMediaAsObjectUrl(absoluteUrl);
    } catch (error) {
      console.warn('Failed to fetch authorized media blob:', error);
      return absoluteUrl;
    }
  }

  /**
   * Set the token provider function from Auth0
   * @param {Function} tokenProvider - Function to get access token
   */
  setTokenProvider(tokenProvider) {
    console.log('🔐 Setting Auth0 token provider in apiService');
    this.getAccessToken = tokenProvider;
    this.tokenProviderVersion += 1;
    this.notifyTokenProviderListeners();
  }

  /**
   * Set the auth error callback for automatic logout
   * @param {Function} callback - Function to call on auth errors
   */
  setAuthErrorCallback(callback) {
    console.log('🔐 Setting auth error callback in apiService');
    this.onAuthError = callback;
  }

  subscribeTokenProvider(listener) {
    if (typeof listener !== 'function') {
      return () => {};
    }
    this.tokenProviderListeners.add(listener);
    return () => {
      this.tokenProviderListeners.delete(listener);
    };
  }

  notifyTokenProviderListeners() {
    for (const listener of this.tokenProviderListeners) {
      try {
        listener(this.tokenProviderVersion);
      } catch (error) {
        console.warn('Token provider listener error:', error);
      }
    }
  }

  /**
   * Make a request to the backend API
   * @param {string} endpoint - The API endpoint (without base URL)
   * @param {Object} data - The request data
   * @param {string} method - HTTP method (default: 'POST')
   * @returns {Promise<Object>} The response data
   */
  async makeRequest(endpoint, data = null, method = 'POST') {
    const headers = {
      'Content-Type': 'application/json',
    };
    
    // Try to get Auth0 token if provider is set
    console.log('🔐 Token provider available:', !!this.getAccessToken);
    if (this.getAccessToken) {
      try {
        console.log('🔐 Attempting to get Auth0 token...');
        // The token provider is now a wrapper function that returns the token
        const accessToken = await this.getAccessToken();
        console.log('🔐 Auth0 token received:', accessToken ? `${accessToken.substring(0, 20)}...` : 'null/undefined');
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
          console.log('🔐 Authorization header set');
        } else {
          console.warn('🔐 No access token received from Auth0');
        }
      } catch (error) {
        console.warn('🔐 Failed to get Auth0 token:', error);

        // Check if this is an Auth0 error indicating expired/invalid refresh token
        if (error.error === 'login_required' ||
            error.error === 'invalid_grant' ||
            error.message?.includes('login_required') ||
            error.message?.includes('expired')) {
          console.error('🔐 Refresh token expired or invalid - triggering logout');
          if (this.onAuthError) {
            this.onAuthError(error);
          }
        }
      }
    } else {
      console.warn('🔐 No token provider set - requests will be unauthenticated');
    }
    
    const options = {
      method,
      headers,
    };
    
    if (method !== 'GET' && data) {
      options.body = JSON.stringify(data);
    }
    
    console.log(`📡 API Request to ${endpoint}:`, data);
    
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, options);

      console.log(`📡 API Response status: ${response.status}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error(`❌ API Error Response:`, errorData);
        const errorMessage = errorData.detail?.error_message ||
                           errorData.detail ||
                           errorData.message ||
                           `HTTP error! status: ${response.status}`;

        // Check for 401 Unauthorized - token expired or invalid
        if (response.status === 401) {
          console.error('🔐 401 Unauthorized - token expired or invalid');
          if (this.onAuthError) {
            this.onAuthError(new Error('Authentication token expired'));
          }
        }

        throw new Error(errorMessage);
      }

      const responseData = await response.json();
      console.log(`📡 API Response data:`, responseData);

      return responseData;
    } catch (error) {
      console.error(`❌ API Request failed:`, error);
      throw error;
    }
  }

  /**
   * Helper to parse structured data fields
   * @param {any} field - Field that might be JSON string or object
   * @returns {any} Parsed field
   */
  parseField(field) {
    if (!field) return '';
    
    // If it's already an object/array, return as-is
    if (typeof field === 'object' && field !== null) {
      return field;
    }
    
    // If it's a string that looks like JSON, try to parse it
    if (typeof field === 'string') {
      const trimmed = field.trim();
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
          return JSON.parse(field);
        } catch (e) {
          console.warn('Failed to parse JSON field:', e);
          return field;
        }
      }
    }
    
    return field;
  }

  mapAudioPayload(payload, sessionId) {
    if (!payload || typeof payload !== 'object') {
      return null;
    }

    const fallbackSession = sessionId || payload.session_id || 'default-session';

    return {
      id: payload.id || `${fallbackSession}-${Date.now()}`,
      sessionId: payload.session_id || fallbackSession,
      url: payload.url,
      mimeType: payload.mime_type || 'audio/mpeg',
      durationSec: payload.duration_sec ?? null,
      createdAt: payload.created_at || new Date().toISOString(),
      sizeBytes: payload.size_bytes ?? null,
      provider: payload.provider || null,
    };
  }

  /**
   * Transform API response to match frontend expectations
   * @param {Object} response - Raw API response
   * @returns {Object} Transformed response
   */
  transformResponse(response) {
    if (!response.message?.structured_data) {
      return {
        response: 'No response received',
        structuredData: null,
        sessionId: response.session_id
      };
    }
    
    const structuredData = response.message.structured_data;
    const sessionId = response.message?.session_id || response.session_id;
    const audioPayload = structuredData.audio ? this.mapAudioPayload(structuredData.audio, sessionId) : null;

    // Parse fields that might be JSON strings
    const transformedData = {
      narrative: this.parseField(structuredData.narrative),
      turn: structuredData.turn || '',
      status: structuredData.status || '',
      characters: this.parseField(structuredData.characters),
      player_options: this.parseField(structuredData.player_options),
      // turn info block from backend for UI turn indicator
      turn_info: this.parseField(structuredData.turn_info),
      // Combat status fields
      combat_status: this.parseField(structuredData.combat_status),
      combat_state: structuredData.combat_state || null,
      action_breakdown: this.parseField(structuredData.action_breakdown),
      turn_resolution: this.parseField(structuredData.turn_resolution),
      environmental_conditions: structuredData.environmental_conditions || '',
      immediate_threats: structuredData.immediate_threats || '',
      story_progression: structuredData.story_progression || '',
      answer: structuredData.answer || 'No answer received',
      summary: structuredData.summary || '',
      observations: this.parseField(structuredData.observations) || [],
      streaming_answer: structuredData.streaming_answer || '',
      streaming_tool_events: this.parseField(structuredData.streaming_tool_events) || [],
      streamed: Boolean(structuredData.streamed),
      // Image fields
      generated_image_url: structuredData.generated_image_url || '',
      generated_image_path: structuredData.generated_image_path || '',
      generated_image_prompt: structuredData.generated_image_prompt || '',
      generated_image_type: structuredData.generated_image_type || '',
      audio: audioPayload,
      perception_checks:
        this.parseField(structuredData.metadata?.perception_checks) ||
        this.parseField(structuredData.perception_checks) ||
        this.parseField(structuredData.observations) ||
        [],
    };

    return {
      response: transformedData.answer,
      structuredData: transformedData,
      sessionId,
    };
  }

  /**
   * Send a chat message
   * @param {string} message - The message to send
   * @param {string} sessionId - The session/campaign ID
   * @returns {Promise<Object>} Transformed response
   */
  async sendMessage(message, sessionId) {
    if (!sessionId) {
      throw new Error('sessionId is required to send a message');
    }
    console.log('💬 Sending chat message:', message);
    console.log('💬 Session ID:', sessionId);
    
    const requestData = {
      message,
      session_id: sessionId,
      input_type: 'CHAT'
    };
    console.log('💬 Request data:', requestData);
    
    const response = await this.makeRequest('/api/chat/compat', requestData);
    
    return this.transformResponse(response);
  }

  /**
   * Start a new campaign
   * @param {boolean} blank - Whether to create a blank campaign
   * @returns {Promise<Object>} Transformed response
   */
  async startNewCampaign(blank = false) {
    console.log('🎲 Starting new campaign, blank:', blank);
    
    const response = await this.makeRequest('/api/campaigns/new', {
      blank
    });
    
    const transformed = this.transformResponse(response);
    // Ensure session_id is set for new campaigns
    transformed.sessionId = response.session_id || response.message?.session_id;
    
    return transformed;
  }

  /**
   * Send a new campaign request (compatibility method)
   * @returns {Promise<Object>} Transformed response
   */
  async sendNewCampaignRequest() {
    return this.startNewCampaign(false);
  }

  /**
   * Send a blank campaign request (compatibility method)
   * @returns {Promise<Object>} Transformed response
   */
  async sendBlankCampaignRequest() {
    return this.startNewCampaign(true);
  }

  /**
   * Add context to a campaign
   * @param {string} contextMessage - The context to add
   * @param {string} sessionId - The session/campaign ID
   * @returns {Promise<Object>} Success response
   */
  async addContext(contextMessage, sessionId) {
    if (!sessionId) {
      throw new Error('sessionId is required to add context');
    }
    console.log('📝 Adding context to campaign:', sessionId);
    
    const response = await this.makeRequest('/api/campaigns/add-context', {
      context: contextMessage,
      session_id: sessionId
    });
    
    return {
      success: response.success,
      message: response.message
    };
  }

  /**
   * Fetch recent images (compatibility with protobuf service)
   * @param {number} limit - Maximum number of images to fetch
   * @param {string} campaignId - Optional campaign ID filter
   * @returns {Promise<Array>} Array of image metadata
   */
  async fetchRecentImages(limit = 10, campaignId = null) {
    try {
      if (!campaignId) {
        console.warn('fetchRecentImages called without campaignId; returning empty list.');
        return [];
      }
      const params = new URLSearchParams({
        limit: String(limit),
        campaign_id: campaignId
      });
      const url = `${this.baseUrl}/api/images?${params}`;
      const data = await this.fetchJsonWithDedupe(url, { method: 'GET' }, { maxAttempts: 3, baseDelayMs: 800, jitterMs: 250 });
      return Array.isArray(data.images) ? data.images : [];
    } catch (error) {
      console.error('❌ Error fetching recent images:', error);
      return [];
    }
  }

  /**
   * Use the compatibility endpoint that accepts the same format as protobuf
   * This makes migration easier by keeping the same request format
   * @param {string} message - The message
   * @param {string} sessionId - Session ID
   * @param {string} inputType - Type of input (CHAT, NEW_CAMPAIGN, etc.)
   * @returns {Promise<Object>} Transformed response
   */
  async sendCompatRequest(message, sessionId, inputType) {
    console.log(`📡 Sending compat request, type: ${inputType}`);
    
    const response = await this.makeRequest('/api/chat/compat', {
      message,
      session_id: sessionId,
      input_type: inputType
    });
    
    return this.transformResponse(response);
  }

  // Campaign Management Methods
  
  /**
   * List all campaigns
   * @param {Object} options - Query options
   * @returns {Promise<Object>} Campaigns list
   */
  async listCampaigns(options = {}) {
    const params = new URLSearchParams({
      limit: String(options.limit ?? 50),
      offset: String(options.offset ?? 0),
      sort_by: options.sortBy ?? 'last_played',
      ascending: String(options.ascending ?? false)
    });

    const response = await fetch(`${this.baseUrl}/api/campaigns?${params}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Load a specific campaign
   * @param {string} campaignId - Campaign ID
   * @returns {Promise<Object>} Campaign data
   */
  async loadCampaign(campaignId) {
    const encodedId = this.encodePathSegment(campaignId);
    const response = await fetch(`${this.baseUrl}/api/campaigns/${encodedId}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Save a campaign
   * @param {string} campaignId - Campaign ID
   * @param {Object} data - Campaign data
   * @returns {Promise<Object>} Save result
   */
  async saveCampaign(campaignId, data) {
    const encodedId = this.encodePathSegment(campaignId);
    return this.makeRequest(`/api/campaigns/${encodedId}/save`, data);
  }

  /**
   * Create a new campaign
   * @param {Object} campaignData - Campaign creation data
   * @returns {Promise<Object>} Created campaign
   */
  async createCampaign(campaignData) {
    return this.makeRequest('/api/campaigns', campaignData);
  }

  /**
   * Create arena quick start campaign
   * @param {Object} options - Arena options (player_count, npc_count, difficulty)
   * @returns {Promise<Object>} Arena campaign response
   */
  async createArenaQuickStart(options = {}) {
    const payload = {
      player_count: options.player_count || 2,
      npc_count: options.npc_count || 2,
      difficulty: options.difficulty || 'medium',
    };
    return this.makeRequest('/api/arena/quick-start', payload);
  }

  /**
   * Get campaign structured data
   * @param {string} campaignId - Campaign ID
   * @param {number} limit - Limit results
   * @returns {Promise<Object>} Structured data
   */
  async getCampaignStructuredData(campaignId, limit = 10) {
    const encodedId = this.encodePathSegment(campaignId);
    const response = await fetch(`${this.baseUrl}/api/campaigns/${encodedId}/structured-data?limit=${limit}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * List simple campaigns
   * @returns {Promise<Object>} Simple campaigns list
   */
  async listSimpleCampaigns({ role = null } = {}) {
    const headers = {
      'Content-Type': 'application/json',
    };

    // Add auth token if available
    if (this.getAccessToken) {
      try {
        const token = await this.getAccessToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      } catch (error) {
        console.warn('Failed to get auth token for listSimpleCampaigns:', error);
      }
    }

    const queryParams = new URLSearchParams();
    if (role) {
      queryParams.set('role', role);
    }
    const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';
    const response = await fetch(`${this.baseUrl}/api/simple-campaigns${queryString}`, { headers });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Load a simple campaign (activates it for DM use)
   * @param {string} campaignId - Campaign ID
   * @returns {Promise<Object>} Simple campaign data
   */
  async loadSimpleCampaign(campaignId) {
    const encodedId = this.encodePathSegment(campaignId);
    const data = await this.fetchJsonWithDedupe(
      `${this.baseUrl}/api/simple-campaigns/${encodedId}`,
      { method: 'GET' }
    );
    if (data?.structured_data?.audio) {
      data.structured_data.audio = this.mapAudioPayload(
        data.structured_data.audio,
        data.session_id || campaignId
      );
    }
    return data;
  }

  /**
   * Read a simple campaign without activating it (for player view)
   * @param {string} campaignId - Campaign ID
   * @returns {Promise<Object>} Simple campaign data
   */
  async readSimpleCampaign(campaignId) {
    const encodedId = this.encodePathSegment(campaignId);
    const data = await this.fetchJsonWithDedupe(
      `${this.baseUrl}/api/simple-campaigns/${encodedId}/read`,
      { method: 'GET' }
    );
    if (data?.structured_data?.audio) {
      data.structured_data.audio = this.mapAudioPayload(
        data.structured_data.audio,
        data.session_id || campaignId
      );
    }
    return data;
  }

  /**
   * Get the currently active campaign ID from the DM interface
   * @returns {Promise<string|null>} Active campaign ID or null if none active
   */
  async getActiveCampaign() {
    const headers = { 'Content-Type': 'application/json' };
    
    // Add Auth0 token if available
    if (this.getAccessToken) {
      try {
        const token = await this.getAccessToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      } catch (error) {
        console.warn('Failed to get Auth0 token for active campaign:', error);
      }
    }
    
    try {
      const response = await fetch(`${this.baseUrl}/api/active-campaign`, {
        method: 'GET',
        headers,
        // Add timeout to prevent hanging
        signal: AbortSignal.timeout(5000)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      return data.active_campaign_id;
    } catch (error) {
      // If it's a network error (backend not running), return null gracefully
      if (error.name === 'AbortError' || error.message.includes('Failed to fetch') || error.message.includes('ERR_')) {
        console.warn('Backend not accessible for active campaign check:', error.message);
        return null;
      }
      // Re-throw other errors
      throw error;
    }
  }

  // Character Management Methods

  /**
   * Get all pregenerated characters
   * @returns {Promise<Object>} List of pregenerated characters
   */
  async getPregeneratedCharacters() {
    const response = await fetch(`${this.baseUrl}/api/characters/pregenerated`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Generate a character
   * @param {Object} characterData - Character generation data
   * @returns {Promise<Object>} Generated character
   */
  async generateCharacter(characterData) {
    return this.makeRequest('/api/characters/generate', characterData);
  }

  /**
   * Create a one-time session invite token.
   * @param {string} sessionId - Session ID to share
   * @param {Object} options - Additional options
   * @param {boolean} options.regenerate - Invalidate existing invites first
   * @param {number|null} options.expiresInMinutes - Optional expiration window
   * @returns {Promise<Object>} Invite response
   */
  async createSessionInvite(sessionId, { regenerate = false, expiresInMinutes = null } = {}) {
    const payload = {
      session_id: sessionId,
      regenerate,
    };
    if (expiresInMinutes) {
      payload.expires_in_minutes = expiresInMinutes;
    }
    return this.makeRequest('/api/sessions/share', payload);
  }

  /**
   * Join a shared session using an invite token.
   * @param {string} inviteToken - Invite token provided by the session owner
   * @returns {Promise<Object>} Join response
   */
  async joinSessionByInvite(inviteToken) {
    return this.makeRequest('/api/sessions/join', {
      invite_token: inviteToken,
    });
  }

  /**
   * Get character voices
   * @returns {Promise<Object>} Available voices
   */
  async getCharacterVoices() {
    const response = await fetch(`${this.baseUrl}/api/characters/voices`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  // Image Generation Methods

  /**
   * Generate an image
   * @param {Object} imageData - Image generation data
   * @returns {Promise<Object>} Generated image
   */
  async generateImage(imageData) {
    return this.makeRequest('/api/generate-image', imageData);
  }

  /**
   * Get available image models
   * @returns {Promise<Object>} Available models
   */
  async getImageModels() {
    const response = await fetch(`${this.baseUrl}/api/image-models`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  // TTS Methods

  /**
   * Get TTS queue status
   * @returns {Promise<Object>} Queue status
   */
  async getTTSQueueStatus(sessionId = null) {
    const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    const url = `${this.baseUrl}/api/tts/queue/status${query}`;
    return this.fetchJsonWithDedupe(url, { method: 'GET' }, { maxAttempts: 3, baseDelayMs: 800, jitterMs: 250 });
  }

  /**
   * Synthesize TTS audio
   * @param {Object} ttsData - TTS synthesis data
   * @returns {Promise<Blob>} Audio blob
   */
  async synthesizeTTS(ttsData, sessionId = null) {
    const headers = { 'Content-Type': 'application/json' };
    
    // Add Auth0 token if available
    if (this.getAccessToken) {
      try {
        const accessToken = await this.getAccessToken();
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
      } catch (error) {
        console.warn('Failed to get Auth0 token for TTS:', error);
      }
    }
    
    const payload = { ...ttsData };
    if (sessionId && !payload.session_id) {
      payload.session_id = sessionId;
    }

    const response = await fetch(`${this.baseUrl}/api/tts/synthesize`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    const sessionForPayload = payload.session_id || sessionId;
    if (data?.audio) {
      data.audio = this.mapAudioPayload(data.audio, sessionForPayload);
    }
    return data;
  }

  /**
   * Stop TTS playback
   * @returns {Promise<Object>} Stop result
   */
  async stopTTS(sessionId = null) {
    const payload = sessionId ? { session_id: sessionId } : {};
    return this.makeRequest('/api/tts/queue/stop', payload);
  }

  /**
   * Get available TTS voices
   * @returns {Promise<Object>} List of available voices
   */
  async getTTSVoices() {
    // Simple in-memory cache to avoid duplicate bursts from multiple components
    if (!this._voicesCache) {
      this._voicesCache = { data: null, ts: 0 };
    }
    const now = Date.now();
    const cacheTtlMs = 60 * 1000; // 1 minute cache
    if (this._voicesCache.data && (now - this._voicesCache.ts) < cacheTtlMs) {
      return this._voicesCache.data;
    }

    const url = `${this.baseUrl}/api/tts/voices`;
    const data = await this.fetchJsonWithDedupe(url, { method: 'GET' }, { maxAttempts: 3, baseDelayMs: 800, jitterMs: 250 });
    this._voicesCache = { data, ts: Date.now() };
    return data;
  }

  /**
   * Stop TTS queue playback
   * @returns {Promise<Object>} Stop result
   */
  async stopTTSQueue(sessionId = null) {
    const payload = sessionId ? { session_id: sessionId } : {};
    return this.makeRequest('/api/tts/queue/stop', payload);
  }

  /**
   * Trigger debug streaming chunks over WebSocket
   * @param {string} sessionId
   * @param {Object} options
   */
  async triggerDebugStream(sessionId, options = {}) {
    if (!sessionId) {
      throw new Error('sessionId is required to trigger debug stream');
    }
    const payload = {
      session_id: sessionId,
    };
    if (options.narrative) {
      payload.narrative = options.narrative;
    }
    if (options.playerResponse) {
      payload.player_response = options.playerResponse;
    }
    return this.makeRequest('/api/debug/streaming-test', payload);
  }

  /**
   * Run Dungeon Master with a fixed debug prompt
   * @param {string} sessionId
   * @param {Object} options
   */
  async runDebugDm(sessionId, options = {}) {
    if (!sessionId) {
      throw new Error('sessionId is required to run debug DM');
    }
    const payload = {
      session_id: sessionId,
    };
    if (options.prompt) {
      payload.prompt = options.prompt;
    }
    return this.makeRequest('/api/debug/run-streaming-direct', {
      ...payload,
      include_scene_context: options.includeSceneContext ?? true,
      include_conversation_context: options.includeConversationContext ?? true,
      analysis: options.analysis ?? null,
      force_audio: options.forceAudio ?? true,
    });
  }

  /**
   * Get TTS availability status
   * @returns {Promise<Object>} TTS availability info
   */
  async getTTSAvailability() {
    const headers = { 'Content-Type': 'application/json' };
    
    // Add Auth0 token if available
    if (this.auth0Client?.isAuthenticated) {
      try {
        const token = await this.auth0Client.getAccessTokenSilently();
        headers['Authorization'] = `Bearer ${token}`;
      } catch (error) {
        console.warn('Failed to get Auth0 token for TTS availability:', error);
      }
    }
    
    const response = await fetch(`${this.baseUrl}/api/tts/availability`, { headers });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Get connected players for a campaign (429-aware with dedupe)
   * @param {string} campaignId
   * @returns {Promise<Object>} { success, connected_players, count }
   */
  async getConnectedPlayers(campaignId) {
    if (!campaignId) throw new Error('campaignId is required');
    const encoded = this.encodePathSegment(campaignId);
    const url = `${this.baseUrl}/api/campaigns/${encoded}/connected-players`;
    // Use limited retries and jitter to avoid hammering when rate-limited
    return this.fetchJsonWithDedupe(url, { method: 'GET' }, { maxAttempts: 3, baseDelayMs: 800, jitterMs: 250 });
  }

  /**
   * Get TTS providers
   * @returns {Promise<Object>} List of TTS providers
   */
  async getTTSProviders() {
    const headers = { 'Content-Type': 'application/json' };

    // Add Auth0 token if available
    if (this.auth0Client?.isAuthenticated) {
      try {
        const token = await this.auth0Client.getAccessTokenSilently();
        headers['Authorization'] = `Bearer ${token}`;
      } catch (error) {
        console.warn('Failed to get Auth0 token for TTS providers:', error);
      }
    }

    const response = await fetch(`${this.baseUrl}/api/tts/providers`, { headers });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Switch image generation model
   * @param {Object} modelData - Model switching data
   * @returns {Promise<Object>} Switch result
   */
  async switchImageModel(modelData) {
    return this.makeRequest('/api/image-models/switch', modelData);
  }

  /**
   * Generate a new campaign
   * @param {Object} campaignData - Campaign generation data
   * @returns {Promise<Object>} Generated campaign
   */
  async generateCampaign(campaignData) {
    return this.makeRequest('/api/campaigns/generate', campaignData);
  }

  /**
   * Assign character to campaign slot
   * @param {string} campaignId - Campaign ID
   * @param {Object} slotData - Slot assignment data
   * @returns {Promise<Object>} Assignment result
   */
  async assignCharacterToSlot(campaignId, slotData) {
    const encodedId = this.encodePathSegment(campaignId);
    return this.makeRequest(`/api/campaigns/${encodedId}/characters/slot`, slotData);
  }

  /**
   * Initialize a campaign
   * @param {Object} initData - Campaign initialization data
   * @returns {Promise<Object>} Initialization result
   */
  async initializeCampaign(initData) {
    return this.makeRequest('/api/campaigns/initialize', initData);
  }

  /**
   * Delete a campaign
   * @param {string} campaignId - Campaign ID to delete
   * @returns {Promise<Object>} Deletion result
   */
  async deleteCampaign(campaignId) {
    const encodedId = this.encodePathSegment(campaignId);
    return this.makeRequest(`/api/campaigns/${encodedId}`, null, 'DELETE');
  }

  /**
   * Get voice activity status
   * @param {string} sessionId - Session ID
   * @returns {Promise<Object>} Voice activity status
   */
  async getVoiceActivity(sessionId) {
    const encodedSessionId = this.encodePathSegment(sessionId);
    const url = `${API_CONFIG.VOICE_ACTIVITY_ENDPOINT}/${encodedSessionId}`;
    return this.fetchJsonWithDedupe(url, { method: 'GET' }, { maxAttempts: 3, baseDelayMs: 800, jitterMs: 250 });
  }

  /**
   * Get auth providers
   * @returns {Promise<Object>} List of auth providers
   */
  async getAuthProviders() {
    const response = await fetch(`${this.baseUrl}/api/auth/providers`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }

  /**
   * Verify Auth0 token
   * @param {string} token - Auth0 token to verify
   * @returns {Promise<Object>} Verification result
   */
  async verifyAuth0Token(token) {
    const response = await fetch(`${this.baseUrl}/api/auth0/verify`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    if (!response.ok) {
      let body = '';
      try {
        body = await response.text();
      } catch (_) {
        // ignore
      }
      const err = new Error(`HTTP error! status: ${response.status}`);
      err.status = response.status;
      err.body = body;
      throw err;
    }
    return response.json();
  }

  // Portrait Generation Methods

  /**
   * Generate a portrait for a character
   * @param {string} characterId - Character ID
   * @param {string} campaignId - Campaign ID
   * @param {Object} options - Generation options
   * @returns {Promise<Object>} Portrait generation result
   */
  async generateCharacterPortrait(characterId, campaignId, options = {}) {
    const headers = { 'Content-Type': 'application/json' };

    // Add Auth0 token if available
    if (this.getAccessToken) {
      try {
        const accessToken = await this.getAccessToken();
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
      } catch (error) {
        console.warn('Failed to get Auth0 token for portrait generation:', error);
      }
    }

    const payload = {
      character_id: characterId,
      campaign_id: campaignId,
      regenerate: options.regenerate || false,
      custom_prompt_additions: options.custom_prompt_additions || null,
      character_data: options.character_data || null
    };

    const response = await fetch(`${this.baseUrl}/api/characters/${this.encodePathSegment(characterId)}/portrait/generate`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to generate portrait: ${errorText}`);
    }

    return response.json();
  }

  /**
   * Get portrait information for a character
   * @param {string} characterId - Character ID
   * @param {string} campaignId - Campaign ID
   * @returns {Promise<Object>} Portrait information
   */
  async getCharacterPortrait(characterId, campaignId) {
    const headers = {};

    // Add Auth0 token if available
    if (this.getAccessToken) {
      try {
        const accessToken = await this.getAccessToken();
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
      } catch (error) {
        console.warn('Failed to get Auth0 token for portrait retrieval:', error);
      }
    }

    const response = await fetch(
      `${this.baseUrl}/api/characters/${this.encodePathSegment(characterId)}/portrait?campaign_id=${this.encodePathSegment(campaignId)}`,
      { headers }
    );

    if (!response.ok) {
      throw new Error(`Failed to get portrait: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Update character visual metadata
   * @param {string} characterId - Character ID
   * @param {string} campaignId - Campaign ID
   * @param {Object} visualData - Visual field updates
   * @returns {Promise<Object>} Update result
   */
  async updateCharacterVisuals(characterId, campaignId, visualData) {
    const headers = { 'Content-Type': 'application/json' };

    // Add Auth0 token if available
    if (this.getAccessToken) {
      try {
        const accessToken = await this.getAccessToken();
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
      } catch (error) {
        console.warn('Failed to get Auth0 token for visual update:', error);
      }
    }

    const response = await fetch(
      `${this.baseUrl}/api/characters/${this.encodePathSegment(characterId)}?campaign_id=${this.encodePathSegment(campaignId)}`,
      {
        method: 'PATCH',
        headers,
        body: JSON.stringify(visualData)
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to update character visuals: ${errorText}`);
    }

    return response.json();
  }

  // ============================================================================
  // ROOM & SEAT MANAGEMENT API METHODS
  // ============================================================================

  /**
   * Get full room state with all seats for a campaign
   * @param {string} campaignId - Campaign/session ID
   * @returns {Promise<Object>} Room state with seats array
   */
  async getRoomState(campaignId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}`
    );
  }

  /**
   * Get lightweight room summary
   * @param {string} campaignId - Campaign/session ID
   * @returns {Promise<Object>} Room summary
   */
  async getRoomSummary(campaignId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/summary`
    );
  }

  /**
   * List room summaries for accessible campaigns
   * @param {Object} options
   * @param {string} [options.role='player'] - Role filter
   * @returns {Promise<Object>} Room summaries response
   */
  async listRoomSummaries({ role = 'player' } = {}) {
    const query = new URLSearchParams();
    if (role) {
      query.set('role', role);
    }
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/summaries${qs}`
    );
  }

  /**
   * List all seats for a campaign
   * @param {string} campaignId - Campaign/session ID
   * @returns {Promise<Array>} Array of seats
   */
  async listSeats(campaignId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/seats`
    );
  }

  /**
   * Get specific seat details
   * @param {string} campaignId - Campaign/session ID
   * @param {string} seatId - Seat ID
   * @returns {Promise<Object>} Seat details
   */
  async getSeat(campaignId, seatId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/seats/${this.encodePathSegment(seatId)}`
    );
  }

  /**
   * Occupy a seat (claim it for current user)
   * @param {string} campaignId - Campaign/session ID
   * @param {string} seatId - Seat ID to occupy
   * @returns {Promise<Object>} Updated seat
   */
  async occupySeat(campaignId, seatId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/seats/${this.encodePathSegment(seatId)}/occupy`,
      { method: 'POST' }
    );
  }

  /**
   * Release a seat (free it from current user)
   * @param {string} campaignId - Campaign/session ID
   * @param {string} seatId - Seat ID to release
   * @returns {Promise<Object>} Updated seat
   */
  async releaseSeat(campaignId, seatId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/seats/${this.encodePathSegment(seatId)}/release`,
      { method: 'POST' }
    );
  }

  /**
   * Vacate a seat (DM only - force remove player)
   * @param {string} campaignId - Campaign/session ID
   * @param {string} seatId - Seat ID to vacate
   * @param {Object} options - Vacate options
   * @param {boolean} options.notify_user - Whether to notify the vacated user
   * @returns {Promise<Object>} Updated seat
   */
  async vacateSeat(campaignId, seatId, options = { notify_user: true }) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/seats/${this.encodePathSegment(seatId)}/vacate`,
      {
        method: 'POST',
        body: JSON.stringify(options)
      }
    );
  }

  /**
   * Assign character to a seat
   * @param {string} campaignId - Campaign/session ID
   * @param {string} seatId - Seat ID
   * @param {Object} characterData - Character creation data
   * @returns {Promise<Object>} Result with character_id
   */
  async assignCharacterToSeat(campaignId, seatId, characterData) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/seats/${this.encodePathSegment(seatId)}/assign-character`,
      {
        method: 'POST',
        body: JSON.stringify({ character_data: characterData })
      }
    );
  }

  /**
   * Start the campaign (DM only)
   * @param {string} campaignId - Campaign/session ID
   * @returns {Promise<Object>} Campaign start result
   */
  async startCampaign(campaignId) {
    return this.fetchJsonWithDedupe(
      `${this.baseUrl}${this.v2Prefix}/rooms/${this.encodePathSegment(campaignId)}/start`,
      { method: 'POST' }
    );
  }

}

// Create and export singleton instance
export const apiService = new ApiService();
export default apiService;
