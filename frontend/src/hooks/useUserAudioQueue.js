import { useCallback, useRef } from 'react';
import { API_CONFIG } from '../config/api.js';

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
  // Tracks queue_ids that are already enqueued/playing to prevent duplicates
  const queuedChunkIdsRef = useRef(new Set());

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

    // Get auth token once for all chunks
    let authToken = null;
    try {
      authToken = await apiService.getAccessToken();
    } catch (error) {
      console.error('🎵 [USER_QUEUE] Failed to get auth token:', error);
    }

    console.log(`🎵 [USER_QUEUE] Starting sequential playback of ${chunks.length} chunks`);

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const queueId = chunk.queue_id ? String(chunk.queue_id) : null;
      console.log(`🎵 [USER_QUEUE] Playing chunk ${i + 1}/${chunks.length}:`, chunk.url);

      try {
        // Create audio element for this chunk
        // Prepend backend URL if chunk.url is relative
        let audioUrl = chunk.url.startsWith('http') ? chunk.url : `${API_CONFIG.BACKEND_URL}${chunk.url}`;

        // Append auth token as query parameter for authenticated access
        if (authToken) {
          audioUrl += `?token=${encodeURIComponent(authToken)}`;
        }

        const audio = new Audio(audioUrl);
        audio.volume = audioStream.volumeLevel;
        audio.muted = audioStream.isMuted;

        // Wait for chunk to finish playing
        await new Promise((resolve, reject) => {
          audio.onended = () => {
            console.log(`🎵 [USER_QUEUE] Chunk ${i + 1}/${chunks.length} finished playing`);
            resolve();
          };
          audio.onerror = (error) => {
            console.error(`🎵 [USER_QUEUE] Error playing chunk ${i + 1}/${chunks.length}:`, error);
            reject(error);
          };
          audio.play().catch(err => {
            console.error(`🎵 [USER_QUEUE] Failed to start playback for chunk ${i + 1}/${chunks.length}:`, err);
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
        // Continue to next chunk even if this one fails
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
    }
  }, [playQueueChunks]);

  // Fetch and play user audio queue (user-scoped playback)
  const fetchUserAudioQueue = useCallback(async (campaignId) => {
    if (!user || !campaignId) {
      console.warn('🎵 [USER_QUEUE] Cannot fetch audio queue: missing user or campaignId');
      return;
    }

    // DEBUG: Check what user object contains
    console.log('🔍 [USER_QUEUE] DEBUG user.user_id:', user.user_id, 'user.email:', user.email);

    // Use GAIA user_id (from /api/auth0/verify) to match WebSocket user_id
    const userId = user.user_id || user.email;
    if (!userId) {
      console.warn('🎵 [USER_QUEUE] Cannot fetch audio queue: no user ID available');
      return;
    }

    try {
      console.log(`🎵 [USER_QUEUE] Fetching audio queue for user ${userId} in campaign ${campaignId}`);
      const response = await apiService.makeRequest(`/api/audio/queue/${encodeURIComponent(userId)}/${encodeURIComponent(campaignId)}`, null, 'GET');

      if (response.success && response.chunks && response.chunks.length > 0) {
        console.log(`🎵 [USER_QUEUE] Received ${response.chunks.length} pending chunks - adding to queue`);
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
    }
  }, [user, processQueue, apiService, registerQueueId]);

  return {
    fetchUserAudioQueue,
    playQueueChunks,
  };
}
