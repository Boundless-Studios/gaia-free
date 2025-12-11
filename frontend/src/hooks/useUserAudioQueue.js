import { useCallback, useRef, useState, useEffect } from 'react';
import { API_CONFIG } from '../config/api.js';

/**
 * Create an Audio element with iOS Safari compatibility attributes.
 * iOS Safari requires playsinline to prevent fullscreen mode and
 * to properly handle autoplay restrictions.
 */
const createIOSCompatibleAudio = () => {
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

// Shared audio element to maintain browser autoplay permission
let sharedAudioElement = null;
let audioUnlocked = false;

// SINGLETON: Global audio element and queue shared across all hook instances
// This ensures only one audio plays at a time, even with multiple components
let globalAudioElement = null;
let globalPlaybackQueue = [];
let globalIsProcessing = false;
let globalQueuedChunkIds = new Set();
let globalCurrentRequestId = null;

// Track pending acknowledgment confirmations
// Map of queue_id -> { resolve, reject, timeout }
const pendingConfirmations = new Map();
const CONFIRMATION_TIMEOUT_MS = 3000; // 3 second timeout for confirmation

/**
 * Handle confirmation of audio_played from backend via WebSocket.
 * Call this when receiving 'audio_played_confirmed' event.
 *
 * @param {Object} data - Confirmation data { queue_id, success, error? }
 */
export function handleAudioPlayedConfirmation(data) {
  const { queue_id: queueId, success, error } = data;
  if (!queueId) {
    console.warn('🎵 [USER_QUEUE] Received confirmation without queue_id');
    return;
  }

  const pending = pendingConfirmations.get(queueId);
  if (!pending) {
    // Confirmation arrived but we weren't waiting for it (maybe timed out already)
    console.debug('🎵 [USER_QUEUE] Received confirmation for unknown queue_id:', queueId);
    return;
  }

  // Clear timeout
  if (pending.timeout) {
    clearTimeout(pending.timeout);
  }
  pendingConfirmations.delete(queueId);

  if (success) {
    console.log('🎵 [USER_QUEUE] Confirmed played:', queueId);
    pending.resolve(true);
  } else {
    console.warn('🎵 [USER_QUEUE] Confirmation failed:', queueId, error);
    pending.reject(new Error(error || 'Backend failed to mark as played'));
  }
}

/**
 * Unlock audio playback by playing a silent audio on user interaction.
 * Call this on any user click/tap to ensure audio can play.
 *
 * iOS Safari is particularly strict about requiring user gestures for audio.
 * This function creates a silent audio element and plays it to "prime" the
 * browser's audio context, allowing subsequent audio playback.
 */
export function unlockAudio() {
  if (audioUnlocked) return Promise.resolve(true);

  if (!sharedAudioElement) {
    sharedAudioElement = createIOSCompatibleAudio();
    // Use a tiny silent audio data URI (approximately 0.1s of silence)
    sharedAudioElement.src = 'data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYoRwmHAAAAAAD/+1DEAAAGAAGn9AAAIiwijW80AAQAAAT/JJ5mn//t/5J//l/kn5J+Sf/5J/t//5f5J+Sf//+X+Sf5J5J+X/8k/ygAAANtVVVV//tQxA4AAADSAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
  }

  // iOS Safari requires load() before play() to recognize the user gesture
  sharedAudioElement.load();

  // Call play() immediately - don't await anything before this to keep gesture context active
  const playPromise = sharedAudioElement.play();

  return playPromise
    .then(() => {
      audioUnlocked = true;
      console.log('🎵 [AUDIO] Browser audio unlocked successfully');
      return true;
    })
    .catch((err) => {
      // On iOS, NotAllowedError means gesture wasn't recognized - may need another tap
      if (err.name === 'NotAllowedError') {
        console.warn('🎵 [AUDIO] Audio unlock requires user gesture (iOS restriction)');
      } else {
        console.warn('🎵 [AUDIO] Failed to unlock audio:', err.name, err.message);
      }
      return false;
    });
}

/**
 * Custom hook for user-scoped audio queue playback
 *
 * Handles fetching and playing audio chunks from the user's queue.
 * This replaces connection-scoped playback with stable user-scoped queues.
 *
 * Features:
 * - SINGLETON: Global queue shared across all hook instances
 * - In-memory FIFO queue to prevent overlapping playback
 * - Sequential playback guaranteed per user
 * - Rapid triggers are queued, not dropped
 * - Handles browser autoplay restrictions
 *
 * @param {Object} params - Configuration object
 * @param {Object} params.user - Auth0 user object (must have email or sub)
 * @param {Object} params.audioStream - Audio stream context
 * @param {Object} params.apiService - API service instance
 * @param {Function} params.socketEmit - Optional Socket.IO emit function for WebSocket acknowledgment
 * @param {string} params.campaignId - Optional campaign ID for WebSocket acknowledgment
 * @returns {Object} Audio queue management interface
 */
export function useUserAudioQueue({ user, audioStream, apiService, socketEmit, campaignId }) {
  // Use global singletons instead of instance-specific refs
  // This ensures all audio from any component goes through the same queue

  // Fetch lock to prevent concurrent API requests (can remain instance-specific)
  const isFetchingRef = useRef(false);
  // Track if audio is blocked
  const [audioBlocked, setAudioBlocked] = useState(false);
  // Track if queue is currently playing (synced from global state)
  const [isPlaying, setIsPlaying] = useState(globalIsProcessing);

  // Stop queue playback and clear queue (called when synchronized stream starts or new request)
  const stopQueuePlayback = useCallback(() => {
    console.log('🎵 [USER_QUEUE] Stopping queue playback');
    // Clear the global queue
    globalPlaybackQueue = [];
    globalQueuedChunkIds.clear();
    globalCurrentRequestId = null;
    // Stop current audio
    if (globalAudioElement) {
      globalAudioElement.pause();
      globalAudioElement.src = '';
    }
    // Reset processing lock (will cause current loop to exit on next iteration)
    globalIsProcessing = false;
    setIsPlaying(false);
  }, []);

  // Try to unlock audio on mount and user interactions
  useEffect(() => {
    const handleInteraction = () => {
      unlockAudio().then(unlocked => {
        if (unlocked) setAudioBlocked(false);
      });
    };

    // Listen for user interactions to unlock audio
    document.addEventListener('click', handleInteraction, { once: true });
    document.addEventListener('keydown', handleInteraction, { once: true });

    return () => {
      document.removeEventListener('click', handleInteraction);
      document.removeEventListener('keydown', handleInteraction);
    };
  }, []);

  const registerQueueId = useCallback((queueId) => {
    if (!queueId) {
      return true;
    }
    const normalizedId = String(queueId);
    if (globalQueuedChunkIds.has(normalizedId)) {
      return false;
    }
    globalQueuedChunkIds.add(normalizedId);
    return true;
  }, []);

  const releaseQueueId = useCallback((queueId) => {
    if (!queueId) {
      return;
    }
    globalQueuedChunkIds.delete(String(queueId));
  }, []);

  // Play audio chunks sequentially from user queue
  const playQueueChunks = useCallback(async (chunks) => {
    if (!chunks || chunks.length === 0) {
      console.log('🎵 [USER_QUEUE] No chunks to play');
      return;
    }

    // Stop any synchronized audio stream to prevent overlapping playback
    if (audioStream?.isStreaming && audioStream?.stopStream) {
      console.log('🎵 [USER_QUEUE] Stopping active audio stream before queue playback');
      audioStream.stopStream();
    }

    // Get auth token once for all chunks
    let authToken = null;
    try {
      authToken = await apiService.getAccessToken();
    } catch (error) {
      console.error('🎵 [USER_QUEUE] Failed to get auth token:', error);
    }

    console.log(`🎵 [USER_QUEUE] Starting sequential playback of ${chunks.length} chunks`);

    // Reuse or create global audio element with iOS Safari compatibility
    if (!globalAudioElement) {
      globalAudioElement = createIOSCompatibleAudio();
    }
    const audio = globalAudioElement;

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const queueId = chunk.queue_id ? String(chunk.queue_id) : null;
      console.log(`🎵 [USER_QUEUE] Playing chunk ${i + 1}/${chunks.length}:`, chunk.url);

      try {
        // Prepend backend URL if chunk.url is relative
        let audioUrl = chunk.url.startsWith('http') ? chunk.url : `${API_CONFIG.BACKEND_URL}${chunk.url}`;

        // Append auth token as query parameter for authenticated access
        if (authToken) {
          audioUrl += `?token=${encodeURIComponent(authToken)}`;
        }

        audio.src = audioUrl;
        audio.volume = audioStream.volumeLevel ?? 1;
        audio.muted = audioStream.isMuted ?? false;

        // Wait for chunk to finish playing
        await new Promise((resolve, reject) => {
          const onEnded = () => {
            console.log(`🎵 [USER_QUEUE] Chunk ${i + 1}/${chunks.length} finished playing`);
            cleanup();
            resolve();
          };
          const onError = (event) => {
            // Get the actual MediaError from the audio element
            const mediaError = audio.error;
            const errorCode = mediaError?.code;
            const errorMessage = mediaError?.message || 'Unknown error';
            console.error(`🎵 [USER_QUEUE] Error playing chunk ${i + 1}/${chunks.length}: code=${errorCode} message=${errorMessage}`);
            cleanup();
            // Create an error object with the MediaError code for proper handling
            const err = new Error(errorMessage);
            err.name = errorCode === 4 ? 'NotSupportedError' : 'MediaError';
            err.code = errorCode;
            reject(err);
          };
          const cleanup = () => {
            audio.removeEventListener('ended', onEnded);
            audio.removeEventListener('error', onError);
          };

          audio.addEventListener('ended', onEnded);
          audio.addEventListener('error', onError);

          audio.play().catch(err => {
            cleanup();
            if (err.name === 'NotAllowedError') {
              console.warn(`🎵 [USER_QUEUE] Autoplay blocked for chunk ${i + 1}/${chunks.length}. User interaction required.`);
              setAudioBlocked(true);
            } else {
              console.error(`🎵 [USER_QUEUE] Failed to start playback for chunk ${i + 1}/${chunks.length}:`, err);
            }
            reject(err);
          });
        });

        // Mark chunk as played via HTTP (always reliable)
        // TODO: Re-enable WebSocket once we figure out why events aren't reaching backend
        try {
          await apiService.makeRequest(`/api/audio/user/played/${chunk.queue_id}`, {}, 'POST');
          console.log(`🎵 [USER_QUEUE] Marked chunk ${i + 1}/${chunks.length} as played`);
          releaseQueueId(queueId);
        } catch (markError) {
          console.error(`🎵 [USER_QUEUE] Failed to mark chunk ${i + 1}/${chunks.length} as played:`, markError);
          // DON'T release queueId on failure - keep it in local set to prevent re-queueing
          // The chunk will be retried on next fetch if not confirmed
          console.warn(`🎵 [USER_QUEUE] Keeping chunk ${queueId} in local set to prevent duplicate playback`);
        }
      } catch (playbackError) {
        console.error(`🎵 [USER_QUEUE] Playback error for chunk ${i + 1}/${chunks.length}, continuing to next:`, playbackError);

        // If autoplay is blocked, stop trying - user needs to interact first
        if (playbackError.name === 'NotAllowedError') {
          console.warn('🎵 [USER_QUEUE] Stopping playback - autoplay blocked. Click anywhere to enable audio.');
          releaseQueueId(queueId);
          break;
        }

        // For NotSupportedError (file not found/stale chunk), mark as played to remove from queue
        if (playbackError.name === 'NotSupportedError') {
          console.warn(`🎵 [USER_QUEUE] Chunk ${i + 1}/${chunks.length} file not found (stale), marking as played to clear from queue`);
          try {
            await apiService.makeRequest(`/api/audio/user/played/${chunk.queue_id}`, {}, 'POST');
            console.log(`🎵 [USER_QUEUE] Marked stale chunk ${chunk.queue_id} as played`);
          } catch (markError) {
            console.error(`🎵 [USER_QUEUE] Failed to mark stale chunk as played:`, markError);
          }
          releaseQueueId(queueId);
          // Continue to next chunk
          continue;
        }

        // For other errors, release the queueId and continue
        releaseQueueId(queueId);
      }
    }

    console.log('🎵 [USER_QUEUE] Completed sequential playback of all chunks');
  }, [audioStream, apiService, releaseQueueId]);

  // Process queued playback requests sequentially
  const processQueue = useCallback(async () => {
    // Prevent concurrent processing using global lock
    if (globalIsProcessing) {
      console.log('🎵 [USER_QUEUE] Queue processor already running, skipping');
      return;
    }

    globalIsProcessing = true;
    setIsPlaying(true);
    console.log('🎵 [USER_QUEUE] Starting queue processor');

    try {
      while (globalPlaybackQueue.length > 0) {
        const chunks = globalPlaybackQueue.shift();
        console.log(`🎵 [USER_QUEUE] Processing queued playback (${globalPlaybackQueue.length} remaining in queue)`);
        await playQueueChunks(chunks);
      }
      console.log('🎵 [USER_QUEUE] Queue processor finished - queue empty');
    } catch (error) {
      console.error('🎵 [USER_QUEUE] Queue processor error:', error);
    } finally {
      globalIsProcessing = false;
      setIsPlaying(false);
    }
  }, [playQueueChunks]);

  // Fetch and play user audio queue (user-scoped playback)
  const fetchUserAudioQueue = useCallback(async (campaignId) => {
    if (!user || !campaignId) {
      console.warn('🎵 [USER_QUEUE] Cannot fetch audio queue: missing user or campaignId');
      return;
    }

    // Prevent concurrent fetches to avoid race condition with duplicate chunks
    if (isFetchingRef.current) {
      console.log('🎵 [USER_QUEUE] Fetch already in progress, skipping duplicate request');
      return;
    }

    // DEBUG: Check what user object contains
    console.log('🔍 [USER_QUEUE] DEBUG user.user_id:', user.user_id, 'user.auth0_sub:', user.auth0_sub);

    // Use Auth0 sub to match WebSocket user_id (backend stores auth0 sub in socket session)
    const userId = user.auth0_sub || user.user_id || user.email;
    if (!userId) {
      console.warn('🎵 [USER_QUEUE] Cannot fetch audio queue: no user ID available');
      return;
    }

    isFetchingRef.current = true;
    try {
      console.log(`🎵 [USER_QUEUE] Fetching audio queue for user ${userId} in campaign ${campaignId}`);
      const response = await apiService.makeRequest(`/api/audio/queue/${encodeURIComponent(userId)}/${encodeURIComponent(campaignId)}`, null, 'GET');

      if (response.success && response.chunks && response.chunks.length > 0) {
        console.log(`🎵 [USER_QUEUE] Received ${response.chunks.length} pending chunks`);

        // Track request_id for logging but DON'T interrupt - just queue behind
        const incomingRequestId = response.chunks[0]?.request_id;
        if (incomingRequestId) {
          console.log(`🎵 [USER_QUEUE] Request ID: ${incomingRequestId} (current: ${globalCurrentRequestId || 'none'})`);
          globalCurrentRequestId = incomingRequestId;
        }

        const newChunks = response.chunks.filter((chunk) => {
          const queueId = chunk.queue_id ? String(chunk.queue_id) : null;
          if (!registerQueueId(queueId)) {
            console.log(`🎵 [USER_QUEUE] Skipping duplicate chunk ${queueId}`);
            return false;
          }
          return true;
        });

        if (newChunks.length === 0) {
          console.log('🎵 [USER_QUEUE] No new chunks after de-duplication');
          return;
        }

        // Add to global queue instead of immediate playback
        globalPlaybackQueue.push(newChunks);
        console.log(`🎵 [USER_QUEUE] Queue depth: ${globalPlaybackQueue.length}`);
        // Trigger queue processing (will skip if already processing)
        processQueue();
      } else {
        console.log('🎵 [USER_QUEUE] No pending audio chunks in queue');
      }
    } catch (error) {
      console.error('🎵 [USER_QUEUE] Failed to fetch audio queue:', error);
    } finally {
      isFetchingRef.current = false;
    }
  }, [user, processQueue, apiService, registerQueueId]);

  return {
    fetchUserAudioQueue,
    playQueueChunks,
    stopQueuePlayback,
    audioBlocked,
    isPlaying,
    unlockAudio,
  };
}
