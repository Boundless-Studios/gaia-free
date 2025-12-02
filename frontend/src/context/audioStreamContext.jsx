import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

import { API_CONFIG } from '../config/api.js';
import { useAudioPlayer } from '../hooks/useAudioPlayer.js';

export const AUDIO_STREAM_COMPLETED_EVENT = 'gaia:audio-stream-complete';

const AudioStreamContext = createContext(null);

/**
 * Synchronized audio streaming context
 *
 * Provides a single shared audio stream that all clients listen to simultaneously.
 * The DM controls when audio starts/stops, and all players hear the same thing at the same time.
 * Players can only mute/unmute their own audio.
 */
export const AudioStreamProvider = ({ children }) => {
  const { audioRef, isMuted, toggleMute, volumeLevel, setVolumeLevel, getAuthToken } = useAudioPlayer();
  const lastStreamInfoRef = React.useRef(null);
  const preferredMuteRef = React.useRef(isMuted);

  const [currentCampaignId, setCurrentCampaignId] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamUrl, setStreamUrl] = useState(null);
  const [needsUserGesture, setNeedsUserGesture] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [currentChunkIds, setCurrentChunkIds] = useState([]);

  // Normalize backend-provided URLs so they work when frontend and API use different hosts
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

  // Append an access token (if available) to the resolved URL without breaking existing params
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

  // Build streaming URL with authentication
  const buildStreamUrl = useCallback(async (campaignId, startOffset = 0) => {
    if (!campaignId) return null;

    const backendBase = API_CONFIG.BACKEND_URL || '';
    const normalizedBase = backendBase.endsWith('/')
      ? backendBase.slice(0, -1)
      : backendBase;
    const streamPath = `/api/audio/stream/${campaignId}`;
    const baseUrl = normalizedBase ? `${normalizedBase}${streamPath}` : streamPath;
    const params = new URLSearchParams();

    if (startOffset && Number.isFinite(startOffset) && startOffset > 0) {
      params.set('start_offset', startOffset.toFixed(2));
    }

    const token = await getAuthToken();
    if (token) {
      params.set('token', token);
    }

    const query = params.toString();
    const relativeUrl = query ? `${baseUrl}?${query}` : baseUrl;
    return ensureAbsoluteUrl(relativeUrl);
  }, [ensureAbsoluteUrl, getAuthToken]);

  const clearPendingChunks = useCallback(() => {
    setCurrentChunkIds([]);
  }, []);

  const dispatchStreamComplete = useCallback(() => {
    if (
      typeof window === 'undefined' ||
      !currentCampaignId ||
      !currentChunkIds.length
    ) {
      return;
    }
    window.dispatchEvent(
      new CustomEvent(AUDIO_STREAM_COMPLETED_EVENT, {
        detail: {
          campaignId: currentCampaignId,
          chunkIds: [...currentChunkIds],
        },
      }),
    );
    clearPendingChunks();
  }, [currentCampaignId, currentChunkIds, clearPendingChunks]);

  // Start streaming audio
  useEffect(() => {
    preferredMuteRef.current = isMuted;
  }, [isMuted]);

  const startStream = useCallback(async (
    campaignId,
    position_sec = 0,
    isLateJoin = false,
    chunkIds = [],
    providedStreamUrl = null,
  ) => {
    if (!audioRef.current || !campaignId) {
      console.warn('[AUDIO_STREAM] Cannot start stream - missing audio element or campaign ID');
      return;
    }

    console.log('[AUDIO_DEBUG] 🎬 Starting audio stream:', {
      campaignId,
      position_sec,
      isLateJoin,
      chunk_count: chunkIds.length,
      chunk_ids: chunkIds,
      provided_url: providedStreamUrl,
    });

    try {
      let url;

      if (providedStreamUrl) {
        // Use the provided stream URL (includes request_id from backend)
        url = await addAuthTokenToUrl(providedStreamUrl);
        console.log('[AUDIO_DEBUG] 🔗 Using provided stream URL (auth %s)',
          url && url.includes('token=') ? 'attached' : 'skipped');
      } else {
        // Build authenticated stream URL
        url = await buildStreamUrl(campaignId, isLateJoin ? position_sec : 0);
        console.log('[AUDIO_DEBUG] 🔗 Built stream URL from campaignId');
      }

      if (!url) {
        console.error('[AUDIO_STREAM] Failed to get stream URL');
        return;
      }

      lastStreamInfoRef.current = {
        campaignId,
        position_sec,
        isLateJoin,
        chunkIds: Array.isArray(chunkIds) ? chunkIds : [],
      };

      // Reset existing playback state before attaching new stream.
      try {
        if (!audioRef.current.paused) {
          audioRef.current.pause();
        }
      } catch (pauseError) {
        console.warn('[AUDIO_DEBUG] ⚠️ Unable to pause existing stream before reload', pauseError);
      }
      // Clearing the src ensures pending play() promises from the previous stream resolve before we attach the new one.
      audioRef.current.removeAttribute('src');
      audioRef.current.load();

      // Update state
      setCurrentCampaignId(campaignId);
      setStreamUrl(url);
      setIsStreaming(true);
      setCurrentChunkIds(Array.isArray(chunkIds) ? chunkIds : []);

      // Set audio source and load
      audioRef.current.src = url;
      audioRef.current.load();

      // Seek to position if late-joining
      if (isLateJoin && position_sec > 0) {
        audioRef.current.currentTime = position_sec;
        console.log('[AUDIO_STREAM] Late join - seeking to', position_sec, 'seconds');
      }

      // Start playback
      const attemptMutedAutoplayFallback = async () => {
        const audioEl = audioRef.current;
        if (!audioEl) {
          return false;
        }
        const previousMutedState = audioEl.muted;
        try {
          console.warn('[AUDIO_DEBUG] 🎧 Autoplay blocked - retrying with temporary mute fallback');
          audioEl.muted = true;
          await audioEl.play();
          const preferredMuted = preferredMuteRef.current;
          audioEl.muted = typeof preferredMuted === 'boolean' ? preferredMuted : previousMutedState;
          console.log('[AUDIO_DEBUG] ✅ Stream playback started after mute fallback');
          setNeedsUserGesture(false);
          setLastError(null);
          return true;
        } catch (mutedError) {
          audioEl.muted = previousMutedState;
          console.error('[AUDIO_DEBUG] ❌ Muted autoplay fallback failed:', mutedError);
          return false;
        }
      };

      try {
        await audioRef.current.play();
        console.log('[AUDIO_DEBUG] ✅ Stream playback started successfully');
        setNeedsUserGesture(false);
        setLastError(null);
      } catch (playError) {
        if (playError.name === 'AbortError') {
          console.warn('[AUDIO_DEBUG] ⚠️ play() aborted due to source change; retrying automatically');
          try {
            await audioRef.current.play();
            console.log('[AUDIO_DEBUG] ✅ Stream playback started after abort retry');
            setNeedsUserGesture(false);
            setLastError(null);
            return;
          } catch (retryError) {
            console.error('[AUDIO_DEBUG] ❌ Retry after abort failed:', retryError);
            setLastError(retryError.message);
            return;
          }
        }
        // Handle user gesture requirement
        if (playError.name === 'NotAllowedError') {
          const fallbackSucceeded = await attemptMutedAutoplayFallback();
          if (!fallbackSucceeded) {
            console.warn('[AUDIO_DEBUG] ⚠️ Autoplay blocked after fallback - user gesture required');
            setNeedsUserGesture(true);
            setLastError(playError.message);
          }
        } else {
          console.error('[AUDIO_DEBUG] ❌ Play error:', playError);
          setLastError(playError.message);
        }
      }
    } catch (error) {
      console.error('[AUDIO_STREAM] Failed to start stream:', error);
      setLastError(error.message);
      setIsStreaming(false);
    }
  }, [addAuthTokenToUrl, buildStreamUrl]);

  // Stop streaming audio
  const stopStream = useCallback(() => {
    if (!audioRef.current) return;

    console.log('[AUDIO_STREAM] Stopping stream');

    try {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current.load();
    } catch (error) {
      console.error('[AUDIO_STREAM] Error stopping stream:', error);
    }

    setIsStreaming(false);
    setStreamUrl(null);
    setCurrentCampaignId(null);
    setLastError(null);
    clearPendingChunks();
    lastStreamInfoRef.current = null;
  }, [clearPendingChunks]);

  // Manually start playback (for user gesture requirement)
  const retryLastStream = useCallback(async () => {
    const info = lastStreamInfoRef.current;
    if (!info || !info.campaignId) {
      console.warn('[AUDIO_STREAM] No cached stream info available for retry');
      return false;
    }
    await startStream(
      info.campaignId,
      info.position_sec || 0,
      info.isLateJoin ?? true,
      info.chunkIds || [],
    );
    return true;
  }, [startStream]);

  const resumePlayback = useCallback(async () => {
    if (!audioRef.current) return;

    try {
      await audioRef.current.play();
      setNeedsUserGesture(false);
      console.log('[AUDIO_STREAM] Playback resumed after user gesture');
    } catch (error) {
      if (error.name === 'NotSupportedError') {
        console.warn('[AUDIO_STREAM] Existing source unsupported, retrying stream attach');
        const retried = await retryLastStream();
        if (!retried) {
          setLastError(error.message);
        }
      } else {
        console.error('[AUDIO_STREAM] Failed to resume playback:', error);
        setLastError(error.message);
      }
    }
  }, [retryLastStream]);

  // Event listener for stream ended
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return undefined;
    }

    const handleEnded = async () => {
      console.log('[AUDIO_DEBUG] 🏁 Stream ended | chunk_ids=%s', JSON.stringify(currentChunkIds));
      console.log('[AUDIO_DEBUG] Dispatching stream completion event for campaign=%s', currentCampaignId);
      dispatchStreamComplete();
      setIsStreaming(false);

      // Backend auto-advances via WebSocket - frontend just waits for audio_stream_started event
      // No need to manually fetch next-pending anymore
      console.log('[AUDIO_DEBUG] ⏸️  Waiting for backend to send next audio_stream_started event (auto-advance)');
    };

    audio.addEventListener('ended', handleEnded);
    return () => {
      audio.removeEventListener('ended', handleEnded);
    };
  }, [dispatchStreamComplete, currentChunkIds, currentCampaignId]);

  const value = {
    // State
    currentCampaignId,
    isStreaming,
    streamUrl,
    isMuted,
    volumeLevel,
    needsUserGesture,
    lastError,
    pendingChunkCount: currentChunkIds.length,

    // Actions
    startStream,
    stopStream,
    resumePlayback,
    toggleMute,
    setVolumeLevel,
    clearPendingChunks,
  };

  return (
    <AudioStreamContext.Provider value={value}>
      {children}
    </AudioStreamContext.Provider>
  );
};

export const useAudioStream = () => {
  const context = useContext(AudioStreamContext);
  if (!context) {
    throw new Error('useAudioStream must be used within AudioStreamProvider');
  }
  return context;
};

export default AudioStreamContext;
