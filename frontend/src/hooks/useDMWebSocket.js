import { useEffect, useRef, useCallback, useState } from 'react';
import { API_CONFIG } from '../config/api.js';

const CAMPAIGN_START_TRACE = '[CAMPAIGN_START_FLOW]';

/**
 * Custom hook to manage DM WebSocket connection
 * Handles connection lifecycle, reconnection, authentication, and message routing
 *
 * @param {Object} params - Configuration object
 * @param {string} params.campaignId - Current campaign ID
 * @param {Function} params.getAccessTokenSilently - Auth0 token getter
 * @param {Function} params.refreshAccessToken - Auth0 token refresh
 * @param {Object} params.handlers - Message type handlers
 * @returns {Object} WebSocket management interface
 */
export function useDMWebSocket({
  campaignId,
  getAccessTokenSilently,
  refreshAccessToken,
  handlers = {},
}) {
  const dmWebSocketRef = useRef(null);
  const dmReconnectTimerRef = useRef(null);
  const dmIsConnectingRef = useRef(false);
  const connectionTokenRef = useRef(null);
  const getAccessTokenSilentlyRef = useRef(getAccessTokenSilently);
  const refreshAccessTokenRef = useRef(refreshAccessToken);
  const [socketVersion, setSocketVersion] = useState(0);

  useEffect(() => {
    getAccessTokenSilentlyRef.current = getAccessTokenSilently;
  }, [getAccessTokenSilently]);

  useEffect(() => {
    refreshAccessTokenRef.current = refreshAccessToken;
  }, [refreshAccessToken]);

  // Restore connection token from localStorage on campaign change
  useEffect(() => {
    if (campaignId) {
      const storedToken = localStorage.getItem(`gaia_conn_token_${campaignId}`);
      if (storedToken) {
        connectionTokenRef.current = storedToken;
        console.log('[CONNECTION_REGISTRY] 🔄 Restored connection token from localStorage | campaign=%s token=%s...',
          campaignId, storedToken.slice(0, 12));
      }
    }
  }, [campaignId]);

  const {
    onAudioAvailable,
    onAudioChunk,
    onNarrativeChunk,
    onResponseChunk,
    onMetadataUpdate,
    onInitializationError,
    onCampaignUpdate,
    onAudioStreamStarted,
    onAudioStreamStopped,
    onAudioQueueCleared,
    onPlaybackQueueUpdated,
    onSfxAvailable,
  } = handlers;

  const handlersRef = useRef({
    onAudioAvailable,
    onAudioChunk,
    onNarrativeChunk,
    onResponseChunk,
    onMetadataUpdate,
    onInitializationError,
    onCampaignUpdate,
    onAudioStreamStarted,
    onAudioStreamStopped,
    onAudioQueueCleared,
    onPlaybackQueueUpdated,
    onSfxAvailable,
  });

  useEffect(() => {
    handlersRef.current = {
      onAudioAvailable,
      onAudioChunk,
      onNarrativeChunk,
      onResponseChunk,
      onMetadataUpdate,
      onInitializationError,
      onCampaignUpdate,
      onAudioStreamStarted,
      onAudioStreamStopped,
      onAudioQueueCleared,
      onPlaybackQueueUpdated,
      onSfxAvailable,
    };
  }, [
    onAudioAvailable,
    onAudioChunk,
    onNarrativeChunk,
    onResponseChunk,
    onMetadataUpdate,
    onInitializationError,
    onCampaignUpdate,
    onAudioStreamStarted,
    onAudioStreamStopped,
    onAudioQueueCleared,
    onPlaybackQueueUpdated,
    onSfxAvailable,
  ]);

  // Connect to DM WebSocket
  const connectWebSocket = useCallback(() => {
    let disposed = false;
    let retryDelay = 1000;

    const clearReconnectTimer = () => {
      if (dmReconnectTimerRef.current) {
        clearTimeout(dmReconnectTimerRef.current);
        dmReconnectTimerRef.current = null;
      }
    };

    const cleanup = () => {
      disposed = true;
      clearReconnectTimer();
      const socket = dmWebSocketRef.current;
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      }
      dmWebSocketRef.current = null;
      dmIsConnectingRef.current = false;
    };

    if (!campaignId) {
      console.warn(`${CAMPAIGN_START_TRACE} DM WebSocket connect skipped - missing campaignId`);
      cleanup();
      return cleanup;
    }

    const connect = async () => {
      if (disposed) return;

      // Prevent duplicate connection attempts
      if (dmIsConnectingRef.current) {
        console.log('🎭 DM connection already in progress, skipping duplicate attempt');
        return;
      }

      const existingSocket = dmWebSocketRef.current;
      if (existingSocket && (existingSocket.readyState === WebSocket.OPEN || existingSocket.readyState === WebSocket.CONNECTING)) {
        return;
      }

      // Mark connection in progress
      dmIsConnectingRef.current = true;

      const sessionIdForSocket = campaignId;
      let token = null;
      try {
        const tokenGetter = getAccessTokenSilentlyRef.current;
        token = await tokenGetter?.();
        if (!token && typeof tokenGetter === 'function') {
          const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
          if (audience) {
            try {
              token = await tokenGetter({
                authorizationParams: {
                  audience,
                  scope: 'openid profile email offline_access'
                }
              });
            } catch {
              // ignore; will fall through
            }
          }
        }
      } catch {
        token = null;
      }

      const isProduction = window.location.hostname !== 'localhost' &&
                           window.location.hostname !== '127.0.0.1' &&
                           !window.location.hostname.startsWith('192.168.');
      const requireAuth = isProduction || import.meta.env.VITE_REQUIRE_AUTH === 'true';

      if (requireAuth && !token) {
        const nextDelay = Math.min(retryDelay, 10000);
        console.log(`🎭 Auth token unavailable; retrying DM WS connect in ${nextDelay}ms`);
        dmIsConnectingRef.current = false;
        clearReconnectTimer();
        dmReconnectTimerRef.current = setTimeout(() => {
          if (disposed) return;
          connect();
        }, nextDelay);
        return;
      }

      const configuredWsBase = (API_CONFIG?.WS_BASE_URL || '').trim();
      const wsBase = configuredWsBase
        ? configuredWsBase.replace(/\/$/, '')
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host}`;

      const query = new URLSearchParams({
        session_id: sessionIdForSocket,
      });
      const wsUrl = `${wsBase}/ws/campaign/dm?${query.toString()}`;

      console.log('🎭 Connecting DM WebSocket:', `${wsBase}/ws/campaign/dm?session_id=${encodeURIComponent(sessionIdForSocket)}`);
      const ws = new WebSocket(wsUrl);
      dmWebSocketRef.current = ws;
      setSocketVersion((version) => version + 1);

      ws.onopen = () => {
        if (disposed) return;
        console.log('🎭 DM WebSocket connected for session:', sessionIdForSocket);

        // Clear connecting flag on success
        dmIsConnectingRef.current = false;

        if (token) {
          ws.send(JSON.stringify({ type: 'auth', token }));
        }

        retryDelay = 1000;
      };

      ws.onmessage = (event) => {
        if (disposed) return;
        const receiveTime = new Date().toISOString();
        console.log(`📨 [WEBSOCKET] onmessage fired at ${receiveTime}`);
        try {
          const data = JSON.parse(event.data);
          console.log('🎭 DM WebSocket received:', data);
          const {
            onAudioAvailable: handleAudioAvailable,
            onAudioChunk: handleAudioChunk,
            onNarrativeChunk: handleNarrativeChunk,
            onResponseChunk: handleResponseChunk,
            onMetadataUpdate: handleMetadataUpdate,
            onInitializationError: handleInitializationError,
            onCampaignUpdate: handleCampaignUpdate,
            onAudioStreamStarted: handleAudioStreamStarted,
            onAudioStreamStopped: handleAudioStreamStopped,
            onAudioQueueCleared: handleAudioQueueCleared,
            onPlaybackQueueUpdated: handlePlaybackQueueUpdated,
          } = handlersRef.current;

          // Route message to appropriate handler
          if (data.type === 'room.campaign_started') {
            console.log(
              `${CAMPAIGN_START_TRACE} WS received room.campaign_started`,
              {
                sessionId: data.campaign_id || sessionIdForSocket,
                payloadKeys: Object.keys(data || {}),
              }
            );
          }
          if (data.type === 'audio_available' && handleAudioAvailable) {
            handleAudioAvailable(data, sessionIdForSocket);
          } else if (data.type === 'audio_chunk_ready' && data.chunk && handleAudioChunk) {
            console.log('[AUDIO_DEBUG] 📡 Received audio_chunk_ready | chunk_id=%s seq=%s group=%s text=%s',
              data.chunk.id, data.sequence_number, data.playback_group, data.chunk.text_preview || 'N/A');
            handleAudioChunk(data.chunk, sessionIdForSocket, data);
          } else if (data.type === 'audio_stream_started' && handleAudioStreamStarted) {
            const textPreview = data.text ? `"${data.text}"` : 'N/A';
            console.log('[AUDIO_DEBUG] 🎬 Playing back %s chunk 1/%d',
              textPreview, (data.chunk_ids || []).length);
            handleAudioStreamStarted(data, sessionIdForSocket);
          } else if (data.type === 'audio_stream_stopped' && handleAudioStreamStopped) {
            console.log('[AUDIO_DEBUG] ⏹️ Received audio_stream_stopped | session=%s', sessionIdForSocket);
            handleAudioStreamStopped(data, sessionIdForSocket);
          } else if (data.type === 'narrative_chunk' && handleNarrativeChunk) {
            console.log(
              `${CAMPAIGN_START_TRACE} WS received narrative_chunk`,
              {
                sessionId: sessionIdForSocket,
                contentLength: data.content ? data.content.length : 0,
                isFinal: data.is_final,
              }
            );
            handleNarrativeChunk(data, sessionIdForSocket);
          } else if (data.type === 'player_response_chunk' && handleResponseChunk) {
            console.log(
              `${CAMPAIGN_START_TRACE} WS received player_response_chunk`,
              {
                sessionId: sessionIdForSocket,
                contentLength: data.content ? data.content.length : 0,
                isFinal: data.is_final,
              }
            );
            handleResponseChunk(data, sessionIdForSocket);
          } else if (data.type === 'metadata_update' && data.metadata && handleMetadataUpdate) {
            console.log(
              `${CAMPAIGN_START_TRACE} WS received metadata_update`,
              {
                sessionId: sessionIdForSocket,
                metadataKeys: Object.keys(data.metadata || {}),
              }
            );
            handleMetadataUpdate(data.metadata, sessionIdForSocket, data.campaign_id);
          } else if (data.type === 'initialization_error' && handleInitializationError) {
            console.log(
              `${CAMPAIGN_START_TRACE} WS received initialization_error`,
              {
                sessionId: sessionIdForSocket,
                error: data.error,
              }
            );
            handleInitializationError(data, sessionIdForSocket, campaignId);
          } else if (
            (data.type === 'campaign_updated' ||
             data.type === 'campaign_loaded' ||
             data.type === 'campaign_active') &&
            handleCampaignUpdate
          ) {
            console.log(
              `${CAMPAIGN_START_TRACE} WS received campaign update`,
              {
                eventType: data.type,
                sessionId: data.campaign_id || data.session_id || sessionIdForSocket,
                hasStructuredData: Boolean(data.structured_data),
              }
            );
            handleCampaignUpdate(data, sessionIdForSocket);
          } else if (data.type === 'audio_queue_cleared' && handleAudioQueueCleared) {
            handleAudioQueueCleared(data, sessionIdForSocket);
          } else if (data.type === 'playback_queue_updated' && handlePlaybackQueueUpdated) {
            console.log('[AUDIO_DEBUG] 📢 Received playback_queue_updated | session=%s pending=%d current=%s',
              sessionIdForSocket, data.pending_count, data.current_request?.request_id || 'None');
            handlePlaybackQueueUpdated(data, sessionIdForSocket);
          } else if (data.type === 'sfx_available') {
            const { onSfxAvailable: handleSfxAvailable } = handlersRef.current;
            if (handleSfxAvailable) {
              console.log('[SFX] 🔊 Received sfx_available | session=%s', sessionIdForSocket);
              handleSfxAvailable(data, sessionIdForSocket);
            }
          } else if (data.type === 'connection_registered') {
            // Store connection token for resume support and audio tracking
            if (data.connection_token) {
              connectionTokenRef.current = data.connection_token;
              // Persist to localStorage for resume support across page refreshes
              localStorage.setItem(`gaia_conn_token_${sessionIdForSocket}`, data.connection_token);
              console.log('[CONNECTION_REGISTRY] 🔑 Received and stored connection token | id=%s token=%s... campaign=%s',
                data.connection_id, data.connection_token.slice(0, 12), sessionIdForSocket);
            }
          } else {
            // Log unhandled event types for debugging
            console.log(
              `${CAMPAIGN_START_TRACE} WS received unhandled event`,
              {
                eventType: data.type,
                sessionId: sessionIdForSocket,
                dataKeys: Object.keys(data || {}),
              }
            );
          }
        } catch (error) {
          console.error('🎭 DM WebSocket message parse error:', error);
        }
      };

      ws.onerror = (error) => {
        if (disposed) return;
        console.error('🎭 DM WebSocket error:', error);
        dmIsConnectingRef.current = false;
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close();
        }
      };

      ws.onclose = async (event) => {
        if (disposed) return;
        const closeCode = event?.code ?? 1000;
        const closeReason = event?.reason ?? '';
        console.log('🎭 DM WebSocket disconnected', { code: closeCode, reason: closeReason });

        if (dmWebSocketRef.current === ws) {
          dmWebSocketRef.current = null;
          setSocketVersion((version) => version + 1);
        } else {
          console.log('🎭 Stale DM socket closed, ignoring');
          return;
        }

        clearReconnectTimer();

        // Handle auth/access errors - DO NOT RECONNECT
        if ([4401, 4403, 4404].includes(closeCode)) {
          if (closeCode === 4401) {
            // Only retry auth errors with token refresh
            try {
              const refreshed = await refreshAccessTokenRef.current?.();
              if (refreshed) {
                console.log('🎭 Refreshed token after 4401; reconnecting');
                connect();
              } else {
                console.log('🎭 Refresh token unavailable; prompted reauthentication');
              }
            } catch (e) {
              console.warn('🎭 Token refresh failed after 4401; not reconnecting');
            }
          } else if (closeCode === 4403) {
            console.log('🎭 Access forbidden (4403); not reconnecting');
          } else if (closeCode === 4404) {
            console.log('🎭 Campaign not found (4404); not reconnecting');
          }
          return;
        }

        // Check if superseded by another DM connection
        const supersededByNewDm =
          closeCode === 1012 && closeReason === "Superseded DM connection";

        if (supersededByNewDm) {
          console.log("🎭 DM WebSocket superseded by another connection; skipping auto-reconnect.");
          return;
        }

        // Auto-reconnect with exponential backoff
        const shouldRetry =
          campaignId &&
          dmWebSocketRef.current === null &&
          !disposed;

        if (shouldRetry) {
          const nextDelay = Math.min(retryDelay, 30000);
          retryDelay = Math.min(retryDelay * 2, 30000);

          console.log(`🎭 Will retry DM connection in ${nextDelay}ms`);
          dmReconnectTimerRef.current = setTimeout(() => {
            if (disposed) return;
            if (!dmWebSocketRef.current && campaignId) {
              console.log('🎭 Retrying DM connection after disconnect');
              connect();
            }
          }, nextDelay);
        }
      };
    };

    connect().catch((error) => {
      console.error('🎭 DM WebSocket connect error:', error);
    });

    return cleanup;
  }, [campaignId]);

  // Set up WebSocket connection
  useEffect(() => {
    const cleanup = connectWebSocket();
    return () => {
      if (typeof cleanup === 'function') {
        cleanup();
      }
    };
  }, [connectWebSocket]);

  // Manual disconnect function
  const disconnect = useCallback(() => {
    if (dmWebSocketRef.current) {
      try {
        dmWebSocketRef.current.close();
      } catch (error) {
        console.warn('🎭 Error closing WebSocket:', error);
      } finally {
        dmWebSocketRef.current = null;
        setSocketVersion((version) => version + 1);
      }
    }
    if (dmReconnectTimerRef.current) {
      clearTimeout(dmReconnectTimerRef.current);
      dmReconnectTimerRef.current = null;
    }
  }, []);

  return {
    webSocketRef: dmWebSocketRef,
    disconnect,
    connectionTokenRef,
    socketVersion,
  };
}
