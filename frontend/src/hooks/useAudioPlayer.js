import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '../contexts/Auth0Context.jsx';

const MUTE_STORAGE_KEY = 'gaiaAudioMuted';
const DEFAULT_VOLUME = 1.0;

/**
 * Create an Audio element with iOS Safari compatibility attributes.
 * iOS Safari requires playsinline to prevent fullscreen mode and
 * to properly handle autoplay restrictions.
 */
const createAudioElement = () => {
  if (typeof Audio === 'undefined') {
    return null;
  }
  const audio = new Audio();
  // iOS Safari requires these attributes for proper playback
  audio.setAttribute('playsinline', '');
  audio.setAttribute('webkit-playsinline', '');
  // Prevent iOS from trying to AirPlay by default
  audio.setAttribute('x-webkit-airplay', 'deny');
  // Allow cross-origin audio (needed for streaming from API)
  audio.crossOrigin = 'anonymous';
  // Preload metadata for faster start
  audio.preload = 'auto';
  return audio;
};

/**
 * Shared audio player hook
 *
 * Provides common audio player functionality used by both AudioQueueContext
 * and AudioStreamContext, including:
 * - Audio element lifecycle management
 * - Mute state with localStorage persistence
 * - Volume control
 * - Auth token fetching helper
 */
export const useAudioPlayer = () => {
  const { getAccessTokenSilently, isAuthenticated } = useAuth();
  const audioRef = useRef(createAudioElement());

  // Mute state with localStorage initialization
  const [isMuted, setIsMuted] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return localStorage.getItem(MUTE_STORAGE_KEY) === 'true';
  });

  // Volume state
  const [volumeLevel, setVolumeLevel] = useState(DEFAULT_VOLUME);

  // Persist mute state to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    localStorage.setItem(MUTE_STORAGE_KEY, isMuted ? 'true' : 'false');
  }, [isMuted]);

  // Apply mute state to audio element
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.muted = isMuted;
  }, [isMuted]);

  // Apply volume to audio element
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.volume = volumeLevel;
  }, [volumeLevel]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        audio.src = '';
      }
    };
  }, []);

  // Toggle mute
  const toggleMute = useCallback((nextValue) => {
    if (typeof nextValue === 'boolean') {
      setIsMuted(nextValue);
    } else {
      setIsMuted((prev) => !prev);
    }
  }, []);

  // Set volume with clamping
  const setVolume = useCallback((value) => {
    const clamped = Math.min(1, Math.max(0, value));
    setVolumeLevel(clamped);
  }, []);

  // Get authentication token for audio requests
  const getAuthToken = useCallback(async () => {
    if (!isAuthenticated || typeof getAccessTokenSilently !== 'function') {
      return null;
    }
    try {
      return await getAccessTokenSilently();
    } catch (error) {
      console.warn('[AUDIO_PLAYER] Failed to obtain access token:', error);
      return null;
    }
  }, [isAuthenticated, getAccessTokenSilently]);

  return {
    audioRef,
    isMuted,
    setIsMuted,
    toggleMute,
    volumeLevel,
    setVolumeLevel,
    setVolume,
    getAuthToken,
  };
};
