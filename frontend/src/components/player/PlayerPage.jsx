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
import { SFXProvider, useSFX } from '../../context/sfxContext.jsx';
import { API_CONFIG } from '../../config/api.js';
import { generateUniqueId } from '../../utils/idGenerator.js';
import { useUserAudioQueue, handleAudioPlayedConfirmation } from '../../hooks/useUserAudioQueue.js';
import { RoomProvider, useRoom } from '../../contexts/RoomContext.jsx';
import SeatSelectionModal from './SeatSelectionModal.jsx';
import CharacterAssignmentModal from './CharacterAssignmentModal.jsx';
import PlayerVacatedModal from './PlayerVacatedModal.jsx';
import VoiceInputScribeV2 from '../VoiceInputScribeV2.jsx';
import { useGameSocket } from '../../hooks/useGameSocket.js';
import { useTurnBasedMessages } from '../../hooks/useTurnBasedMessages.js';

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

  // Collaborative editing state (managed here because Socket.IO handlers need to update it)
  const [collabIsConnected, setCollabIsConnected] = useState(false);
  const [collabPlayers, setCollabPlayers] = useState([]);
  const [collabPlayerId, setCollabPlayerId] = useState('');
  const [assignedPlayerName, setAssignedPlayerName] = useState('');

  // Synchronized audio streaming (only playback mechanism)
  const audioStream = useAudioStream();

  // Sound effects context
  const { handleSfxAvailable } = useSFX();

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

  // Turn-based messages for consistent display with DM view
  const {
    turns,
    isProcessing,
    handleTurnStarted,
    handleTurnMessage,
    handleTurnComplete,
    handleTurnError,
    handleInputReceived,
    loadTurnsFromHistory,
    clearTurns,
    appendStreamingText,
    setCurrentTurn,
  } = useTurnBasedMessages(currentCampaignId);

  // Track previous campaign to detect campaign switches (for clearing)
  const prevCampaignIdRef = useRef(currentCampaignId);
  useEffect(() => {
    console.log('📚 Turns loading effect:', {
      currentCampaignId,
      prevCampaignId: prevCampaignIdRef.current,
      campaignMessagesCount: campaignMessages?.length || 0,
      turnsCount: turns?.length || 0,
    });
    // Clear turns when campaign changes
    if (prevCampaignIdRef.current !== currentCampaignId) {
      console.log('📚 Campaign changed, clearing turns');
      clearTurns();
      prevCampaignIdRef.current = currentCampaignId;
    }
    // Load turns from messages
    if (campaignMessages && campaignMessages.length > 0) {
      console.log('📚 Loading turns from', campaignMessages.length, 'messages');
      loadTurnsFromHistory(campaignMessages);
    }
  }, [campaignMessages, currentCampaignId, loadTurnsFromHistory, clearTurns]);

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
      // Personalized player options (per-character options)
      personalized_player_options: structData.personalized_player_options || null,
      pending_observations: structData.pending_observations || null,
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

      // Initialize turn counter from backend (authoritative source)
      if (data?.current_turn != null) {
        setCurrentTurn(data.current_turn);
      }

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
  }, [setSessionMessages, setSessionStructuredData, transformStructuredData, setCampaignName, setCurrentTurn]);

  // Ref for socket emit - allows useUserAudioQueue to use socket before useGameSocket is called
  const socketEmitRef = useRef(null);
  const socketEmitWrapper = useCallback((...args) => {
    if (socketEmitRef.current) {
      socketEmitRef.current(...args);
    } else {
      console.warn('🎵 [USER_QUEUE] Socket emit not available yet, skipping:', args[0]);
    }
  }, []);

  // User audio queue playback (shared hook) - uses WebSocket for reliable acknowledgment
  const { fetchUserAudioQueue, audioBlocked, unlockAudio } = useUserAudioQueue({
    user,
    audioStream,
    apiService,
    socketEmit: socketEmitWrapper,
    campaignId: currentCampaignId,
  });

  // UNIFIED: Auto-enable all audio on first user interaction
  // CRITICAL for Safari: Handler must be SYNCHRONOUS - async functions lose gesture context!
  useEffect(() => {
    const needsUnlock = audioStream.needsUserGesture || audioBlocked;
    if (!needsUnlock) {
      return;
    }

    // IMPORTANT: This handler must NOT be async - Safari loses gesture context with async
    const handleUserInteraction = () => {
      console.log('🎵 [PLAYER] User interaction - unlocking all audio (sync handler)');
      if (audioBlocked) {
        unlockAudio();
      }
      if (audioStream.needsUserGesture) {
        audioStream.resumePlayback();
      }
    };

    const options = { once: true, capture: true };
    document.addEventListener('click', handleUserInteraction, options);
    document.addEventListener('keydown', handleUserInteraction, options);
    document.addEventListener('touchstart', handleUserInteraction, options);

    return () => {
      document.removeEventListener('click', handleUserInteraction, options);
      document.removeEventListener('keydown', handleUserInteraction, options);
      document.removeEventListener('touchstart', handleUserInteraction, options);
    };
  }, [audioStream, audioBlocked, unlockAudio]);

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
          setSessionStructuredData(sessionId, (prev) => ({
            ...(prev || {}),
            ...transformedData,
            personalized_player_options:
              transformedData?.personalized_player_options ?? prev?.personalized_player_options ?? null,
            pending_observations:
              transformedData?.pending_observations ?? prev?.pending_observations ?? null,
          }));
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
            setSessionStructuredData(sessionId, (prev) => ({
              ...(prev || {}),
              ...transformedData,
              personalized_player_options:
                transformedData?.personalized_player_options ?? prev?.personalized_player_options ?? null,
              pending_observations:
                transformedData?.pending_observations ?? prev?.pending_observations ?? null,
            }));
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
        // No-op - audio_available already handles queue playback
        console.log('🎵 [PLAYER] Received audio_stream_started (no-op, audio_available handles queue)');
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
        // Socket.IO handles heartbeats automatically
        // This case is kept for compatibility but is typically not needed
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
            // Also update turn-based view with streaming text
            appendStreamingText(update.content, update.is_final);
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

      case 'personalized_player_options': {
        // Received personalized options for all connected players
        console.log('🎲 Personalized player options received:', update.personalized_player_options);
        if (sessionId && update.personalized_player_options) {
          setSessionStructuredData(sessionId, (prevData) => ({
            ...prevData,
            personalized_player_options: update.personalized_player_options
          }));
        }
        break;
      }

      case 'pending_observations': {
        // Received pending observations from secondary players
        console.log('👁️ Pending observations received:', update.pending_observations);
        if (sessionId && update.pending_observations) {
          setSessionStructuredData(sessionId, (prevData) => ({
            ...prevData,
            pending_observations: update.pending_observations
          }));
        }
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

  // Socket.IO connection using useGameSocket hook
  // Create handlers that wrap data with type field for handleCampaignUpdate
  const socketHandlers = useMemo(() => ({
    // Turn-based message events (real-time updates for history view)
    turn_started: handleTurnStarted,
    turn_message: handleTurnMessage,
    turn_complete: handleTurnComplete,
    turn_error: handleTurnError,
    // Input received event (immediate feedback when DM submits - includes input text)
    // Also clears player options since the turn has advanced
    input_received: (data) => {
      handleInputReceived(data);
      // Clear player options when turn advances
      const { session_id } = data;
      if (session_id) {
        setStructuredDataBySession(prev => {
          const current = prev[session_id];
          if (!current) return prev;
          return {
            ...prev,
            [session_id]: {
              ...current,
              personalized_player_options: null,
            }
          };
        });
      }
    },
    // Core game events
    narrative_chunk: (data) => handleCampaignUpdate({ ...data, type: 'narrative_chunk' }),
    player_response_chunk: (data) => handleCampaignUpdate({ ...data, type: 'player_response_chunk' }),
    player_options: (data) => handleCampaignUpdate({ ...data, type: 'player_options' }),
    personalized_player_options: (data) => handleCampaignUpdate({ ...data, type: 'personalized_player_options' }),
    pending_observations: (data) => handleCampaignUpdate({ ...data, type: 'pending_observations' }),
    metadata_update: (data) => handleCampaignUpdate({ ...data, type: 'metadata_update' }),
    campaign_updated: (data) => handleCampaignUpdate({ ...data, type: 'campaign_updated' }),
    campaign_loaded: (data) => handleCampaignUpdate({ ...data, type: 'campaign_loaded' }),
    campaign_active: (data) => handleCampaignUpdate({ ...data, type: 'campaign_active' }),
    campaign_deactivated: (data) => handleCampaignUpdate({ ...data, type: 'campaign_deactivated' }),
    initialization_error: (data) => handleCampaignUpdate({ ...data, type: 'initialization_error' }),
    // Audio events
    audio_available: (data) => handleCampaignUpdate({ ...data, type: 'audio_available' }),
    audio_chunk_ready: (data) => handleCampaignUpdate({ ...data, type: 'audio_chunk_ready' }),
    audio_stream_started: (data) => handleCampaignUpdate({ ...data, type: 'audio_stream_started' }),
    audio_stream_stopped: (data) => handleCampaignUpdate({ ...data, type: 'audio_stream_stopped' }),
    playback_queue_updated: (data) => handleCampaignUpdate({ ...data, type: 'playback_queue_updated' }),
    // Audio acknowledgment confirmation (for reliable user queue playback)
    audio_played_confirmed: handleAudioPlayedConfirmation,
    // Sound effects broadcast
    sfx_available: (data) => {
      console.log('🔊 [PLAYER] Received sfx_available event:', data);
      handleSfxAvailable(data, data.campaign_id || sessionId);
    },
    // Room events - handle both dot notation and direct names
    'room.seat_updated': (data) => handleCampaignUpdate({ ...data, type: 'room.seat_updated' }),
    'room.seat_character_updated': (data) => handleCampaignUpdate({ ...data, type: 'room.seat_character_updated' }),
    'room.campaign_started': (data) => handleCampaignUpdate({ ...data, type: 'room.campaign_started' }),
    'room.player_vacated': (data) => handleCampaignUpdate({ ...data, type: 'room.player_vacated' }),
    'room.dm_joined': (data) => handleCampaignUpdate({ ...data, type: 'room.dm_joined' }),
    'room.dm_left': (data) => handleCampaignUpdate({ ...data, type: 'room.dm_left' }),
    // Connection events
    onPlayerConnected: (data) => console.log('🎮 Player connected:', data),
    onPlayerDisconnected: (data) => console.log('🎮 Player disconnected:', data),
    // Collaborative editing events (replacing old collab WebSocket)
    player_list: (data) => {
      if (Array.isArray(data.players)) {
        // Transform backend format (playerId, playerName) to component format (id, name)
        const transformed = data.players.map(p => ({
          id: p.playerId || p.id,
          name: p.playerName || p.name,
          isConnected: p.isConnected,
        }));
        setCollabPlayers(transformed);
      }
    },
    initial_state: (data) => {
      if (Array.isArray(data.allPlayers)) {
        // Transform backend format (playerId, playerName) to component format (id, name)
        const transformed = data.allPlayers.map(p => ({
          id: p.playerId || p.id,
          name: p.playerName || p.name,
          isConnected: p.isConnected,
        }));
        setCollabPlayers(transformed);
      }
    },
    registered: (data) => {
      console.log('[Collab] Player registered via Socket.IO:', data);
      setCollabIsConnected(true);
    },
  }), [handleCampaignUpdate, handleSfxAvailable, sessionId, handleTurnStarted, handleTurnMessage, handleTurnComplete, handleTurnError, handleInputReceived, setStructuredDataBySession]);

  // Use Socket.IO connection
  const {
    socket: sioSocket,
    isConnected: sioIsConnected,
    connectionError: sioConnectionError,
    emit: sioEmit,
    sendAudioPlayed,
  } = useGameSocket({
    campaignId: sessionId,
    getAccessToken: getAccessTokenSilently,
    role: 'player',
    handlers: socketHandlers,
  });

  // Update socketEmitRef so useUserAudioQueue can use it for reliable acknowledgments
  useEffect(() => {
    socketEmitRef.current = sioEmit;
  }, [sioEmit]);

  // Sync Socket.IO connection state to component state
  useEffect(() => {
    setIsConnected(sioIsConnected);
    if (sioConnectionError) {
      setError(sioConnectionError);
    } else if (sioIsConnected) {
      setError(null);
    }
  }, [sioIsConnected, sioConnectionError]);

  // Sync collab connection state with Socket.IO connection
  useEffect(() => {
    setCollabIsConnected(sioIsConnected);
  }, [sioIsConnected]);

  // Set collab player ID from user email and register when connected
  useEffect(() => {
    if (user?.email) {
      const role = 'player';
      const playerId = `${user.email}:${role}`;
      setCollabPlayerId(playerId);
      // Note: Character name from seat is handled in PlayerRoomShell which has access to useRoom()
      // Use "Player" as default - character name will be updated when seat data loads
      // Only set if not already set (preserve character name if already loaded)
      setAssignedPlayerName(prev => prev || 'Player');
    }
  }, [user?.email]);

  // Register with backend when connected (separate effect to handle reconnections properly)
  useEffect(() => {
    if (sioIsConnected && sioSocket && collabPlayerId) {
      // Use current assignedPlayerName (which may be character name or "Player")
      const nameToRegister = assignedPlayerName || 'Player';
      sioSocket.emit('register', { playerId: collabPlayerId, playerName: nameToRegister });
      console.log('[PlayerPage] Registered with backend:', { playerId: collabPlayerId, playerName: nameToRegister });
    }
  }, [sioIsConnected, sioSocket, collabPlayerId, assignedPlayerName]);

  // Create a ref that holds the socket for backward compatibility
  const socketRef = useRef(null);
  useEffect(() => {
    socketRef.current = sioSocket;
    // Also update wsRef for backward compatibility with code that checks wsRef
    wsRef.current = sioSocket ? {
      // Provide WebSocket-like interface
      readyState: sioSocket.connected ? 1 : 3, // OPEN = 1, CLOSED = 3
      send: (data) => {
        try {
          const parsed = JSON.parse(data);
          sioEmit(parsed.type || 'message', parsed);
        } catch (e) {
          console.warn('Failed to parse message for Socket.IO:', e);
        }
      },
      close: () => sioSocket?.disconnect(),
      __sessionId: sessionId,
    } : null;
  }, [sioSocket, sessionId, sioEmit]);

  // Fetch audio queue when connected
  useEffect(() => {
    if (sioIsConnected && sessionId) {
      fetchUserAudioQueue(sessionId);
    }
  }, [sioIsConnected, sessionId, fetchUserAudioQueue]);

  // Legacy waitForSocketClose - kept for any remaining references
  const waitForSocketClose = useCallback((socket, timeoutMs = 1000) => {
    // Socket.IO handles disconnection automatically
    if (!socket) {
      return Promise.resolve();
    }
    // For Socket.IO sockets
    if (socket.disconnect) {
      socket.disconnect();
      return Promise.resolve();
    }
    // For raw WebSockets (legacy)
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

  // WebSocket connection management - now handled by useGameSocket
  // This function is kept for backward compatibility with error handlers
  // that may call connectWebSocket({ forceReconnect: true })
  const connectWebSocket = useCallback(async (options = {}) => {
    // Socket.IO handles all connection management automatically via useGameSocket
    // This is a no-op stub for backward compatibility
    console.log('[Socket.IO] connectWebSocket called - Socket.IO handles connection automatically');
  }, []);

  // Socket.IO handles connection automatically via useGameSocket hook
  // The useEffect below is a legacy placeholder for cleanup

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (historyRefreshTimerRef.current) {
        clearTimeout(historyRefreshTimerRef.current);
        historyRefreshTimerRef.current = null;
      }
    };
  }, []);

  // Audio stream completed event handler - uses Socket.IO
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
      // Use Socket.IO to send audio_played acknowledgment
      if (!sioIsConnected) {
        console.warn('[PLAYER][AUDIO_STREAM] Cannot send audio_played ack - socket not connected');
        return;
      }
      // Send via Socket.IO emit
      sioEmit('audio_played', {
        campaign_id: detail.sessionId || currentCampaignId,
        chunk_ids: chunkIds,
      });
      console.log('[PLAYER][AUDIO_STREAM] Sent audio_played ack | chunks=%s',
        chunkIds.length);
    };

    window.addEventListener(AUDIO_STREAM_COMPLETED_EVENT, handleStreamComplete);
    return () => {
      window.removeEventListener(AUDIO_STREAM_COMPLETED_EVENT, handleStreamComplete);
    };
  }, [currentCampaignId, sioIsConnected, sioEmit]);

  // Handle player actions - notifies DM via Socket.IO (doesn't send to backend directly)
  // The DM sees player submissions and can incorporate them into their own submission
  const handlePlayerAction = useCallback((action) => {
    if (!currentCampaignId) {
      setError('No campaign selected');
      return;
    }

    // Extract message from action
    const message = action?.message || action?.text || (typeof action === 'string' ? action : null);
    if (!message) {
      console.warn('🎯 handlePlayerAction: No message in action', action);
      return;
    }

    if (!sioIsConnected || !sioSocket) {
      console.warn('🎯 Cannot submit player action - socket not connected');
      return;
    }

    // Get character info for the submission
    // Note: currentUserPlayerSeat is only available in PlayerRoomShell, so we use collabPlayerId/assignedPlayerName here
    const characterId = collabPlayerId || 'unknown';
    const characterName = assignedPlayerName || 'Player';

    console.log('🎯 Player submitted action (notifying DM):', { characterName, message });

    // Send player submission to DM via Socket.IO
    // The DM will see a popup with the player's input and can copy it
    sioEmit('player_action_submitted', {
      character_id: characterId,
      character_name: characterName,
      action_text: message.trim()
    });

    console.log('🎯 Player action sent to DM via Socket.IO');
  }, [currentCampaignId, setError, sioIsConnected, sioSocket, sioEmit, collabPlayerId, assignedPlayerName]);

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
        turns={turns}
        isProcessing={isProcessing}
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
        setAudioPermissionState={setAudioPermissionState}
        userEmail={userEmail}
        sioIsConnected={sioIsConnected}
        sioEmit={sioEmit}
        sioSocket={sioSocket}
        collabIsConnected={collabIsConnected}
        setCollabIsConnected={setCollabIsConnected}
        collabPlayers={collabPlayers}
        setCollabPlayers={setCollabPlayers}
        collabPlayerId={collabPlayerId}
        setCollabPlayerId={setCollabPlayerId}
        assignedPlayerName={assignedPlayerName}
        setAssignedPlayerName={setAssignedPlayerName}
        // Audio unlock props (for iOS mobile support)
        audioBlocked={audioBlocked}
        unlockAudio={unlockAudio}
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
  turns,
  isProcessing,
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
  setAudioPermissionState,
  userEmail,
  sioIsConnected,
  sioEmit,
  sioSocket,
  // Collaborative editing state (managed in parent PlayerPage)
  collabIsConnected,
  setCollabIsConnected,
  collabPlayers,
  setCollabPlayers,
  collabPlayerId,
  setCollabPlayerId,
  assignedPlayerName,
  setAssignedPlayerName,
  // Audio unlock props (for iOS mobile support)
  audioBlocked,
  unlockAudio,
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

  // Update assignedPlayerName from seat's character_name
  // Note: Re-registration with backend is handled automatically by the effect in PlayerPage
  // that watches assignedPlayerName changes
  useEffect(() => {
    const characterName = currentUserPlayerSeat?.character_name;
    if (characterName && characterName !== assignedPlayerName) {
      console.log('[PlayerRoomShell] Updating player name from seat character:', characterName);
      setAssignedPlayerName(characterName);
    }
  }, [currentUserPlayerSeat?.character_name, assignedPlayerName, setAssignedPlayerName]);

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

  // Voice transcription handler - sends text to backend via Socket.IO
  // Backend uses player_id from the connection to update the correct section
  const handleVoiceTranscription = useCallback((transcribedText, metadata) => {
    console.log('🎤 Voice transcription received:', transcribedText, metadata);

    // Ignore any transcription events if the mic toggle is off
    if (!isTranscribingRef.current) {
      console.warn('🎤 Ignoring transcription because mic is not active');
      return;
    }

    if (!sioIsConnected) {
      console.warn('🎤 Socket.IO not connected, voice text not sent');
      return;
    }

    // Send voice transcription to backend - it will update the Y.js doc
    // using the player_id associated with this connection
    sioEmit('voice_transcription', {
      text: transcribedText,
      is_partial: metadata?.is_partial ?? false
    });

    console.log('🎤 Sent voice_transcription via Socket.IO, is_partial:', metadata?.is_partial);
  }, [sioIsConnected, sioEmit]);

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
      if (sioIsConnected) {
        sioEmit('voice_session_start', {});
        console.log('🎤 Sent voice_session_start via Socket.IO');
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
  }, [isTranscribing, audioPermissionState, sioIsConnected, sioEmit]);

  // Collaborative editing is now handled via Socket.IO (useGameSocket hook)
  // See handlers: player_list, initial_state, registered in socketHandlers

  // Handle observation submission from secondary players
  const handleSubmitObservation = useCallback((observationText) => {
    if (!sioIsConnected || !sioSocket) {
      console.warn('👁️ Cannot submit observation - socket not connected');
      return;
    }

    const characterId = currentUserPlayerSeat?.character_id || collabPlayerId;
    const characterName = currentUserPlayerSeat?.character_name || assignedPlayerName;

    console.log('👁️ Submitting observation:', { characterId, characterName, observationText });

    sioEmit('submit_observation', {
      character_id: characterId,
      character_name: characterName,
      observation_text: observationText
    });

    console.log('👁️ Observation submitted via Socket.IO');
  }, [sioIsConnected, sioSocket, sioEmit, currentUserPlayerSeat, collabPlayerId, assignedPlayerName]);

  // Handle copying an observation to the chat input
  const handleCopyObservation = useCallback((observation) => {
    if (collabEditorRef?.current?.insertText) {
      const formattedObservation = `[${observation.character_name} observes]: ${observation.observation_text}`;
      collabEditorRef.current.insertText(formattedObservation);
    }
  }, [collabEditorRef]);

  // Determine if current player is the active (turn-taking) player
  const { currentCharacterId, isActivePlayer, pendingObservations } = useMemo(() => {
    // Use the player's own character_id from their seat - DO NOT fall back to active_character_id
    // Each player should only see their own personalized options
    const charId = currentUserPlayerSeat?.character_id || null;
    const personalizedOptions = latestStructuredData?.personalized_player_options;
    const pending = latestStructuredData?.pending_observations?.observations || [];
    const characters = personalizedOptions?.characters || {};
    const activeCharacterId = personalizedOptions?.active_character_id || null;

    // Debug: Log what we're computing
    console.log('👁️ PlayerPage useMemo computing:', {
      charId,
      pendingObsRaw: latestStructuredData?.pending_observations,
      pendingCount: pending?.length,
      hasPersonalizedOptions: !!personalizedOptions,
      activeCharacterId,
      charactersKeys: Object.keys(characters)
    });

    // If we have the player's character_id, look up their personalized options
    if (personalizedOptions && charId) {
      const charOptions = characters?.[charId];
      return {
        currentCharacterId: charId,
        isActivePlayer: charOptions?.is_active ?? charId === activeCharacterId,
        pendingObservations: pending
      };
    }

    // No character_id available - player hasn't been assigned a character yet
    // Don't show as active player if we can't determine their character
    return {
      currentCharacterId: charId,
      isActivePlayer: false,
      pendingObservations: pending
    };
  }, [currentUserPlayerSeat?.character_id, latestStructuredData]);

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
              turns={turns}
              imageRefreshTrigger={imageRefreshTriggersBySession[currentCampaignId]}
              onPlayerAction={handlePlayerAction}
              onLoadCampaignData={loadCampaignData}
              streamingNarrative={streamingNarrativeBySession[currentCampaignId] || ''}
              streamingResponse={streamingResponseBySession[currentCampaignId] || ''}
              isNarrativeStreaming={isNarrativeStreamingBySession[currentCampaignId] || false}
              isResponseStreaming={isResponseStreamingBySession[currentCampaignId] || false}
              // Event-driven processing indicator (set by turn_started socket event)
              isProcessing={isProcessing}
              // Collaborative editing props (now via Socket.IO)
              collabWebSocket={sioSocket}
              collabPlayerId={collabPlayerId}
              collabPlayerName={assignedPlayerName}
              collabAllPlayers={collabPlayers}
              collabIsConnected={collabIsConnected}
              // Voice input props
              audioPermissionState={audioPermissionState}
              userEmail={userEmail}
              isTranscribing={isTranscribing}
              onToggleTranscription={toggleVoiceTranscription}
              voiceActivityLevel={voiceActivityLevel}
              collabEditorRef={collabEditorRef}
              // Personalized player options props
              currentCharacterId={currentCharacterId}
              isActivePlayer={isActivePlayer}
              pendingObservations={pendingObservations}
              onCopyObservation={handleCopyObservation}
              onSubmitObservation={handleSubmitObservation}
              // Audio unlock props (for iOS mobile support)
              userAudioBlocked={audioBlocked}
              onUnlockUserAudio={unlockAudio}
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

// Wrap PlayerPage with AudioStreamProvider and SFXProvider to enable synchronized audio streaming and sound effects
function PlayerPageWithAudioStream() {
  return (
    <AudioStreamProvider>
      <SFXProvider>
        <PlayerPage />
      </SFXProvider>
    </AudioStreamProvider>
  );
}

export default PlayerPageWithAudioStream;
