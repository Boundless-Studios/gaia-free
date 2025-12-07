/**
 * Socket.IO-based game connection hook.
 *
 * Replaces raw WebSocket connections with Socket.IO for:
 * - Automatic reconnection with exponential backoff
 * - Room-based message routing (campaigns)
 * - Built-in heartbeats and connection health
 * - Cleaner event-based API
 *
 * Usage:
 *   const { socket, isConnected, emit } = useGameSocket({
 *     campaignId: 'campaign-123',
 *     getAccessToken,
 *     handlers: {
 *       narrative_chunk: (data) => console.log('Narrative:', data),
 *       campaign_updated: (data) => console.log('Update:', data),
 *     },
 *   });
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import { API_CONFIG } from '../config/api.js';

/**
 * Custom hook to manage Socket.IO connection to game server.
 *
 * @param {Object} params - Configuration object
 * @param {string} params.campaignId - Current campaign/session ID
 * @param {Function} params.getAccessToken - Async function to get auth token
 * @param {string} params.role - Connection role ('player' or 'dm')
 * @param {Object} params.handlers - Event handlers { eventName: handler }
 * @returns {Object} Socket management interface
 */
export function useGameSocket({
  campaignId,
  getAccessToken,
  role = 'player',
  handlers = {},
}) {
  const socketRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [connectionId, setConnectionId] = useState(null);
  const [connectionToken, setConnectionToken] = useState(null);
  const handlersRef = useRef(handlers);

  // Keep handlers ref updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  // Restore connection token from localStorage
  useEffect(() => {
    if (campaignId) {
      const storedToken = localStorage.getItem(`gaia_conn_token_${campaignId}`);
      if (storedToken) {
        setConnectionToken(storedToken);
        console.log(
          '[SOCKET.IO] Restored connection token from localStorage | campaign=%s',
          campaignId
        );
      }
    }
  }, [campaignId]);

  // Main connection effect
  useEffect(() => {
    if (!campaignId) {
      console.log('[SOCKET.IO] No campaignId, skipping connection');
      return;
    }

    let mounted = true;

    const connect = async () => {
      // Get the base URL for Socket.IO
      const configuredBase = (API_CONFIG?.WS_BASE_URL || '').trim();
      let baseUrl;

      if (configuredBase) {
        // Convert wss:// to https:// for Socket.IO
        baseUrl = configuredBase
          .replace(/^wss:/, 'https:')
          .replace(/^ws:/, 'http:')
          .replace(/\/$/, '');
      } else {
        // Use current host
        const protocol = window.location.protocol;
        const host =
          window.location.hostname === 'localhost'
            ? 'localhost:8000'
            : window.location.host;
        baseUrl = `${protocol}//${host}`;
      }

      console.log('[SOCKET.IO] Connecting to %s/campaign | session=%s role=%s',
        baseUrl, campaignId, role);

      // Create Socket.IO connection with async auth
      const socket = io(`${baseUrl}/campaign`, {
        // Auth callback - called before connection
        auth: async (cb) => {
          let token = null;
          try {
            token = await getAccessToken?.();
          } catch (err) {
            console.warn('[SOCKET.IO] Failed to get access token:', err);
          }
          cb({
            token,
            session_id: campaignId,
            role,
          });
        },
        // Reconnection settings (Socket.IO handles this automatically)
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 30000,
        reconnectionAttempts: Infinity,
        // Transport settings
        transports: ['websocket', 'polling'],
        // Timeout settings
        timeout: 20000,
      });

      socketRef.current = socket;

      // Connection events
      socket.on('connect', () => {
        if (!mounted) return;
        console.log('[SOCKET.IO] Connected | socket.id=%s', socket.id);
        setIsConnected(true);
        setConnectionError(null);
      });

      socket.on('disconnect', (reason) => {
        if (!mounted) return;
        console.log('[SOCKET.IO] Disconnected | reason=%s', reason);
        setIsConnected(false);
      });

      socket.on('connect_error', (error) => {
        if (!mounted) return;
        console.error('[SOCKET.IO] Connection error:', error.message);
        setConnectionError(error.message);
        setIsConnected(false);
      });

      // Connection registration (receives connection token)
      socket.on('connection_registered', (data) => {
        if (!mounted) return;
        console.log('[SOCKET.IO] Connection registered | id=%s', data.connection_id);
        setConnectionId(data.connection_id);
        if (data.connection_token) {
          setConnectionToken(data.connection_token);
          localStorage.setItem(`gaia_conn_token_${campaignId}`, data.connection_token);
        }
      });

      // Player events
      socket.on('player_connected', (data) => {
        if (!mounted) return;
        console.log('[SOCKET.IO] Player connected | user=%s count=%d',
          data.user_id, data.connected_count);
        handlersRef.current.onPlayerConnected?.(data);
      });

      socket.on('player_disconnected', (data) => {
        if (!mounted) return;
        console.log('[SOCKET.IO] Player disconnected | user=%s count=%d',
          data.user_id, data.connected_count);
        handlersRef.current.onPlayerDisconnected?.(data);
      });

      // Game events - route to handlers
      const gameEvents = [
        'narrative_chunk',
        'player_response_chunk',
        'player_options',
        'personalized_player_options',
        'pending_observations',
        'metadata_update',
        'campaign_updated',
        'campaign_loaded',
        'campaign_active',
        'campaign_deactivated',
        'initialization_error',
        'room.seat_updated',
        'room.seat_character_updated',
        'room.campaign_started',
        'room.player_vacated',
        'room.dm_joined',
        'room.dm_left',
        // Player action submission (notifies DM when player submits)
        'player_action_submitted',
      ];

      gameEvents.forEach((event) => {
        socket.on(event, (data) => {
          if (!mounted) return;
          console.log(`[SOCKET.IO] Received game event: ${event}`, data);
          // Try exact match first, then camelCase conversion
          const handler = handlersRef.current[event] ||
            handlersRef.current[toCamelCase(event)];
          if (handler) {
            handler(data, campaignId);
          } else {
            console.warn(`[SOCKET.IO] No handler for event: ${event}`);
          }
        });
      });

      // Audio events
      const audioEvents = [
        'audio_available',
        'audio_chunk_ready',
        'audio_stream_started',
        'audio_stream_stopped',
        'audio_queue_cleared',
        'playback_queue_updated',
        'sfx_available',
        'audio_played_confirmed',  // Acknowledgment confirmation for reliable playback
      ];

      audioEvents.forEach((event) => {
        socket.on(event, (data) => {
          if (!mounted) return;
          const handler = handlersRef.current[event] ||
            handlersRef.current[toCamelCase(event)];
          if (handler) {
            handler(data, campaignId);
          }
        });
      });

      // Collaborative editing events
      socket.on('yjs_update', (data) => {
        if (!mounted) return;
        handlersRef.current.onYjsUpdate?.(data);
        handlersRef.current.yjs_update?.(data);
      });

      socket.on('awareness_update', (data) => {
        if (!mounted) return;
        handlersRef.current.onAwarenessUpdate?.(data);
        handlersRef.current.awareness_update?.(data);
      });

      socket.on('player_list', (data) => {
        if (!mounted) return;
        handlersRef.current.onPlayerList?.(data);
        handlersRef.current.player_list?.(data);
      });

      socket.on('partial_overlay', (data) => {
        if (!mounted) return;
        handlersRef.current.onPartialOverlay?.(data);
        handlersRef.current.partial_overlay?.(data);
      });

      socket.on('registered', (data) => {
        if (!mounted) return;
        handlersRef.current.onRegistered?.(data);
        handlersRef.current.registered?.(data);
      });

      // Heartbeat/ping events
      socket.on('heartbeat', () => {
        // Socket.IO handles ping/pong automatically, this is for app-level heartbeat
        handlersRef.current.onHeartbeat?.();
      });
    };

    connect().catch((error) => {
      console.error('[SOCKET.IO] Connection setup error:', error);
      setConnectionError(error.message);
    });

    // Cleanup on unmount or campaignId change
    return () => {
      mounted = false;
      if (socketRef.current) {
        console.log('[SOCKET.IO] Disconnecting...');
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [campaignId, getAccessToken, role]);

  // Emit function with connection check
  const emit = useCallback((event, data) => {
    const socket = socketRef.current;
    if (socket?.connected) {
      socket.emit(event, data);
    } else {
      console.warn('[SOCKET.IO] Cannot emit %s - not connected', event);
    }
  }, []);

  // Convenience methods for common operations
  const sendYjsUpdate = useCallback((update, playerId, source = 'keyboard') => {
    emit('yjs_update', {
      sessionId: campaignId,
      playerId,
      update,
      source,
      timestamp: new Date().toISOString(),
    });
  }, [emit, campaignId]);

  const sendAwarenessUpdate = useCallback((update, playerId) => {
    emit('awareness_update', {
      sessionId: campaignId,
      playerId,
      update,
      timestamp: new Date().toISOString(),
    });
  }, [emit, campaignId]);

  const sendAudioPlayed = useCallback((chunkId) => {
    emit('audio_played', { chunk_id: chunkId });
  }, [emit]);

  const register = useCallback((playerId, playerName) => {
    emit('register', { playerId, playerName });
  }, [emit]);

  return {
    socket: socketRef.current,
    isConnected,
    connectionError,
    connectionId,
    connectionToken,
    emit,
    // Convenience methods
    sendYjsUpdate,
    sendAwarenessUpdate,
    sendAudioPlayed,
    register,
  };
}

/**
 * Convert snake_case or dot.notation to camelCase.
 * e.g., 'narrative_chunk' -> 'narrativeChunk'
 *       'room.seat_updated' -> 'roomSeatUpdated'
 */
function toCamelCase(str) {
  return str
    .replace(/[._]([a-z])/g, (_, letter) => letter.toUpperCase())
    .replace(/^([A-Z])/, (_, letter) => letter.toLowerCase());
}

export default useGameSocket;
