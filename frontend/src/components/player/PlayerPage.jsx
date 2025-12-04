import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import SharedHeaderLayout from '../layout/SharedHeaderLayout.jsx';
import { useAuth } from '../../contexts/Auth0Context.jsx';
import { Link, useParams } from 'react-router-dom';
import LobbyButton from '../layout/LobbyButton.jsx';
import CampaignNameDisplay from '../layout/CampaignNameDisplay.jsx';
import { UserMenu } from '../../AppWithAuth0.jsx';
import PlayerView from './PlayerView.jsx';
import apiService from '../../services/apiService.js';
import { AudioStreamProvider, useAudioStream, AUDIO_STREAM_COMPLETED_EVENT } from '../../context/audioStreamContext.jsx';
import { API_CONFIG } from '../../config/api.js';
import { generateUniqueId } from '../../utils/idGenerator.js';
import { useUserAudioQueue } from '../../hooks/useUserAudioQueue.js';
import { RoomProvider, useRoom } from '../../contexts/RoomContext.jsx';
import SeatSelectionModal from './SeatSelectionModal.jsx';
import CharacterAssignmentModal from './CharacterAssignmentModal.jsx';
import PlayerVacatedModal from './PlayerVacatedModal.jsx';
import VoiceInputScribeV2 from '../VoiceInputScribeV2.jsx';

const PLAYER_SOCKET_GLOBAL_KEY = '__gaia_player_active_socket';
const CHARACTER_DRAFT_STORAGE_PREFIX = 'player-seat-draft';

// Simple UUID generator for message correlation
function generateMessageId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
}

// Merge local messages with backend history
// Keeps local messages that aren't in backend yet, replaces with backend version when available
function mergeMessages(localMessages, backendMessages) {
  const merged = [];
  const backendByMessageId = new Map();
  const backendByTimestamp = new Map();

  // Index backend messages by message_id and timestamp for fast lookup
  backendMessages.forEach(msg => {
    if (msg.message_id) {
      backendByMessageId.set(msg.message_id, msg);
    }
    if (msg.timestamp) {
      backendByTimestamp.set(msg.timestamp, msg);
    }
  });

  // Process local messages
  const processedBackendIds = new Set();
  localMessages.forEach(localMsg => {
    let backendVersion = null;

    // Try to find backend version by message_id
    if (localMsg.message_id) {
      backendVersion = backendByMessageId.get(localMsg.message_id);
    }

    // Fallback: try to match by timestamp for older messages without message_id
    if (!backendVersion && localMsg.timestamp) {
      backendVersion = backendByTimestamp.get(localMsg.timestamp);
    }

    if (backendVersion) {
      // Use backend version (confirmed)
      merged.push({ ...backendVersion, isLocal: false });
      processedBackendIds.add(backendVersion.message_id || backendVersion.timestamp);
    } else if (localMsg.isLocal) {
      // Keep local message (not yet confirmed by backend)
      merged.push(localMsg);
    }
    // Skip local messages that are neither in backend nor marked isLocal
  });

  // Add any backend messages that weren't matched with local messages
  backendMessages.forEach(backendMsg => {
    const id = backendMsg.message_id || backendMsg.timestamp;
    if (!processedBackendIds.has(id)) {
      merged.push({ ...backendMsg, isLocal: false });
    }
  });

  // Sort by timestamp
  merged.sort((a, b) => {
    const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
    const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
    return timeA - timeB;
  });

  return merged;
}

