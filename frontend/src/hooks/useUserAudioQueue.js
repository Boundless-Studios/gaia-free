import { useCallback, useRef, useState, useEffect } from 'react';
import { API_CONFIG } from '../config/api.js';

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

/**
 * Unlock audio playback by playing a silent audio on user interaction.
 * Call this on any user click/tap to ensure audio can play.
 */
export function unlockAudio() {
  if (audioUnlocked) return Promise.resolve(true);

  if (!sharedAudioElement) {
    sharedAudioElement = new Audio();
    // Use a tiny silent audio data URI
    sharedAudioElement.src = 'data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYoRwmHAAAAAAD/+1DEAAAGAAGn9AAAIiwijW80AAQAAAT/JJ5mn//t/5J//l/kn5J+Sf/5J/t//5f5J+Sf//+X+Sf5J5J+X/8k/ygAAANtVVVV//tQxA4AAADSAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
  }

  return sharedAudioElement.play()
    .then(() => {
      audioUnlocked = true;
      console.log('🎵 [AUDIO] Browser audio unlocked');
      return true;
    })
    .catch((err) => {
      console.warn('🎵 [AUDIO] Failed to unlock audio:', err.message);
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
 * - In-memory FIFO queue to prevent overlapping playback
 * - Sequential playback guaranteed per user
 * - Rapid triggers are queued, not dropped
 * - Handles browser autoplay restrictions
 *
 * @param {Object} params - Configuration object
 * @param {Object} params.user - Auth0 user object (must have email or sub)
 * @param {Object} params.audioStream - Audio stream context
 * @param {Object} params.apiService - API service instance
 * @returns {Object} Audio queue management interface
 */
export function useUserAudioQueue({ user, audioStream, apiService }) {
  // In-memory playback queue (FIFO)
  const playbackQueueRef = useRef([]);
  // Processing lock to prevent concurrent playback
  const isProcessingRef = useRef(false);
  // Fetch lock to prevent concurrent API requests
  const isFetchingRef = useRef(false);
  // Tracks queue_ids that are already enqueued/playing to prevent duplicates
  const queuedChunkIdsRef = useRef(new Set());
  // Track the current request_id being played (to detect new requests)
  const currentRequestIdRef = useRef(null);
  // Track if audio is blocked
  const [audioBlocked, setAudioBlocked] = useState(false);
  // Persistent audio element for reuse
  const audioElementRef = useRef(null);
  // Track if queue is currently playing
  const [isPlaying, setIsPlaying] = useState(false);

  // Stop queue playback and clear queue (called when synchronized stream starts or new request)
  const stopQueuePlayback = useCallback(() => {
    console.log('🎵 [USER_QUEUE] Stopping queue playback');
    // Clear the queue
    playbackQueueRef.current = [];
    queuedChunkIdsRef.current.clear();
    currentRequestIdRef.current = null;
    // Stop current audio
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.src = '';
    }
    // Reset processing lock (will cause current loop to exit on next iteration)
    isProcessingRef.current = false;
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
    const knownIds = queuedChunkIdsRef.current;
    if (knownIds.has(normalizedId)) {
      return false;
    }
    knownIds.add(normalizedId);
    return true;
  }, []);

  const releaseQueueId = useCallback((queueId) => {
    if (!queueId) {
      return;
    }
    queuedChunkIdsRef.current.delete(String(queueId));
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

    // Reuse or create audio element
    if (!audioElementRef.current) {
      audioElementRef.current = new Audio();
    }
    const audio = audioElementRef.current;

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
          const onError = (error) => {
            console.error(`🎵 [USER_QUEUE] Error playing chunk ${i + 1}/${chunks.length}:`, error);
            cleanup();
            reject(error);
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

        // Mark chunk as played
        try {
          await apiService.makeRequest(`/api/audio/user/played/${chunk.queue_id}`, {}, 'POST');
          console.log(`🎵 [USER_QUEUE] Marked chunk ${i + 1}/${chunks.length} as played`);
          releaseQueueId(queueId);
        } catch (markError) {
          console.error(`🎵 [USER_QUEUE] Failed to mark chunk ${i + 1}/${chunks.length} as played:`, markError);
          releaseQueueId(queueId);
        }
      } catch (playbackError) {
        console.error(`🎵 [USER_QUEUE] Playback error for chunk ${i + 1}/${chunks.length}, continuing to next:`, playbackError);
        releaseQueueId(queueId);
        // If autoplay is blocked, stop trying - user needs to interact first
        if (playbackError.name === 'NotAllowedError') {
          console.warn('🎵 [USER_QUEUE] Stopping playback - autoplay blocked. Click anywhere to enable audio.');
          break;
        }
        // Continue to next chunk for other errors
      }
    }

    console.log('🎵 [USER_QUEUE] Completed sequential playback of all chunks');
  }, [audioStream, apiService, releaseQueueId]);

  // Process queued playback requests sequentially
  const processQueue = useCallback(async () => {
    // Prevent concurrent processing
    if (isProcessingRef.current) {
      console.log('🎵 [USER_QUEUE] Queue processor already running, skipping');
      return;
    }

    isProcessingRef.current = true;
    setIsPlaying(true);
    console.log('🎵 [USER_QUEUE] Starting queue processor');

    try {
      while (playbackQueueRef.current.length > 0) {
        const chunks = playbackQueueRef.current.shift();
        console.log(`🎵 [USER_QUEUE] Processing queued playback (${playbackQueueRef.current.length} remaining in queue)`);
        await playQueueChunks(chunks);
      }
      console.log('🎵 [USER_QUEUE] Queue processor finished - queue empty');
    } catch (error) {
      console.error('🎵 [USER_QUEUE] Queue processor error:', error);
    } finally {
      isProcessingRef.current = false;
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

        // Check if this is a new request (different request_id)
        // If so, stop current playback and clear the queue
        const incomingRequestId = response.chunks[0]?.request_id;
        if (incomingRequestId && currentRequestIdRef.current && incomingRequestId !== currentRequestIdRef.current) {
          console.log(`🎵 [USER_QUEUE] New request detected (${incomingRequestId}), stopping current playback (${currentRequestIdRef.current})`);
          stopQueuePlayback();
        }

        // Update current request ID
        if (incomingRequestId) {
          currentRequestIdRef.current = incomingRequestId;
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

        // Add to queue instead of immediate playback
        playbackQueueRef.current.push(newChunks);
        console.log(`🎵 [USER_QUEUE] Queue depth: ${playbackQueueRef.current.length}`);
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
  }, [user, processQueue, apiService, registerQueueId, stopQueuePlayback]);

  return {
    fetchUserAudioQueue,
    playQueueChunks,
    stopQueuePlayback,
    audioBlocked,
    isPlaying,
    unlockAudio,
  };
}
