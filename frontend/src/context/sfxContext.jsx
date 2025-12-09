import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';

import { API_CONFIG } from '../config/api.js';
import { useAuth } from '../contexts/Auth0Context.jsx';
import sfxService from '../services/sfxService.js';

const SFX_VOLUME = 0.5; // 50% volume for sound effects
const SFX_MUTE_STORAGE_KEY = 'gaiaSfxMuted';

const SFXContext = createContext(null);

/**
 * Sound Effects Context
 *
 * Provides a separate audio element for playing sound effects simultaneously
 * with narration. Sound effects play at 50% volume and don't interrupt
 * the main audio stream.
 *
 * Features:
 * - Separate audio playback at 50% volume
 * - Sound effect generation via ElevenLabs API
 * - WebSocket event handling for broadcast SFX
 * - Mute state persistence
 */
export const SFXProvider = ({ children }) => {
  const { getAccessTokenSilently, isAuthenticated } = useAuth();

  // Separate audio element for SFX (plays simultaneously with narration)
  const sfxAudioRef = useRef(typeof Audio !== 'undefined' ? new Audio() : null);

  // SFX mute state with localStorage persistence
  const [isSfxMuted, setIsSfxMuted] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return localStorage.getItem(SFX_MUTE_STORAGE_KEY) === 'true';
  });

  const [isPlaying, setIsPlaying] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastError, setLastError] = useState(null);

  // SFX cache for deduplication (Map: cacheKey -> audioPayload)
  const [sfxCache, setSfxCache] = useState(new Map());

  // Initialize sfxService with token getter
  useEffect(() => {
    if (isAuthenticated && getAccessTokenSilently) {
      sfxService.setAccessTokenGetter(getAccessTokenSilently);
    }
  }, [isAuthenticated, getAccessTokenSilently]);

  // Persist SFX mute state to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    localStorage.setItem(SFX_MUTE_STORAGE_KEY, isSfxMuted ? 'true' : 'false');
  }, [isSfxMuted]);

  // Apply mute state and fixed volume to SFX audio element
  useEffect(() => {
    const audio = sfxAudioRef.current;
    if (!audio) {
      return;
    }
    audio.muted = isSfxMuted;
    audio.volume = SFX_VOLUME;
  }, [isSfxMuted]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const audio = sfxAudioRef.current;
      if (audio) {
        audio.pause();
        audio.src = '';
      }
    };
  }, []);

  // Get authentication token for audio requests
  const getAuthToken = useCallback(async () => {
    if (!isAuthenticated || typeof getAccessTokenSilently !== 'function') {
      return null;
    }
    try {
      return await getAccessTokenSilently();
    } catch (error) {
      console.warn('[SFX] Failed to obtain access token:', error);
      return null;
    }
  }, [isAuthenticated, getAccessTokenSilently]);

  // Normalize backend-provided URLs
  const ensureAbsoluteUrl = useCallback((rawUrl) => {
    if (!rawUrl || typeof rawUrl !== 'string') {
      return rawUrl || null;
    }

    const trimmed = rawUrl.trim();
    if (!trimmed) {
      return null;
    }

    if (/^https?:\/\//i.test(trimmed)) {
      return trimmed;
    }

    if (trimmed.startsWith('//')) {
      const protocol = typeof window !== 'undefined' && window.location?.protocol
        ? window.location.protocol
        : 'https:';
      return `${protocol}${trimmed}`;
    }

    const normalizedPath = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
    const configBaseRaw = API_CONFIG.BACKEND_URL || '';
    const normalizedConfigBase = configBaseRaw.endsWith('/')
      ? configBaseRaw.slice(0, -1)
      : configBaseRaw;
    const fallbackOrigin = typeof window !== 'undefined' && window.location?.origin
      ? window.location.origin
      : '';
    const base = normalizedConfigBase || fallbackOrigin;
    if (!base) {
      return normalizedPath;
    }
    return `${base}${normalizedPath}`;
  }, []);

  // Add auth token to URL
  const addAuthTokenToUrl = useCallback(async (rawUrl) => {
    const absoluteUrl = ensureAbsoluteUrl(rawUrl);
    if (!absoluteUrl) {
      return null;
    }

    const token = await getAuthToken();
    if (!token) {
      return absoluteUrl;
    }

    try {
      const urlObj = new URL(absoluteUrl);
      urlObj.searchParams.set('token', token);
      return urlObj.toString();
    } catch (error) {
      const separator = absoluteUrl.includes('?') ? '&' : '?';
      return `${absoluteUrl}${separator}token=${encodeURIComponent(token)}`;
    }
  }, [ensureAbsoluteUrl, getAuthToken]);

  /**
   * Generate cache key from sfxId or phrase
   * @param {string|null} sfxId - Catalog ID
   * @param {string} phrase - Text phrase
   * @returns {string} Cache key
   */
  const getCacheKey = useCallback((sfxId, phrase) => {
    return sfxId || phrase.toLowerCase().trim();
  }, []);

  /**
   * Retrieve cached SFX audio payload
   * @param {string|null} sfxId - Catalog ID
   * @param {string} phrase - Text phrase
   * @returns {Object|null} Cached audio payload or null
   */
  const getCachedSFX = useCallback((sfxId, phrase) => {
    const key = getCacheKey(sfxId, phrase);
    return sfxCache.get(key) || null;
  }, [sfxCache, getCacheKey]);

  /**
   * Store SFX audio payload in cache
   * @param {string|null} sfxId - Catalog ID
   * @param {string} phrase - Text phrase
   * @param {Object} audioPayload - Audio data to cache
   */
  const cacheSFX = useCallback((sfxId, phrase, audioPayload) => {
    const key = getCacheKey(sfxId, phrase);
    setSfxCache(prev => {
      const newCache = new Map(prev);
      newCache.set(key, audioPayload);
      return newCache;
    });
    console.log('[SFX] Cached audio for:', key);
  }, [getCacheKey]);

  /**
   * Play a sound effect from a URL
   * This plays simultaneously with any existing narration audio
   */
  const playSfx = useCallback(async (audioUrl) => {
    if (!sfxAudioRef.current) {
      console.warn('[SFX] Audio element not available');
      return;
    }

    try {
      const url = await addAuthTokenToUrl(audioUrl);
      if (!url) {
        console.error('[SFX] Failed to get audio URL');
        return;
      }

      console.log('[SFX] Playing sound effect:', url.substring(0, 100) + '...');

      const audio = sfxAudioRef.current;

      // Reset any previous playback
      audio.pause();
      audio.currentTime = 0;

      // Set source and play
      audio.src = url;
      audio.volume = SFX_VOLUME;
      audio.load();

      setIsPlaying(true);
      setLastError(null);

      await audio.play();
      console.log('[SFX] Sound effect playing successfully');
    } catch (error) {
      console.error('[SFX] Failed to play sound effect:', error);
      setLastError(error.message);
      setIsPlaying(false);
    }
  }, [addAuthTokenToUrl]);

  /**
   * Play a sound effect from audio payload received from WebSocket/API
   */
  const playSfxFromPayload = useCallback(async (audioPayload) => {
    if (!audioPayload?.url) {
      console.warn('[SFX] No URL in audio payload');
      return;
    }
    await playSfx(audioPayload.url);
  }, [playSfx]);

  /**
   * Handle sfx_available WebSocket event
   * Called when a sound effect is broadcast to the session
   */
  const handleSfxAvailable = useCallback((data, sessionId) => {
    const { audio } = data;
    if (!audio?.url) {
      console.warn('[SFX] sfx_available missing audio URL');
      return;
    }

    console.log('[SFX] 🔊 Playing broadcast sound effect | session=%s', sessionId);
    playSfxFromPayload(audio);
  }, [playSfxFromPayload]);

  /**
   * Generate a sound effect from selected text
   * @param {string} text - Description of the sound effect
   * @param {string} sessionId - Campaign/session ID for broadcasting
   * @param {string|null} sfxId - Optional catalog ID for caching
   * @returns {Promise<Object|null>} Generated sound effect data or null on error
   */
  const generateSoundEffect = useCallback(async (text, sessionId, sfxId = null) => {
    if (!text || text.trim().length === 0) {
      console.log('[SFX] No text provided for sound effect generation');
      return null;
    }

    setIsGenerating(true);
    setLastError(null);

    try {
      console.log('[SFX] Generating sound effect for:', text.substring(0, 50) + '...');

      const result = await sfxService.generateSoundEffect(
        {
          text: text.trim(),
          prompt_influence: 0.7,
          duration_seconds: 3
        },
        sessionId,
      );

      console.log('[SFX] Sound effect generation triggered', {
        sessionId,
        textLength: text.length,
        sfxId,
      });

      // Cache the result if audio is available
      if (result?.audio) {
        cacheSFX(sfxId, text, result.audio);
      }

      return result;
    } catch (error) {
      console.error('[SFX] Failed to generate sound effect:', error);
      setLastError(error.message);
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, [cacheSFX]);

  /**
   * Check if SFX service is available
   * @returns {Promise<boolean>}
   */
  const checkAvailability = useCallback(async () => {
    try {
      const result = await sfxService.getAvailability();
      return result?.available ?? false;
    } catch (error) {
      console.error('[SFX] Failed to check availability:', error);
      return false;
    }
  }, []);

  // Handle audio ended event
  useEffect(() => {
    const audio = sfxAudioRef.current;
    if (!audio) {
      return undefined;
    }

    const handleEnded = () => {
      console.log('[SFX] Sound effect playback ended');
      setIsPlaying(false);
    };

    const handleError = (e) => {
      console.error('[SFX] Audio error:', e);
      setLastError(e.message || 'Audio playback error');
      setIsPlaying(false);
    };

    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    return () => {
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
  }, []);

  // Toggle SFX mute
  const toggleSfxMute = useCallback((nextValue) => {
    if (typeof nextValue === 'boolean') {
      setIsSfxMuted(nextValue);
    } else {
      setIsSfxMuted((prev) => !prev);
    }
  }, []);

  // Stop current SFX playback
  const stopSfx = useCallback(() => {
    const audio = sfxAudioRef.current;
    if (!audio) {
      return;
    }
    audio.pause();
    audio.currentTime = 0;
    setIsPlaying(false);
  }, []);

  const value = {
    // State
    isSfxMuted,
    isPlaying,
    isGenerating,
    lastError,
    sfxVolume: SFX_VOLUME,

    // Playback actions
    playSfx,
    playSfxFromPayload,
    stopSfx,
    toggleSfxMute,

    // Generation actions
    generateSoundEffect,
    checkAvailability,

    // Cache actions
    getCachedSFX,
    cacheSFX,

    // WebSocket handler
    handleSfxAvailable,
  };

  return (
    <SFXContext.Provider value={value}>
      {children}
    </SFXContext.Provider>
  );
};

export const useSFX = () => {
  const context = useContext(SFXContext);
  if (!context) {
    throw new Error('useSFX must be used within SFXProvider');
  }
  return context;
};

export default SFXContext;