const PlayerPage = () => {
  const { sessionId } = useParams(); // Get session ID from URL
  const { user, getAccessTokenSilently, refreshAccessToken, isAuthenticated } = useAuth();

  // User profile with email (used for both collab and voice)
  const currentUserProfile = useMemo(() => {
    if (!user) {
      return null;
    }
    return {
      name: user.full_name || user.username || user.display_name || user.email || null,
      email: user.email || null,
    };
  }, [user]);

  // Extract user email from Auth0 (for voice transcription)
  const userEmail = user?.email || null;

  // Synchronized audio streaming (only playback mechanism)
  const audioStream = useAudioStream();

  // Campaign ID loaded from URL params via useEffect (see below)
  const [currentCampaignId, setCurrentCampaignId] = useState(null);
  const [campaignName, setCampaignName] = useState('');
  const [structuredDataBySession, setStructuredDataBySession] = useState({});
  const [messagesBySession, setMessagesBySession] = useState({});
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [imageRefreshTriggersBySession, setImageRefreshTriggersBySession] = useState({});
  const [lastRoomEvent, setLastRoomEvent] = useState(null);
  const loadingCampaignsRef = useRef(new Set()); // Track campaigns currently being loaded

  // Streaming DM state - tracks chunks as they arrive
  // Note: Player options use existing PlayerOptionsAgent, not streaming DM
  const [streamingNarrativeBySession, setStreamingNarrativeBySession] = useState({});
  const [streamingResponseBySession, setStreamingResponseBySession] = useState({});
  const [isNarrativeStreamingBySession, setIsNarrativeStreamingBySession] = useState({});
  const [isResponseStreamingBySession, setIsResponseStreamingBySession] = useState({});

  const latestStructuredData = currentCampaignId
    ? structuredDataBySession[currentCampaignId] ?? null
    : null;
  const campaignMessages = currentCampaignId
    ? messagesBySession[currentCampaignId] || []
    : [];

  const handleRoomEvent = useCallback((event) => {
    setLastRoomEvent({ event, timestamp: Date.now() });
  }, []);

  const setSessionMessages = useCallback(
    (sessionId, updater) => {
      if (!sessionId) {
        return;
      }
      setMessagesBySession((previous) => {
        const current = previous[sessionId] || [];
        const next = typeof updater === 'function' ? updater(current) : updater;
        if (next === current) {
          return previous;
        }
        return { ...previous, [sessionId]: next };
      });
    },
    [setMessagesBySession]
  );

  const markLastDmMessageHasAudio = useCallback(
    (sessionId) => {
      if (!sessionId) {
        return;
      }
      setSessionMessages(sessionId, (previous) => {
        if (!previous.length) {
          return previous;
        }
        for (let index = previous.length - 1; index >= 0; index -= 1) {
          const candidate = previous[index];
          if (candidate?.sender === 'dm') {
            if (candidate.hasAudio) {
              return previous;
            }
            const updated = [...previous];
            updated[index] = { ...candidate, hasAudio: true };
            return updated;
          }
        }
        return previous;
      });
    },
    [setSessionMessages]
  );

  // Audio now handled by synchronized streaming via WebSocket
  // No need to manually enqueue - backend manages the queue

  const setSessionStructuredData = useCallback(
    (sessionId, updater) => {
      if (!sessionId) {
        return;
      }
      setStructuredDataBySession((previous) => {
        const current = Object.prototype.hasOwnProperty.call(previous, sessionId)
          ? previous[sessionId]
          : null;
        const next = typeof updater === 'function' ? updater(current) : updater;
        if (next === current) {
          return previous;
        }
        // Audio handled by backend synchronized streaming
        return { ...previous, [sessionId]: next };
      });
    },
    [setStructuredDataBySession]
  );


  // WebSocket connection state
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnectingRef = useRef(false); // Track if connection is in progress
  const MAX_BACKOFF_EXPONENT = 5;
  const RECONNECT_WARNING_THRESHOLD = 6;
  const historyRefreshTimerRef = useRef(null);
  const manualCloseRef = useRef(false);
  const lastNarrativeChunkSignatureRef = useRef({});
  const lastResponseChunkSignatureRef = useRef({});
  const activeSessionIdRef = useRef(sessionId); // Use sessionId from URL
  const attemptedCampaigns = useRef(new Set()); // Track campaigns we've attempted to prevent retry loops


  // Audio permission state
  const [audioPermissionState, setAudioPermissionState] = useState('pending'); // 'pending' | 'granted' | 'denied' | 'prompt'
  const audioPermissionRequestedRef = useRef(false);

  // Set up Auth0 token provider for apiService
  useEffect(() => {
    if (getAccessTokenSilently && !apiService.getAccessToken) {
      apiService.setTokenProvider(async () => {
        try {
          return await getAccessTokenSilently();
        } catch (error) {
          console.warn('Failed to get Auth0 token in PlayerPage:', error);
          return null;
        }
      });
    }
  }, [getAccessTokenSilently]);

  // Request audio permission on mount after authentication
  useEffect(() => {
    if (!isAuthenticated || audioPermissionRequestedRef.current) {
      return;
    }

    const requestAudioPermission = async () => {
      // Check localStorage to avoid repeated prompts
      const storedPermission = localStorage.getItem('audioPermissionState');
      if (storedPermission === 'granted' || storedPermission === 'denied') {
        setAudioPermissionState(storedPermission);
        audioPermissionRequestedRef.current = true;
        return;
      }

      try {
        console.log('🎤 Requesting microphone permission...');
        setAudioPermissionState('prompt');

        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 48000
          }
        });

        // Release the stream immediately - we just wanted to check permission
        stream.getTracks().forEach(track => track.stop());

        console.log('🎤 Microphone permission granted');
        setAudioPermissionState('granted');
        localStorage.setItem('audioPermissionState', 'granted');
      } catch (error) {
        console.warn('🎤 Microphone permission denied or error:', error);
        if (error.name === 'NotAllowedError') {
          setAudioPermissionState('denied');
          localStorage.setItem('audioPermissionState', 'denied');
        } else if (error.name === 'NotFoundError') {
          setAudioPermissionState('denied');
          console.error('🎤 No microphone device found');
        } else {
          setAudioPermissionState('denied');
          console.error('🎤 Microphone access error:', error);
        }
      } finally {
        audioPermissionRequestedRef.current = true;
      }
    };

    requestAudioPermission();
  }, [isAuthenticated]);

  useEffect(() => {
    activeSessionIdRef.current = currentCampaignId;
  }, [currentCampaignId]);

  // Auto-enable audio on first user interaction
  useEffect(() => {
    if (!audioStream.needsUserGesture) {
      return;
    }

    const handleUserInteraction = () => {
      audioStream.resumePlayback();
    };

    // Listen for any user interaction to auto-enable audio
    document.addEventListener('click', handleUserInteraction, { once: true });
    document.addEventListener('keydown', handleUserInteraction, { once: true });
    document.addEventListener('touchstart', handleUserInteraction, { once: true });

    return () => {
      document.removeEventListener('click', handleUserInteraction);
      document.removeEventListener('keydown', handleUserInteraction);
      document.removeEventListener('touchstart', handleUserInteraction);
    };
  }, [audioStream]);

  // Load simple campaigns to map IDs to names for display
  // Removed: No longer fetching all campaign names, will get name from single campaign load.

  // Transform structured data for PlayerView components
  const parseField = useCallback((field, { allowEmptyObject = true } = {}) => {
    if (field === null || field === undefined) {
      return null;
    }

    if (typeof field === 'object') {
      if (!allowEmptyObject && Object.keys(field).length === 0) {
        return null;
      }
      return field;
    }

    if (typeof field === 'string') {
      const trimmed = field.trim();
      if (trimmed.length === 0) {
        return allowEmptyObject ? field : null;
      }
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
          return JSON.parse(trimmed);
        } catch (error) {
          console.warn('Failed to parse structured field:', field, error);
        }
      }
      return field;
    }

    return field;
  }, []);

  const transformStructuredData = useCallback((structData) => {
    const base = {
      narrative: structData.narrative || '',
      all_narratives: structData.all_narratives || null,
      turn: structData.turn || '',
      status: structData.status || '',
      characters: parseField(structData.characters),
      turn_info: parseField(structData.turn_info, { allowEmptyObject: false }),
      combat_status: parseField(structData.combat_status),  // Allow empty object - it's valid combat state
      environmental_conditions: structData.environmental_conditions || '',
      immediate_threats: structData.immediate_threats || '',
      story_progression: structData.story_progression || '',
      // New StructuredGameData fields
      answer: structData.answer || '',
      player_options: structData.player_options || '',
      // Image generation fields
      generated_image_url: structData.generated_image_url || '',
      generated_image_path: structData.generated_image_path || '',
      generated_image_prompt: structData.generated_image_prompt || '',
      generated_image_type: structData.generated_image_type || '',
      audio: structData.audio || null,
    };
    if (structData.combat_state) {
      base.combat_state = structData.combat_state;
    }
    return base;
  }, [parseField]);

  const loadCampaignData = useCallback(async (campaignId, options = {}) => {
    if (!campaignId) {
      return;
    }

    const { mergeWithLocal = false } = options;

    // Prevent duplicate simultaneous loads of the same campaign
    if (loadingCampaignsRef.current.has(campaignId)) {
      console.log(`🎮 Campaign ${campaignId} is already loading, skipping duplicate request`);
      return;
    }

    const sessionId = campaignId;
    try {
      // Mark this campaign as loading
      loadingCampaignsRef.current.add(campaignId);
      setIsLoading(true);

      const data = await apiService.readSimpleCampaign(campaignId);
      console.log('🎮 PlayerPage received from backend:', data);
      console.log('🎮 Backend structured_data.combat_status:', data?.structured_data?.combat_status);
      if (data && data.success && data.structured_data) {
        const transformedData = transformStructuredData(data.structured_data);
        console.log('🎮 PlayerPage transformed data:', transformedData);
        setSessionStructuredData(sessionId, transformedData);
        setCampaignName(data.name || sessionId); // Set campaign name from response

        if (data.messages && Array.isArray(data.messages)) {
          if (mergeWithLocal) {
            // Merge backend messages with local messages
            setSessionMessages(sessionId, (localMessages) => {
              const backendMessages = data.messages.map(msg => ({
                ...msg,
                message_id: msg.message_id,
                isLocal: false
              }));
              const merged = mergeMessages(localMessages, backendMessages);
              console.log('🎮 Merged messages:', merged.length, '(', localMessages.length, 'local +', backendMessages.length, 'backend)');
              return merged;
            });
          } else {
            // Replace messages (initial load)
            setSessionMessages(sessionId, data.messages);
          }
        } else {
          setSessionMessages(sessionId, []);
        }
      } else {
        setSessionStructuredData(sessionId, null);
        setSessionMessages(sessionId, []);
        setCampaignName(sessionId); // Fallback to ID if no name
      }
    } catch (loadError) {
      console.error('Error loading campaign data:', loadError);
      setError(`Failed to load campaign: ${loadError.message}`);
      setCampaignName(campaignId); // Fallback to ID on error

      // Remove from loading set
      loadingCampaignsRef.current.delete(campaignId);
      setIsLoading(false);

      // Re-throw error so caller's .catch() block can handle it
      throw loadError;
    } finally {
      // Remove from loading set (if not already done in catch)
      loadingCampaignsRef.current.delete(campaignId);
      setIsLoading(false);
    }
  }, [setSessionMessages, setSessionStructuredData, transformStructuredData, setCampaignName]);

  // User audio queue playback (shared hook)
  const { fetchUserAudioQueue } = useUserAudioQueue({ user, audioStream, apiService });

  // Load campaign from URL session ID
  useEffect(() => {
    if (sessionId && sessionId !== currentCampaignId) {
      // Check if we've already tried and failed to load this campaign
      if (attemptedCampaigns.current.has(sessionId)) {
        console.log('⚠️ Already attempted to load campaign:', sessionId, '- skipping retry');
        return;
      }

      console.log('📍 Loading campaign from URL:', sessionId);

      // Mark this campaign as attempted BEFORE calling loadCampaignData
      attemptedCampaigns.current.add(sessionId);

      // Update activeSessionIdRef to match URL
      activeSessionIdRef.current = sessionId;

      loadCampaignData(sessionId)
        .then(() => {
          console.log('✅ Successfully loaded campaign from URL:', sessionId);
          setCurrentCampaignId(sessionId);
          // Save to localStorage for UI tracking (optional)
          if (typeof window !== 'undefined') {
            localStorage.setItem('lastCampaignId', sessionId);
          }
          // Remove from attempted set on success so user can retry later
          attemptedCampaigns.current.delete(sessionId);
        })
        .catch(error => {
          console.error('❌ Failed to load campaign from URL:', error);

          // Handle different error types with user-friendly messages
          if (error.message?.includes('404') || error.message?.includes('not found')) {
            setError('Campaign not found');
            // Keep in attempted set - don't retry 404s
          } else if (error.message?.includes('403') || error.message?.includes('unauthorized') || error.message?.includes('Access denied')) {
            setError('You do not have access to this campaign');
            // Keep in attempted set - don't retry access denied
          } else {
            setError('Unable to load campaign');
            // For transient errors, remove from attempted set to allow retry
            attemptedCampaigns.current.delete(sessionId);
          }
        });
    }
  }, [sessionId, currentCampaignId, loadCampaignData]);

  // Join shared session if invite token present in URL
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const currentUrl = new URL(window.location.href);
    const inviteToken = currentUrl.searchParams.get('invite');
    if (!inviteToken) {
      return;
    }

    currentUrl.searchParams.delete('invite');
    window.history.replaceState({}, '', currentUrl.toString());

    let cancelled = false;
    let clearFeedbackTimeout = null;
    const joinSharedSession = async () => {
      try {
        setIsLoading(true);
        const response = await apiService.joinSessionByInvite(inviteToken);
        const sessionId = response?.session_id;
        if (!sessionId) {
          throw new Error('Invite did not return a session id');
        }
        if (cancelled) {
          return;
        }
        activeSessionIdRef.current = sessionId;
        setCurrentCampaignId(sessionId);
        localStorage.setItem('lastCampaignId', sessionId);
        await loadCampaignData(sessionId);
      } catch (err) {
        console.error('Failed to join player session via invite:', err);
        if (!cancelled) {
          setError(`Failed to join shared session: ${err.message || err}`);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    joinSharedSession();

    return () => {
      cancelled = true;
      if (clearFeedbackTimeout) {
        clearTimeout(clearFeedbackTimeout);
      }
    };
  }, [loadCampaignData]);

  // Debounced history refresh function - ONLY used when really needed (tab switch to empty history)
  // WebSocket already delivers real-time updates, so avoid redundant full campaign reloads
  const debouncedHistoryRefresh = useCallback((campaignId) => {
    if (historyRefreshTimerRef.current) {
      clearTimeout(historyRefreshTimerRef.current);
    }

    historyRefreshTimerRef.current = setTimeout(() => {
      console.log('📜 Auto-refreshing history after WebSocket update');
      loadCampaignData(campaignId);
    }, 1000);
  }, [loadCampaignData]);

  // Handle campaign updates from WebSocket
  const handleCampaignUpdate = useCallback((update) => {
    console.log('🎮 Received campaign update:', update.type, update);
    const sessionId = update?.campaign_id;

    switch (update.type) {
      case 'error': {
        console.warn('🎮 WS error update:', update);
        if (typeof update.reason === 'string') {
          setError(update.reason);
        }
        // If auth is required and we got an auth error, try to refresh token once
        if ((update.code === 4401 || /auth/i.test(update.reason || '')) && isAuthenticated) {
          (async () => {
            try {
              const refreshed = await refreshAccessToken?.();
              if (refreshed) {
                console.log('🎮 Token refreshed after WS error; reconnecting');
                connectWebSocket({ forceReconnect: true });
              } else {
                console.log('🎮 Refresh token unavailable; initiated re-login flow');
              }
            } catch (e) {
              console.warn('🎮 Failed to refresh token after WS error');
            }
          })();
        }
        break;
      }
      case 'campaign_active':
      case 'campaign_loaded': {
        console.log('🎮 Campaign activated/loaded:', update.campaign_id);
        if (update.campaign_id !== currentCampaignId) {
          setCurrentCampaignId(update.campaign_id);
          localStorage.setItem('lastCampaignId', update.campaign_id);
        }

        if (sessionId && update.structured_data) {
          const transformedData = transformStructuredData(update.structured_data);
          setSessionStructuredData(sessionId, transformedData);
          console.log('🎮 Updated structured data from WebSocket');
        }

        // REMOVED: Redundant history refresh - WebSocket already delivers real-time updates
        // Only load history on initial connection or explicit user action
        break;
      }
      case 'campaign_updated': {
        console.log('🎮 Campaign updated:', update.campaign_id);
        console.log('🎮 Campaign update structured_data:', update.structured_data);
        console.log('🎮 Campaign update audio field:', update.structured_data?.audio);
        if (update.structured_data) {
          // If we don't have a current campaign, or if this is a different campaign,
          // update to the campaign that's actually sending updates
          if (!currentCampaignId || (sessionId && sessionId !== currentCampaignId)) {
            console.log('🎮 Switching to campaign:', update.campaign_id);
            setCurrentCampaignId(update.campaign_id);
            localStorage.setItem('lastCampaignId', update.campaign_id);
          }
          const transformedData = transformStructuredData(update.structured_data);
          if (sessionId) {
            setSessionStructuredData(sessionId, transformedData);
          }
          console.log('🎮 Updated structured data from campaign update');

          // If this was a streamed response, reload chat history from backend and merge with local
          const wasStreamed = Boolean(transformedData?.streamed || update.structured_data?.streamed);
          if (wasStreamed && sessionId) {
            console.log('🔄 Reloading chat history after streamed response (merge mode)');
            loadCampaignData(sessionId, { mergeWithLocal: true })
              .then(() => {
                console.log('✅ Chat history merged from backend');
                // Clear streaming content now that history has loaded
                setStreamingNarrativeBySession(prev => {
                  const updated = { ...prev };
                  delete updated[sessionId];
                  return updated;
                });
                delete lastNarrativeChunkSignatureRef.current[sessionId];
                setStreamingResponseBySession(prev => {
                  const updated = { ...prev };
                  delete updated[sessionId];
                  return updated;
                });
                delete lastResponseChunkSignatureRef.current[sessionId];
              })
              .catch((error) => {
                console.error('Failed to reload chat history:', error);
                // On error, still clear streaming content
                setStreamingNarrativeBySession(prev => {
                  const updated = { ...prev };
                  delete updated[sessionId];
                  return updated;
                });
                delete lastNarrativeChunkSignatureRef.current[sessionId];
                setStreamingResponseBySession(prev => {
                  const updated = { ...prev };
                  delete updated[sessionId];
                  return updated;
                });
                delete lastResponseChunkSignatureRef.current[sessionId];
              });
          }
        }
        break;
      }
      case 'campaign_deactivated': {
        console.log('🎮 Campaign deactivated');
        const deactivatedId = sessionId || currentCampaignId;
        if (deactivatedId) {
          setSessionStructuredData(deactivatedId, null);
          setSessionMessages(deactivatedId, []);
        }
        if (!sessionId || sessionId === currentCampaignId) {
          setCurrentCampaignId(null);
          localStorage.removeItem('lastCampaignId');
        }
        break;
      }

      case 'audio_available':
      case 'audio_chunk_ready': {
        // Fetch user's audio queue and start playback
        console.log('🎵 [PLAYER] Audio available, fetching user queue');
        const targetSessionId = update.campaign_id || sessionId;
        if (targetSessionId) {
          fetchUserAudioQueue(targetSessionId);
        }
        break;
      }

      case 'audio_stream_started': {
        // Synchronized audio stream started
        console.log('🎵 [PLAYER] Received audio_stream_started:', update);

        // Guard: Only start stream if nothing is currently playing
        // This prevents duplicate playback when both App.jsx and PlayerPage.jsx
        // receive the same audio_stream_started WebSocket message
        if (audioStream.isStreaming) {
          console.log('🎵 [PLAYER] ⏭️  Audio already playing, ignoring duplicate stream start');
          break;
        }

        const targetSessionId = update.campaign_id || sessionId;
        if (targetSessionId && update.stream_url) {
          const positionSec = update.position_sec || 0;
          const isLateJoin = update.is_late_join || false;
          console.log(`🎵 [PLAYER] Starting synchronized stream for ${targetSessionId}`, {
            position: positionSec,
            isLateJoin,
            stream_url: update.stream_url,
          });
          audioStream.startStream(
            targetSessionId,
            positionSec,
            isLateJoin,
            update.chunk_ids || [],
            update.stream_url, // Pass the stream URL from WebSocket (includes request_id)
          );
        }
        break;
      }

      case 'audio_stream_stopped': {
        // Synchronized audio stream stopped
        console.log('🎵 [PLAYER] Received audio_stream_stopped:', update);
        const targetSessionId = update.campaign_id || sessionId;
        if (targetSessionId) {
          console.log(`🎵 [PLAYER] Stopping synchronized stream for ${targetSessionId}`);
          audioStream.stopStream();
        }
        break;
      }

      case 'image_generated': {
        // New image was generated - trigger instant refresh in MediaGallery
        console.log('📸 Image generated event received:', update);
        if (sessionId && update.filename) {
          // Trigger MediaGallery refresh by updating a timestamp in separate UI state
          // (keeping UI state separate from game data)
          setImageRefreshTriggersBySession((prev) => ({
            ...prev,
            [sessionId]: Date.now()
          }));
          console.log(`📸 Triggered instant image refresh for ${update.filename}`);
        }
        break;
      }

      case 'pong':
        // Heartbeat response - connection is healthy
        break;

      case 'heartbeat':
        // Respond to server heartbeat
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'heartbeat',
          }));
        }
        break;

      case 'narrative_chunk': {
        console.log('📖 Narrative chunk received:', update.content, 'final:', update.is_final);
        if (sessionId) {
          const hasContent = typeof update.content === 'string' && update.content.length > 0;
          const signature = hasContent
            ? `${update.timestamp || ''}|${update.content}`
            : null;
          const lastSignature = lastNarrativeChunkSignatureRef.current[sessionId];

          if (hasContent && signature && lastSignature === signature) {
            console.log('📖 Skipping duplicate narrative chunk for session:', sessionId);
            break;
          }

          if (hasContent && signature) {
            lastNarrativeChunkSignatureRef.current[sessionId] = signature;
          }

          if (update.is_final && !hasContent) {
            // Streaming complete - just mark as not actively streaming
            setIsNarrativeStreamingBySession(prev => ({ ...prev, [sessionId]: false }));
            delete lastNarrativeChunkSignatureRef.current[sessionId];
          } else if (hasContent) {
            setStreamingNarrativeBySession(prev => {
              const previousContent = prev[sessionId] || '';
              if (previousContent.endsWith(update.content)) {
                return prev;
              }
              return {
                ...prev,
                [sessionId]: previousContent + update.content
              };
            });
            setIsNarrativeStreamingBySession(prev => ({
              ...prev,
              [sessionId]: !update.is_final
            }));
            if (update.is_final) {
              delete lastNarrativeChunkSignatureRef.current[sessionId];
            }
          }
        }
        break;
      }

      case 'player_response_chunk': {
        console.log('💬 Response chunk received:', update.content, 'final:', update.is_final);
        if (sessionId) {
          const hasContent = typeof update.content === 'string' && update.content.length > 0;
          const signature = hasContent
            ? `${update.timestamp || ''}|${update.content}`
            : null;
          const lastSignature = lastResponseChunkSignatureRef.current[sessionId];

          if (hasContent && signature && lastSignature === signature) {
            console.log('💬 Skipping duplicate response chunk for session:', sessionId);
            break;
          }

          if (hasContent && signature) {
            lastResponseChunkSignatureRef.current[sessionId] = signature;
          }

          if (update.is_final && !hasContent) {
            setIsResponseStreamingBySession(prev => ({ ...prev, [sessionId]: false }));
            delete lastResponseChunkSignatureRef.current[sessionId];
          } else if (hasContent) {
            setStreamingResponseBySession(prev => {
              const previousContent = prev[sessionId] || '';
              if (previousContent.endsWith(update.content)) {
                return prev;
              }
              return {
                ...prev,
                [sessionId]: previousContent + update.content
              };
            });
            setIsResponseStreamingBySession(prev => ({
              ...prev,
              [sessionId]: !update.is_final
            }));
            if (update.is_final) {
              delete lastResponseChunkSignatureRef.current[sessionId];
            }
          }
        }
        break;
      }

      case 'metadata_update': {
        console.log('📊 Metadata update received:', Object.keys(update.metadata || {}));
        if (sessionId && update.metadata) {
          // Merge metadata into structured data
          setSessionStructuredData(sessionId, (prevData) => ({
            ...prevData,
            ...update.metadata
          }));
        }
        break;
      }

      case 'connection_registered': {
        break;
      }

      default:
        console.log('🎮 Unknown update type:', update.type);
    }
  }, [
    currentCampaignId,
    debouncedHistoryRefresh,
    markLastDmMessageHasAudio,
    setSessionMessages,
    setSessionStructuredData,
    transformStructuredData,
    setStreamingNarrativeBySession,
    setStreamingResponseBySession,
    setIsNarrativeStreamingBySession,
    setIsResponseStreamingBySession
  ]);

  const waitForSocketClose = useCallback((socket, timeoutMs = 1000) => {
    if (!socket || socket.readyState === WebSocket.CLOSED) {
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      let resolved = false;

      const cleanup = () => {
        if (resolved) {
          return;
        }
        resolved = true;
        socket.removeEventListener('close', handleClose);
        clearTimeout(timeoutId);
        resolve();
      };

      const handleClose = () => {
        cleanup();
      };

      const timeoutId = setTimeout(() => {
        console.warn('🎮 Timed out waiting for previous WebSocket to close');
        cleanup();
      }, timeoutMs);

      socket.addEventListener('close', handleClose, { once: true });
    });
  }, []);

  // WebSocket connection management
  const connectWebSocket = useCallback(async (options = {}) => {
    const { forceReconnect = false } = options;
    const sessionId = activeSessionIdRef.current;
    if (!sessionId) {
      console.warn('🎮 Skipping WebSocket connect - no session ID available');
      return;
    }

    // Prevent duplicate connection attempts
    if (isConnectingRef.current) {
      console.log('🎮 Connection already in progress, skipping duplicate attempt');
      return;
    }

    if (!forceReconnect && typeof window !== 'undefined') {
      const globalSocket = window[PLAYER_SOCKET_GLOBAL_KEY];
      if (globalSocket && globalSocket !== wsRef.current) {
        const state = globalSocket.readyState;
        if (state !== WebSocket.CLOSED) {
          try {
            console.log('🎮 Closing stale global player socket before opening a new one');
            globalSocket.__manualClose = true;
            try {
              globalSocket.onmessage = null;
              globalSocket.onopen = null;
              globalSocket.onerror = null;
            } catch (cleanupError) {
              // ignore cleanup errors
            }
            if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
              globalSocket.close();
            }
          } catch (error) {
            console.warn('🎮 Failed closing global player socket:', error);
          }
          await waitForSocketClose(globalSocket, 2000);
        }
        if (window[PLAYER_SOCKET_GLOBAL_KEY] === globalSocket) {
          window[PLAYER_SOCKET_GLOBAL_KEY] = null;
        }
      }
    }

    const existingSocket = wsRef.current;
    if (existingSocket) {
      const sameSession = existingSocket.__sessionId === sessionId;
      const state = existingSocket.readyState;

      // If we already have an open or connecting socket for this session, skip reconnect unless forced
      if (!forceReconnect && sameSession && (state === WebSocket.OPEN || state === WebSocket.CONNECTING)) {
        console.log('🎮 WebSocket already exists for session, skipping duplicate connection');
        isConnectingRef.current = false;
        return;
      }

      // If the socket is already closing for this session and we're not forcing a reconnect, defer until close completes
      if (!forceReconnect && sameSession && state === WebSocket.CLOSING) {
        console.log('🎮 WebSocket closing for session, deferring new connection until close completes');
        isConnectingRef.current = false;
        return;
      }

      // Ensure the existing socket is fully closed before starting a new one
      if (state !== WebSocket.CLOSED && state !== WebSocket.CLOSING) {
        manualCloseRef.current = true;
        existingSocket.__manualClose = true;
        try {
          existingSocket.onmessage = null;
          existingSocket.onopen = null;
          existingSocket.onerror = null;
        } catch (cleanupError) {
          // Ignore cleanup errors
        }
        try {
          existingSocket.close();
        } catch (closeError) {
          console.warn('🎮 Error closing previous WebSocket:', closeError);
        }
      }
      await waitForSocketClose(existingSocket);

      // Ensure we clear the ref once the previous socket is done
      if (wsRef.current === existingSocket) {
        wsRef.current = null;
      }
      manualCloseRef.current = false;
    }

    // Mark connection in progress
    isConnectingRef.current = true;

    try {
      // Prefer configured WebSocket base URL (supports proxied backends)
      const configuredWsBase = (API_CONFIG?.WS_BASE_URL || '').trim();
      const wsBase = configuredWsBase
        ? configuredWsBase.replace(/\/$/, '')
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host}`;
      // Try to include Auth0 token when available. If not available yet, do NOT
      // open an unauthenticated socket that will immediately be rejected.
      let token = null;
      try {
        token = await getAccessTokenSilently();
        if (!token && typeof getAccessTokenSilently === 'function') {
          // Retry with explicit audience/scope in case initial login lacked API audience
          const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
          if (audience) {
            try {
              token = await getAccessTokenSilently({
                authorizationParams: {
                  audience,
                  scope: 'openid profile email offline_access'
                }
              });
            } catch (e2) {
              // ignore, will fall through to retry logic
            }
          }
        }
      } catch (err) {
        console.warn('🎮 Failed to get Auth0 token for WS, will retry shortly:', err?.error || err?.message || err);
        token = null;
      }

      // In production/auth-required environments, avoid connecting without a token
      const isProduction = window.location.hostname !== 'localhost' && 
                           window.location.hostname !== '127.0.0.1' &&
                           !window.location.hostname.startsWith('192.168.');
      const requireAuth = isProduction || import.meta.env.VITE_REQUIRE_AUTH === 'true';

      if (requireAuth && !token) {
        // Defer connection until a token is available to prevent 4401 loops
        const nextDelay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
        console.log(`🎮 Auth token unavailable; retrying WS connect in ${nextDelay}ms`);
        setError('Authentication required');
        if (!reconnectTimeoutRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current += 1;
            reconnectTimeoutRef.current = null;
            connectWebSocket();
          }, nextDelay);
        }
        isConnectingRef.current = false;
        return;
      }
      // Build WS URL without embedding sensitive tokens in query params
      const wsUrl = `${wsBase}/ws/campaign/player?session_id=${encodeURIComponent(sessionId)}`;

      console.log('🎮 Connecting to WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.__sessionId = sessionId;
      if (typeof window !== 'undefined') {
        window[PLAYER_SOCKET_GLOBAL_KEY] = ws;
      }

      ws.onopen = () => {
        console.log('🎮 Player WebSocket connected for session:', sessionId);

        // Send authentication token as first message if available
        if (token) {
          ws.send(JSON.stringify({ type: 'auth', token: token }));
        }

        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        isConnectingRef.current = false; // Clear connecting flag on success

        // Clear any pending reconnection
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }

        // Send a ping to confirm connection
        ws.send(JSON.stringify({ type: 'ping' }));

        // Fetch any pending audio in user's queue
        fetchUserAudioQueue(sessionId);
      };

      ws.onmessage = (event) => {
        console.log('🎮 RAW WebSocket message received:', event.data);
        try {
          const update = JSON.parse(event.data);
          console.log('🎮 PARSED WebSocket message:', update);
          handleCampaignUpdate(update);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = async (event) => {
        const closeCode = event?.code ?? 1000;
        const closeReason = event?.reason ?? '';
        console.log('🎮 Player WebSocket disconnected:', { code: closeCode, reason: closeReason });
        setIsConnected(false);

        const wasManualClose = Boolean(ws.__manualClose || manualCloseRef.current);
        if (ws.__manualClose) {
          delete ws.__manualClose;
        }
        if (manualCloseRef.current) {
          manualCloseRef.current = false;
        }

        // Only clear our ref if this is the socket that's actually closing
        if (wsRef.current === ws) {
          wsRef.current = null;
        } else {
          console.log('🎮 Stale player socket closed, ignoring');
          if (wasManualClose) {
            return;
          }
          return;
        }

        if (typeof window !== 'undefined' && window[PLAYER_SOCKET_GLOBAL_KEY] === ws) {
          window[PLAYER_SOCKET_GLOBAL_KEY] = null;
        }

        if (wasManualClose) {
          console.log('🎮 Manual websocket shutdown detected; skipping auto-reconnect');
          reconnectAttempts.current = 0;
          return;
        }

        // On auth/ACL errors, try a one-time token refresh then reconnect
        if ([4401, 4403, 4404].includes(closeCode)) {
          if (closeCode === 4401 && isAuthenticated) {
            try {
              const refreshed = await refreshAccessToken?.();
              if (refreshed) {
                console.log('🎮 Refreshed token after 4401; reconnecting');
                connectWebSocket();
              } else {
                console.log('🎮 Refresh token unavailable; prompted user to reauthenticate');
              }
            } catch (e) {
              setError('Authentication required');
            }
          } else if (closeCode === 4403) {
            setError('You do not have access to this campaign');
          } else if (closeCode === 4404) {
            setError('Campaign not found');
        }
        return;
      }

      const nextAttempt = reconnectAttempts.current + 1;

      if (!reconnectTimeoutRef.current) {
        const cappedBackoffStep = Math.min(Math.max(nextAttempt - 1, 0), MAX_BACKOFF_EXPONENT);
        const delay = Math.min(1000 * Math.pow(2, cappedBackoffStep), 30000); // Max 30s delay
        console.log(`🎮 Attempting WebSocket reconnection in ${delay}ms... (attempt ${nextAttempt})`);

        reconnectAttempts.current = nextAttempt;
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connectWebSocket();
        }, delay);
      }

      if (nextAttempt >= RECONNECT_WARNING_THRESHOLD) {
        setError('Connection lost. Retrying automatically...');
      } else {
        setError('Connection interrupted. Reconnecting...');
      }
    };

    ws.onerror = (error) => {
      console.error('🎮 WebSocket error details:', {
        type: error.type,
          target: error.target?.url,
          readyState: error.target?.readyState,
          timestamp: new Date().toISOString()
        });
        setError('Connection error - attempting to reconnect...');
        isConnectingRef.current = false; // Clear connecting flag on error
        if (typeof window !== 'undefined' && window[PLAYER_SOCKET_GLOBAL_KEY] === ws) {
          window[PLAYER_SOCKET_GLOBAL_KEY] = null;
        }
      };

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setError(`Failed to connect: ${error.message}`);
      isConnectingRef.current = false; // Clear connecting flag on exception
    }
  }, [handleCampaignUpdate, waitForSocketClose]);

  // Initialize WebSocket connection when campaign is loaded
  useEffect(() => {
    if (currentCampaignId) {
      connectWebSocket();
    }

    return () => {
      if (wsRef.current) {
        try {
          manualCloseRef.current = true;
          wsRef.current.__manualClose = true;
          try {
            wsRef.current.onmessage = null;
            wsRef.current.onopen = null;
            wsRef.current.onerror = null;
          } catch (cleanupError) {
            // ignore
          }
          wsRef.current.close();
        } catch (closeError) {
          console.warn('🎮 Error closing WebSocket during cleanup:', closeError);
        } finally {
          wsRef.current = null;
          manualCloseRef.current = false;
        }
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (historyRefreshTimerRef.current) {
        clearTimeout(historyRefreshTimerRef.current);
        historyRefreshTimerRef.current = null;
      }
      // Clear connecting flag on cleanup
      isConnectingRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentCampaignId]); // Only reconnect when campaign changes, not when connectWebSocket changes

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const handleStreamComplete = (event) => {
      const detail = event?.detail || {};
      const chunkIds = detail.chunkIds;
      if (!chunkIds || !chunkIds.length) {
        return;
      }
      const socket = wsRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn('[PLAYER][AUDIO_STREAM] Cannot send audio_played ack - socket unavailable');
        return;
      }
      const payload = {
        type: 'audio_played',
        campaign_id: detail.sessionId || currentCampaignId,
        chunk_ids: chunkIds,
      };
      socket.send(JSON.stringify(payload));
      console.log('[PLAYER][AUDIO_STREAM] Sent audio_played ack | chunks=%s',
        chunkIds.length);
    };

    window.addEventListener(AUDIO_STREAM_COMPLETED_EVENT, handleStreamComplete);
    return () => {
      window.removeEventListener(AUDIO_STREAM_COMPLETED_EVENT, handleStreamComplete);
    };
  }, [currentCampaignId]);

  // Handle player actions
  const handlePlayerAction = (action) => {
    if (!currentCampaignId) {
      setError('No campaign selected');
      return;
    }

    // The current behavior (filling text box) is already handled elsewhere
    // No replacement needed - just removed the sendPlayerSuggestion call
  };

  // Demo character data
  const demoCharacter = {
    name: "Gaius",
    class: "Barbarian",
    level: 5,
    race: "Human",
    background: "Folk Hero",
    stats: {
      strength: 18,
      dexterity: 14,
      constitution: 16,
      intelligence: 10,
      wisdom: 12,
      charisma: 13
    },
    abilities: [
      {
        id: 'rage',
        name: 'Rage',
        type: 'feature',
        description: 'Enter a battle fury that grants bonus damage and resistance to physical damage.',
        uses: { current: 3, max: 3 },
        usageType: 'per_short_rest'
      },
      {
        id: 'reckless_attack',
        name: 'Reckless Attack',
        type: 'feature',
        description: 'Attack with advantage, but enemies have advantage against you until your next turn.',
        uses: { current: -1, max: -1 }, // Unlimited use
        usageType: 'unlimited'
      }
    ],
    hitPoints: { current: 65, max: 65 },
    armorClass: 16,
    proficiencyBonus: 3,
    equipment: [
      'Greataxe',
      'Chain Mail',
      'Shield',
      'Handaxe (2)',
      'Explorer\'s Pack'
    ]
  };

  const resolvedRoomCampaignId = currentCampaignId || sessionId || null;

  return (
    <RoomProvider
      campaignId={resolvedRoomCampaignId}
      currentUserId={user?.user_id || null}
      currentUserProfile={currentUserProfile}
      webSocketRef={wsRef}
      onRoomEvent={handleRoomEvent}
    >
      <PlayerRoomShell
        campaignName={campaignName}
        currentCampaignId={currentCampaignId}
        sessionId={sessionId}
        isConnected={isConnected}
        reconnectAttemptsRef={reconnectAttempts}
        error={error}
        isLoading={isLoading}
        imageRefreshTriggersBySession={imageRefreshTriggersBySession}
        latestStructuredData={latestStructuredData}
        campaignMessages={campaignMessages}
        handlePlayerAction={handlePlayerAction}
        loadCampaignData={loadCampaignData}
        streamingNarrativeBySession={streamingNarrativeBySession}
        streamingResponseBySession={streamingResponseBySession}
        isNarrativeStreamingBySession={isNarrativeStreamingBySession}
        isResponseStreamingBySession={isResponseStreamingBySession}
        demoCharacter={demoCharacter}
        roomEvent={lastRoomEvent}
        currentUserId={user?.user_id || null}
        campaignId={currentCampaignId}
        user={user}
        audioPermissionState={audioPermissionState}
        userEmail={userEmail}
      />
    </RoomProvider>
  );
};

const PlayerRoomShell = ({
  campaignName,
  currentCampaignId,
  sessionId,
  isConnected,
  reconnectAttemptsRef,
  error,
  isLoading,
  imageRefreshTriggersBySession,
  latestStructuredData,
  campaignMessages,
  handlePlayerAction,
  loadCampaignData,
  streamingNarrativeBySession,
  streamingResponseBySession,
  isNarrativeStreamingBySession,
  isResponseStreamingBySession,
  demoCharacter,
  roomEvent,
  currentUserId,
  campaignId,
  user,
  audioPermissionState,
  userEmail,
}) => {
  const {
    playerSeats,
    roomState,
    roomSummary,
    loading: roomLoading,
    currentUserSeat,
    currentUserSeatNeedsCharacter,
    currentUserPlayerSeat,
    currentUserPlayerSeatNeedsCharacter,
    occupySeat,
    refreshRoomState,
    assignCharacter,
    isDMSeated,
  } = useRoom();

  // Collaborative editing WebSocket state
  const [collabIsConnected, setCollabIsConnected] = useState(false);
  const [collabPlayers, setCollabPlayers] = useState([]);
  const [collabPlayerId, setCollabPlayerId] = useState('');
  const [assignedPlayerName, setAssignedPlayerName] = useState('');
  const collabWsRef = useRef(null);

  // Voice transcription state
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceActivityLevel, setVoiceActivityLevel] = useState(0);
  const collabEditorRef = useRef(null);
  const isTranscribingRef = useRef(false);

  useEffect(() => {
    isTranscribingRef.current = isTranscribing;
  }, [isTranscribing]);

  // Debug: Log VoiceInputScribeV2 rendering conditions
  useEffect(() => {
    const shouldRender = isTranscribing && audioPermissionState === 'granted';
    console.log('[PlayerPage.jsx VoiceInput Debug]', {
      isTranscribing,
      audioPermissionState,
      shouldRenderVoiceInput: shouldRender
    });
  }, [isTranscribing, audioPermissionState]);

  // Voice transcription handler - sends text to backend via collab WebSocket
  // Backend uses player_id from the connection to update the correct section
  const handleVoiceTranscription = useCallback((transcribedText, metadata) => {
    console.log('🎤 Voice transcription received:', transcribedText, metadata);

    // Ignore any transcription events if the mic toggle is off
    if (!isTranscribingRef.current) {
      console.warn('🎤 Ignoring transcription because mic is not active');
      return;
    }

    if (!collabWsRef.current || collabWsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('🎤 Collab WebSocket not connected, voice text not sent');
      return;
    }

    // Send voice transcription to backend - it will update the Y.js doc
    // using the player_id associated with this connection
    collabWsRef.current.send(JSON.stringify({
      type: 'voice_transcription',
      text: transcribedText,
      is_partial: metadata?.is_partial ?? false
    }));

    console.log('🎤 Sent voice_transcription to collab backend, is_partial:', metadata?.is_partial);
  }, []);

  // Toggle voice transcription on/off
  const toggleVoiceTranscription = useCallback(async () => {
    // If turning OFF, just toggle
    if (isTranscribing) {
      setIsTranscribing(false);
      return;
    }

    // Helper to signal backend that a new voice session is starting
    // This resets committed_content tracking so edits are preserved
    const sendVoiceSessionStart = () => {
      if (collabWsRef.current?.readyState === WebSocket.OPEN) {
        collabWsRef.current.send(JSON.stringify({
          type: 'voice_session_start'
        }));
        console.log('🎤 Sent voice_session_start to reset backend tracking');
      }
    };

    // If turning ON, request permission first if not granted
    if (audioPermissionState !== 'granted') {
      try {
        console.log('🎤 Requesting microphone permission for transcription...');
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 16000  // Match ElevenLabs requirement
          }
        });

        // Release the stream immediately - VoiceInputScribeV2 will request it again
        stream.getTracks().forEach(track => track.stop());

        console.log('✅ Microphone permission granted');
        setAudioPermissionState('granted');
        localStorage.setItem('audioPermissionState', 'granted');
        sendVoiceSessionStart();
        setIsTranscribing(true);
      } catch (error) {
        console.error('❌ Microphone permission denied:', error);
        setAudioPermissionState('denied');
        localStorage.setItem('audioPermissionState', 'denied');
        // Don't enable transcription if permission denied
      }
    } else {
      // Permission already granted, just toggle on
      sendVoiceSessionStart();
      setIsTranscribing(true);
    }
  }, [isTranscribing, audioPermissionState]);

  // Reset microphone permission (clear localStorage and re-prompt)
  const resetMicPermission = useCallback(async () => {
    console.log('🎤 Resetting microphone permission...');
    localStorage.removeItem('audioPermissionState');
    audioPermissionRequestedRef.current = false;
    setAudioPermissionState('pending');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 48000
        }
      });
      stream.getTracks().forEach(track => track.stop());
      console.log('🎤 Microphone permission granted after reset');
      setAudioPermissionState('granted');
      localStorage.setItem('audioPermissionState', 'granted');
    } catch (error) {
      console.error('🎤 Microphone permission denied after reset:', error);
      setAudioPermissionState('denied');
      localStorage.setItem('audioPermissionState', 'denied');
    }
  }, []);

  // Collaborative editing WebSocket connection
  useEffect(() => {
    if (!campaignId || !user || !user.email) {
      return;
    }

    // PlayerRoomShell is ONLY used in player view, so always connect as 'player'
    // (DM view uses App.jsx's separate WebSocket connection)
    // Use stable player ID (don't include character_id to avoid reconnections)
    const role = 'player';
    const playerId = `${user.email}:${role}`;

    // Use full character name to match document section labels
    const characterName = currentUserSeat?.character_name;
    const playerName = characterName || user.name || user.email.split('@')[0];

    // Set player ID and name
    setCollabPlayerId(playerId);
    setAssignedPlayerName(playerName);

    // Build collab WebSocket URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname;
    const wsPort = process.env.NODE_ENV === 'development' ? '8000' : window.location.port;
    const collabWsUrl = `${wsProtocol}//${wsHost}:${wsPort}/ws/collab/session/${campaignId}`;

    console.log('[Collab] Connecting as:', { playerId, playerName, role });

    const collabWs = new WebSocket(collabWsUrl);
    collabWsRef.current = collabWs;

    collabWs.onopen = () => {
      console.log('[Collab] WebSocket connected for session:', campaignId);
      setCollabIsConnected(true);

      // Register with backend
      collabWs.send(JSON.stringify({
        type: 'register',
        playerId: playerId,
        playerName: playerName,
        timestamp: new Date().toISOString()
      }));
    };

    collabWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'initial_state') {
          if (data.allPlayers) {
            setCollabPlayers(data.allPlayers);
            console.log('[Collab] All players:', data.allPlayers);
          }
        } else if (
          (data.type === 'collab_players' || data.type === 'collab_reset' || data.type === 'player_list') &&
          Array.isArray(data.players)
        ) {
          setCollabPlayers(data.players);
          console.log('[Collab] Updated player roster:', data.players);
        }
      } catch (err) {
        console.warn('[Collab] Failed to parse message:', err);
      }
    };

    collabWs.onclose = () => {
      console.log('[Collab] WebSocket disconnected');
      setCollabIsConnected(false);
    };

    collabWs.onerror = (error) => {
      console.error('[Collab] WebSocket error:', error);
    };

    return () => {
      if (collabWs && collabWs.readyState === WebSocket.OPEN) {
        collabWs.close();
      }
      collabWsRef.current = null;
      setCollabIsConnected(false);
    };
  }, [campaignId, user?.email, currentUserSeat?.character_name]);

  const [seatModalOpen, setSeatModalOpen] = useState(false);
  const [seatError, setSeatError] = useState(null);
  const [selectingSeatId, setSelectingSeatId] = useState(null);
  const [characterModalOpen, setCharacterModalOpen] = useState(false);
  const [characterDraft, setCharacterDraft] = useState(null);
  const [characterError, setCharacterError] = useState(null);
  const [characterSaving, setCharacterSaving] = useState(false);
  const [vacatedInfo, setVacatedInfo] = useState(null);

  const seatOwnedByCurrentUser = useMemo(() => {
    if (!currentUserId || !currentUserPlayerSeat) {
      return false;
    }
    const ownerId =
      currentUserPlayerSeat.owner_identity?.gaia_user_id ||
      currentUserPlayerSeat.owner_user_id ||
      null;
    return ownerId === currentUserId;
  }, [currentUserId, currentUserPlayerSeat]);

  const needsSeat = !roomLoading && !seatOwnedByCurrentUser;
  const roomStatus = roomState?.room_status || roomSummary?.room_status || null;

  useEffect(() => {
    if (needsSeat) {
      setSeatModalOpen(true);
    } else {
      setSeatModalOpen(false);
      setSeatError(null);
    }
  }, [needsSeat]);

  const draftStorageKey = useMemo(() => {
    if (!campaignId || !currentUserPlayerSeat?.seat_id) return null;
    return `${CHARACTER_DRAFT_STORAGE_PREFIX}:${campaignId}:${currentUserPlayerSeat.seat_id}`;
  }, [campaignId, currentUserPlayerSeat?.seat_id]);

  const createDefaultDraft = useCallback(() => {
    if (!currentUserPlayerSeat) return null;
    return {
      name: '',
      race: '',
      character_class: '',
      background: '',
      description: '',
      backstory: '',
      appearance: '',
      slot_id: currentUserPlayerSeat.slot_index ?? 0,
      seat_id: currentUserPlayerSeat.seat_id,
    };
  }, [currentUserPlayerSeat]);

  useEffect(() => {
    if (currentUserPlayerSeatNeedsCharacter && currentUserPlayerSeat && seatOwnedByCurrentUser) {
      let base = createDefaultDraft();
      if (draftStorageKey) {
        try {
          const saved = localStorage.getItem(draftStorageKey);
          if (saved) {
            base = { ...base, ...JSON.parse(saved) };
          }
        } catch (err) {
          console.warn('Failed to restore character draft', err);
        }
      }
      setCharacterDraft(base);
      setCharacterModalOpen(true);
    } else {
      setCharacterModalOpen(false);
      setCharacterDraft(null);
      setCharacterError(null);
    }
  }, [
    currentUserPlayerSeatNeedsCharacter,
    currentUserPlayerSeat,
    seatOwnedByCurrentUser,
    draftStorageKey,
    createDefaultDraft,
  ]);

  useEffect(() => {
    if (!draftStorageKey || !characterDraft) return;
    try {
      localStorage.setItem(draftStorageKey, JSON.stringify(characterDraft));
    } catch (err) {
      console.warn('Failed to persist character draft', err);
    }
  }, [characterDraft, draftStorageKey]);

  useEffect(() => {
    if (!draftStorageKey) return;
    if (!currentUserPlayerSeatNeedsCharacter) {
      localStorage.removeItem(draftStorageKey);
    }
  }, [currentUserPlayerSeatNeedsCharacter, draftStorageKey]);

  const handleSelectSeat = useCallback(async (seatId) => {
    if (!seatId) return;
    setSeatError(null);
    setSelectingSeatId(seatId);
    try {
      await occupySeat(seatId);
      setSeatModalOpen(false);
    } catch (err) {
      console.error('Player seat selection failed:', err);
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Seat could not be claimed. Please try another seat or refresh.';
      setSeatError(detail);
      refreshRoomState();
    } finally {
      setSelectingSeatId(null);
    }
  }, [occupySeat, refreshRoomState]);

  const reconnectAttempts = reconnectAttemptsRef?.current || 0;
  const seatModalRequiresSelection = needsSeat;

  const handleCharacterSubmit = useCallback(async () => {
    if (!seatOwnedByCurrentUser || !currentUserPlayerSeat?.seat_id) {
      setSeatError('Select an available seat before creating your character.');
      setSeatModalOpen(true);
      return;
    }
    if (!characterDraft) return;
    setCharacterSaving(true);
    setCharacterError(null);
    try {
      await assignCharacter(currentUserPlayerSeat.seat_id, characterDraft);
      if (draftStorageKey) {
        localStorage.removeItem(draftStorageKey);
      }
      setCharacterModalOpen(false);
    } catch (err) {
      console.error('Failed to save character', err);
      setCharacterError(err.message || 'Failed to save character');
      refreshRoomState();
    } finally {
      setCharacterSaving(false);
    }
  }, [
    assignCharacter,
    characterDraft,
    currentUserPlayerSeat,
    draftStorageKey,
    refreshRoomState,
    seatOwnedByCurrentUser,
  ]);

  useEffect(() => {
    if (!roomEvent?.event || !currentUserId) {
      return;
    }
    if (
      roomEvent.event.type === 'player_vacated' &&
      roomEvent.event.data?.previous_owner === currentUserId
    ) {
      setVacatedInfo({
        seatId: roomEvent.event.data?.seat_id || null,
        timestamp: roomEvent.timestamp,
      });
      setSeatError('The DM released your seat. Please choose another open seat.');
      setSeatModalOpen(true);
      refreshRoomState();
    }
  }, [roomEvent, currentUserId, refreshRoomState]);

  const vacatedSeatLabel = useMemo(() => {
    if (!vacatedInfo?.seatId) return 'your seat';
    const seat = playerSeats.find((s) => s.seat_id === vacatedInfo.seatId);
    if (!seat || seat.slot_index === undefined || seat.slot_index === null) {
      return 'your seat';
    }
    return `Seat ${seat.slot_index + 1}`;
  }, [vacatedInfo, playerSeats]);

  const handleVacatedConfirm = useCallback(() => {
    setVacatedInfo(null);
  }, []);

  return (
    <>
      <div className="min-h-screen bg-gaia-dark">
        {/* Header */}
        <SharedHeaderLayout>
            {/* Connection Status Indicator */}
            <div className={`px-3 py-1 rounded-full text-xs flex items-center gap-2 ${
              isConnected
                ? 'bg-green-900 text-green-300 border border-green-600'
                : reconnectAttempts > 0
                  ? 'bg-yellow-900 text-yellow-300 border border-yellow-600'
                  : 'bg-red-900 text-red-300 border border-red-600'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                isConnected
                  ? 'bg-green-400 animate-pulse'
                  : reconnectAttempts > 0
                    ? 'bg-yellow-400 animate-pulse'
                    : 'bg-red-400'
              }`} />
              {isConnected
                ? 'Live'
                : reconnectAttempts > 0
                  ? 'Reconnecting...'
                  : 'Disconnected'}
            </div>

            {currentCampaignId && (
              <CampaignNameDisplay name={campaignName || currentCampaignId} />
            )}
            <LobbyButton />
        </SharedHeaderLayout>

        {/* Voice Input (hidden background service) */}
        {isTranscribing && audioPermissionState === 'granted' && (
          <div style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden' }}>
            <VoiceInputScribeV2
              onSendMessage={handleVoiceTranscription}
              conversationalMode={true}
              userEmail={userEmail}
              characterId={currentUserPlayerSeat?.character_id || null}
              autoStart={true}
              onVoiceLevel={setVoiceActivityLevel}
              onRecordingStop={() => setIsTranscribing(false)}
            />
          </div>
        )}

        {/* Error display */}
        {error && !currentCampaignId && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-center bg-gaia-light rounded-lg p-8 max-w-md">
              <h2 className="text-xl font-bold text-red-400 mb-4">⚠️ Campaign Load Failed</h2>
              <p className="text-white mb-4 text-lg font-semibold">{error}</p>
              <p className="text-gray-300 mb-6 text-sm">
                {error?.includes('not found')
                  ? 'This campaign may have been deleted or the URL is incorrect.'
                  : error?.includes('access') || error?.includes('unauthorized')
                  ? 'You need to be invited to this campaign to view it.'
                  : 'There was a problem loading this campaign.'}
              </p>
              <Link
                to="/"
                className="inline-block px-6 py-3 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors font-bold"
              >
                🏠 Return to Campaign Lobby
              </Link>
            </div>
          </div>
        )}
        {error && currentCampaignId && (
          <div className="bg-gaia-error text-white px-4 py-3 mx-4 rounded-md font-bold mt-4">
            Error: {error}
          </div>
        )}


        {/* Loading overlay */}
        {isLoading && (
          <div className="fixed top-0 left-0 right-0 bottom-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gaia-light rounded-lg p-6 flex flex-col items-center">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent mb-4"></div>
              <span className="text-white">Processing your action...</span>
            </div>
          </div>
        )}

        {/* No campaign message */}
        {!currentCampaignId && !error && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-center bg-gaia-light rounded-lg p-8 max-w-md">
              {sessionId ? (
                <>
                  <h2 className="text-xl font-bold text-white mb-4">Loading Your Adventure...</h2>
                  <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent mx-auto my-4"></div>
                  <p className="text-gaia-muted mb-4">
                    Now fetching campaign details and preparing your character sheet. This should only take a moment.
                  </p>
                </>
              ) : (
                <>
                  <h2 className="text-xl font-bold text-white mb-4">No Active Campaign</h2>
                  <p className="text-gaia-muted mb-4">
                    Waiting for DM to load a campaign. You'll be automatically connected when a campaign starts.
                  </p>
                  {!isConnected && (
                    <p className="text-yellow-400 text-sm mb-4">
                      Connection status: {reconnectAttempts > 0 ? 'Reconnecting...' : 'Waiting for connection...'}
                    </p>
                  )}
                  <Link
                    to="/"
                    className="px-6 py-3 bg-gaia-success text-black rounded-lg hover:bg-green-500 transition-colors font-bold"
                  >
                    Go to Lobby
                  </Link>
                </>
              )}
            </div>
          </div>
        )}

        {/* Player View */}
        {currentCampaignId && (
          <div className="h-[calc(100vh-80px)]">
            <PlayerView
              campaignId={currentCampaignId}
              playerId="demo_player"
              characterData={demoCharacter}
              latestStructuredData={latestStructuredData}
              campaignMessages={campaignMessages}
              imageRefreshTrigger={imageRefreshTriggersBySession[currentCampaignId]}
              onPlayerAction={handlePlayerAction}
              onLoadCampaignData={loadCampaignData}
              streamingNarrative={streamingNarrativeBySession[currentCampaignId] || ''}
              streamingResponse={streamingResponseBySession[currentCampaignId] || ''}
              isNarrativeStreaming={isNarrativeStreamingBySession[currentCampaignId] || false}
              isResponseStreaming={isResponseStreamingBySession[currentCampaignId] || false}
              // Collaborative editing props
              collabWebSocket={collabWsRef.current}
              collabPlayerId={collabPlayerId}
              collabPlayerName={assignedPlayerName}
              collabAllPlayers={collabPlayers}
              collabIsConnected={collabIsConnected}
              // Voice input props
              audioPermissionState={audioPermissionState}
              onResetMicPermission={resetMicPermission}
              userEmail={userEmail}
              isTranscribing={isTranscribing}
              onToggleTranscription={toggleVoiceTranscription}
              voiceActivityLevel={voiceActivityLevel}
              collabEditorRef={collabEditorRef}
            />
          </div>
        )}
      </div>
      <SeatSelectionModal
        open={seatModalOpen}
        onClose={() => setSeatModalOpen(false)}
        requireSelection={seatModalRequiresSelection}
        seats={playerSeats}
        selectingSeatId={selectingSeatId}
        onSelectSeat={handleSelectSeat}
        onRefresh={refreshRoomState}
        errorMessage={seatError}
        roomStatus={roomStatus}
      />
      <CharacterAssignmentModal
        open={characterModalOpen && seatOwnedByCurrentUser && Boolean(currentUserPlayerSeat)}
        seat={currentUserPlayerSeat}
        draft={characterDraft}
        onDraftChange={setCharacterDraft}
        onSubmit={handleCharacterSubmit}
        isSubmitting={characterSaving}
        errorMessage={characterError}
        campaignId={campaignId}
      />
      <PlayerVacatedModal
        open={Boolean(vacatedInfo)}
        onConfirm={handleVacatedConfirm}
        seatLabel={vacatedSeatLabel}
      />
    </>
  );
};

// Wrap PlayerPage with AudioStreamProvider to enable synchronized audio streaming
function PlayerPageWithAudioStream() {
  return (
    <AudioStreamProvider>
      <PlayerPage />
    </AudioStreamProvider>
  );
}

export default PlayerPageWithAudioStream;
