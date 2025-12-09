import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from './contexts/Auth0Context.jsx';
import SharedHeaderLayout from './components/layout/SharedHeaderLayout.jsx';
import LobbyButton from './components/layout/LobbyButton.jsx';
import CampaignNameDisplay from './components/layout/CampaignNameDisplay.jsx';
import { UserMenu } from './AppWithAuth0.jsx';
import GameDashboard from './components/GameDashboard.jsx';
import AudioPlayerBar from './components/audio/AudioPlayerBar.jsx';
import ControlPanel from "./components/ControlPanel.jsx";
import CampaignManager from './components/CampaignManager.jsx';
import CampaignSetup from "./components/CampaignSetup.jsx";
// CharacterManagement removed - will be added in followup
import ContextInput from './components/ContextInput.jsx';
import VoiceInputScribeV2 from './components/VoiceInputScribeV2.jsx';
import VoiceActivityIndicator from "./components/VoiceActivityIndicator.jsx";
import ImagePopup from "./components/ImagePopup.jsx";
import KeyboardShortcutsHelp from "./components/KeyboardShortcutsHelp.jsx";
import SettingsButton from './components/SettingsButton.jsx';
import SettingsModal from './components/SettingsModal.jsx';
import ConnectedPlayers from './components/ConnectedPlayers.jsx';
import { LoadingProvider } from './contexts/LoadingContext.jsx';
import { RoomProvider } from './contexts/RoomContext.jsx';
import UnifiedLoadingIndicator from './components/UnifiedLoadingIndicator.jsx';
import { API_CONFIG } from './config/api.js';
// Import API service
import apiService from "./services/apiService.js"; // OpenAPI service
import { AudioStreamProvider, useAudioStream, AUDIO_STREAM_COMPLETED_EVENT } from './context/audioStreamContext.jsx';
import { SFXProvider, useSFX } from './context/sfxContext.jsx';
import { Modal } from './components/base-ui/Modal.jsx';
import { Button } from './components/base-ui/Button.jsx';
import { Input } from './components/base-ui/Input.jsx';
import { Alert } from './components/base-ui/Alert.jsx';
// Import custom hooks
import { useCampaignMessages } from './hooks/useCampaignMessages.js';
import { useStreamingState } from './hooks/useStreamingState.js';
import { useGameSocket } from './hooks/useGameSocket.js';
import { useCampaignState } from './hooks/useCampaignState.js';
import { useImageManagement } from './hooks/useImageManagement.js';
import { useCampaignOperations } from './hooks/useCampaignOperations.js';
import { useShareInvite } from './hooks/useShareInvite.js';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts.js';
import { useGlobalErrorHandler } from './hooks/useGlobalErrorHandler.js';
import { useUserAudioQueue, handleAudioPlayedConfirmation } from './hooks/useUserAudioQueue.js';

const CAMPAIGN_START_TRACE = '[CAMPAIGN_START_FLOW]';

const logCampaignStartTrace = (message, details) => {
  if (typeof details !== 'undefined') {
    console.log(`${CAMPAIGN_START_TRACE} ${message}`, details);
  } else {
    console.log(`${CAMPAIGN_START_TRACE} ${message}`);
  }
};

// Simple UUID generator for message correlation
function generateMessageId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
}

// Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("🚨 React Error Boundary caught an error:", error, errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-5 text-gaia-error bg-red-50 border-2 border-gaia-error m-5 rounded-lg">
          <h2 className="text-xl font-bold mb-3">🚨 Something went wrong!</h2>
          <details className="whitespace-pre-wrap">
            <summary className="cursor-pointer hover:text-red-700">Error Details</summary>
            <p className="mt-2"><strong>Error:</strong> {this.state.error && this.state.error.toString()}</p>
            <p><strong>Stack:</strong> {this.state.error && this.state.error.stack}</p>
            <p><strong>Component Stack:</strong> {this.state.errorInfo && this.state.errorInfo.componentStack}</p>
          </details>
          <button 
            onClick={() => window.location.reload()} 
            className="mt-4 px-4 py-2 bg-gaia-error text-white rounded-md hover:bg-red-600 transition-colors"
          >
            🔄 Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

function App() {
  const { sessionId } = useParams(); // Get session ID from URL
  const { user, handleAuthError, getAccessTokenSilently, refreshAccessToken } = useAuth();

  // Synchronized audio streaming
  const audioStream = useAudioStream();

  // Sound effects (separate audio element at 50% volume for simultaneous playback)
  const sfx = useSFX();

  const currentUserProfile = useMemo(() => {
    if (!user) return null;
    return {
      name: user.full_name || user.username || user.display_name || user.email || null,
      email: user.email || null,
    };
  }, [user]);

  // Campaign state
  // Campaign ID loaded from URL params via useEffect (see line ~849)
  const [currentCampaignId, setCurrentCampaignId] = useState(null);
  const [campaignName, setCampaignName] = useState('');

  // Basic state declarations (must be before hooks that use them)
  const [isLoading, setIsLoading] = useState(false);
  const [inputMessage, setInputMessage] = useState("");
  const [error, setError] = useState(null);
  const [showCampaignList, setShowCampaignList] = useState(false);
  const [appError, setAppError] = useState(null);
  const [showContextInput, setShowContextInput] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [audioPermissionState, setAudioPermissionState] = useState('pending');
  const [voiceActivityLevel, setVoiceActivityLevel] = useState(0);
  const [isTTSPlaying, setIsTTSPlaying] = useState(false);
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState(''); // Will be set dynamically by ControlPanel
  const [selectedProvider, setSelectedProvider] = useState(''); // Will be set dynamically by TTSProviderSelector
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [infoBanner, setInfoBanner] = useState(null);
  const [audioQueueStatus, setAudioQueueStatus] = useState(null);
  const [isClearingAudioQueue, setIsClearingAudioQueue] = useState(false);
  const [playbackQueueInfo, setPlaybackQueueInfo] = useState(null);

  // Player action submissions (shown in DM's player options section)
  const [playerSubmissions, setPlayerSubmissions] = useState([]);

  // Collaborative editing state (now managed via Socket.IO)
  const [collabIsConnected, setCollabIsConnected] = useState(false);
  const [collabPlayers, setCollabPlayers] = useState([]);
  const [collabPlayerName, setCollabPlayerName] = useState('DM');
  const [collabPlayerId, setCollabPlayerId] = useState('');

  // Refs (must be before hooks that use them)
  const controlPanelRef = useRef(null);
  const transcriptionRef = useRef(null);
  const isTranscribingRef = useRef(false);

  const resolvedCampaignIdForSocket = currentCampaignId || sessionId || null;

  // Streaming state management via custom hooks
  const {
    streamingNarrative: dmStreamingNarrative,
    streamingResponse: dmStreamingResponse,
    isNarrativeStreaming: dmIsNarrativeStreaming,
    isResponseStreaming: dmIsResponseStreaming,
    isNarrativeStreamingRef: dmIsNarrativeStreamingRef,
    isResponseStreamingRef: dmIsResponseStreamingRef,
    updateStreamingNarrative,
    updateStreamingResponse,
    handleDebugStreamPreview,
    clearStreaming,
  } = useStreamingState(currentCampaignId);

  // Message state management via custom hooks (needs streaming state for clearing after reload)
  const {
    messages,
    messagesRef: messagesBySessionRef,
    setMessages: setSessionMessages,
    markLastDmMessageHasAudio,
    addUserMessage,
    addContextMessage,
    addDMMessage,
    addSystemError,
    reloadHistoryAfterStream,
  } = useCampaignMessages(currentCampaignId, {
    clearNarrativeStreaming: clearStreaming,
    clearResponseStreaming: clearStreaming,
  });

  // Campaign state management via custom hook
  const {
    structuredData: latestStructuredData,
    historyInfo,
    needsResume,
    pendingInitialNarrative: isInitialNarrativePending,
    allStructuredData: structuredDataBySession,
    allHistoryInfo: historyInfoBySession,
    allNeedsResume: needsResumeBySession,
    allPendingInitialNarrative: pendingInitialNarrativeBySession,
    setStructuredData: setSessionStructuredData,
    setHistoryInfo: setSessionHistoryInfo,
    setNeedsResume: setSessionNeedsResume,
    setPendingInitialNarrative,
    transformStructuredData,
  } = useCampaignState(currentCampaignId);

  // Image management via custom hook
  const {
    images: generatedImages,
    showPopup: showImagePopup,
    currentPopupImage,
    handleNewImage,
    handleImageClick,
    closePopup: handleImagePopupClose,
    loadRecent: loadRecentImages,
  } = useImageManagement(currentCampaignId);

  // Campaign operations via custom hook
  const {
    selectCampaign: handleSelectCampaign,
    createBlankCampaign: resetApp,
    startArenaQuickStart: handleArenaQuickStart,
    joinSharedSession,
  } = useCampaignOperations({
    currentCampaignId,
    setCurrentCampaignId,
    setPendingInitialNarrative,
    setSessionNeedsResume,
    setSessionMessages,
    setSessionStructuredData,
    setSessionHistoryInfo,
    setIsLoading,
    setError,
    setShowCampaignList,
    transformStructuredData,
    loadRecentImages,
    markLastDmMessageHasAudio,
    handleNewImage,
    updateStreamingNarrative,
    updateStreamingResponse,
    clearStreaming,
    setCampaignName,
  });

  const refreshActiveCampaignState = useCallback(async () => {
    if (!currentCampaignId) return;
    logCampaignStartTrace('refreshActiveCampaignState invoked', {
      campaignId: currentCampaignId,
    });
    try {
      setPendingInitialNarrative(currentCampaignId, true);
      setIsLoading(true);
      logCampaignStartTrace('Calling loadSimpleCampaign after room.campaign_started', {
        campaignId: currentCampaignId,
      });
      const data = await apiService.loadSimpleCampaign(currentCampaignId);
      logCampaignStartTrace('loadSimpleCampaign result', {
        campaignId: currentCampaignId,
        hasStructuredData: Boolean(data?.structured_data),
        hasHistoryInfo: Boolean(data?.history_info),
      });
      if (data?.structured_data) {
        const transformed = transformStructuredData(data.structured_data, {
          needsResponse: Boolean(data.needs_response),
          sessionId: currentCampaignId,
        });
        if (transformed) {
          logCampaignStartTrace('Applying structured data from refreshActiveCampaignState', {
            campaignId: currentCampaignId,
            keys: Object.keys(transformed),
          });
          setSessionStructuredData(currentCampaignId, transformed);
        }
      }
      if (data?.history_info) {
        setSessionHistoryInfo(currentCampaignId, data.history_info);
        setTimeout(() => setSessionHistoryInfo(currentCampaignId, null), 10000);
      }
    } catch (err) {
      console.error('Failed to refresh campaign after start:', err);
      logCampaignStartTrace('refreshActiveCampaignState failed', {
        campaignId: currentCampaignId,
        error: err?.message,
      });
    } finally {
      setPendingInitialNarrative(currentCampaignId, false);
      setIsLoading(false);
      logCampaignStartTrace('refreshActiveCampaignState complete', {
        campaignId: currentCampaignId,
      });
    }
  }, [
    currentCampaignId,
    setPendingInitialNarrative,
    setIsLoading,
    transformStructuredData,
    setSessionStructuredData,
    setSessionHistoryInfo,
  ]);

  const handleRoomEvent = useCallback(
    (event) => {
      if (!event || event.type !== 'campaign_started') return;
      const eventCampaignId = event.data?.campaign_id;
      logCampaignStartTrace('handleRoomEvent received campaign_started', {
        eventCampaignId,
        currentCampaignId,
      });
      if (!currentCampaignId || eventCampaignId !== currentCampaignId) {
        logCampaignStartTrace('Ignoring campaign_started event for mismatched session', {
          eventCampaignId,
          currentCampaignId,
        });
        return;
      }
      logCampaignStartTrace('Triggering refreshActiveCampaignState after campaign_started', {
        campaignId: currentCampaignId,
      });
      refreshActiveCampaignState();
    },
    [currentCampaignId, refreshActiveCampaignState],
  );

  // Share and invite management
  const {
    showModal: showShareModal,
    setShowModal: setShowShareModal,
    shareState,
    fetchToken: fetchInviteToken,
    copyInviteLink: handleCopyInviteLink,
    inviteLink,
  } = useShareInvite(currentCampaignId, setInfoBanner);

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    controlPanelRef,
    transcriptionRef,
  });

  // Global error handling
  useGlobalErrorHandler(setAppError);

  // Expose token getter for debugging (dev only)
  useEffect(() => {
    if (typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
      window.getAuthToken = async () => {
        try {
          const token = await getAccessTokenSilently();
          console.log('🔑 Auth Token:', token);
          return token;
        } catch (error) {
          console.error('Failed to get token:', error);
          return null;
        }
      };
    }
  }, [getAccessTokenSilently]);

  // Derived state
  const isChatProcessing = isLoading || isInitialNarrativePending;

  // Check if audio is currently streaming
  const hasPendingAudio = audioStream.isStreaming || (audioStream.pendingChunkCount > 0);

  // Ref for pending initial narrative (used in callbacks)
  const pendingInitialNarrativeRef = useRef(pendingInitialNarrativeBySession);
  useEffect(() => {
    pendingInitialNarrativeRef.current = pendingInitialNarrativeBySession;
  }, [pendingInitialNarrativeBySession]);

  // Old campaign state functions removed - now handled by useCampaignState hook

  // Set up Auth0 access token provider for apiService
  useEffect(() => {
    console.log('🔐 App.jsx: Setting up Auth0 access token provider');
    console.log('🔐 getAccessTokenSilently function available:', !!getAccessTokenSilently);
    // Pass a wrapper that always uses the current Auth0 context
    apiService.setTokenProvider(async () => {
      if (typeof getAccessTokenSilently !== 'function') {
        return null;
      }
      const authErrorLog = (label, error) => {
        console.warn(`🔐 Token wrapper: ${label}`, error);
      };
      try {
        console.log('🔐 Token wrapper: Fetching token from current Auth0 context');
        const token = await getAccessTokenSilently();
        if (token) {
          return token;
        }
      } catch (error) {
        authErrorLog('Primary token fetch failed', error);
      }

      // Fallback: explicitly request token with audience/scope if configured
      const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
      const scope = import.meta.env.VITE_AUTH0_SCOPE || 'openid profile email offline_access';
      if (audience) {
        try {
          console.log('🔐 Token wrapper: Fetching token with audience fallback');
          const token = await getAccessTokenSilently({
            authorizationParams: {
              audience,
              scope,
            },
          });
          if (token) {
            return token;
          }
        } catch (error) {
          authErrorLog('Audience fallback token fetch failed', error);
        }
      }
      return null;
    });
  }, [getAccessTokenSilently]);

  // Auto-resize textarea as content grows
  useEffect(() => {
    if (chatInputRef.current) {
      chatInputRef.current.style.height = 'auto';
      chatInputRef.current.style.height = `${chatInputRef.current.scrollHeight}px`;
    }
  }, [inputMessage]);

  // Set up auth error handler for automatic logout on token expiration
  useEffect(() => {
    console.log('🔐 App.jsx: Setting up auth error callback');
    apiService.setAuthErrorCallback(handleAuthError);
  }, [handleAuthError]);
  
  useEffect(() => {
    if (!infoBanner) {
      return undefined;
    }
    const timer = setTimeout(() => setInfoBanner(null), 8000);
    return () => clearTimeout(timer);
  }, [infoBanner]);

  // Collaborative editing is now handled via Socket.IO (useGameSocket hook)
  // See handlers: player_list, initial_state, registered in useGameSocket config
  // NOTE: Voice transcription callbacks are defined AFTER useGameSocket hook below

  // Auto-enable audio on first user interaction (browser autoplay policy)
  useEffect(() => {
    if (!audioStream.needsUserGesture) {
      return undefined;
    }

    const handleUserInteraction = () => {
      try {
        audioStream.resumePlayback();
      } catch (_) {
        // no-op
      }
    };

    // Listen once for any user interaction to resume audio
    document.addEventListener('click', handleUserInteraction, { once: true });
    document.addEventListener('keydown', handleUserInteraction, { once: true });
    document.addEventListener('touchstart', handleUserInteraction, { once: true });

    return () => {
      document.removeEventListener('click', handleUserInteraction);
      document.removeEventListener('keydown', handleUserInteraction);
      document.removeEventListener('touchstart', handleUserInteraction);
    };
  }, [audioStream]);
  
  // Choose the service based on feature flag
  const messageService = apiService; // Always use OpenAPI now
  
  // Log which service is being used
  useEffect(() => {
    console.log(`📡 Using ${API_CONFIG.USE_OPENAPI ? 'OpenAPI/JSON' : 'Protobuf'} service for communication`);
  }, []);

  const [showCampaignSetup, setShowCampaignSetup] = useState(false);
  // Character management removed - will be added in followup
  const [voiceRecordingState, setVoiceRecordingState] = useState({ isRecording: false, sessionId: null });
  const [voiceActivityActive, setVoiceActivityActive] = useState(null); // null = unknown, boolean when known
  const chatEndRef = useRef(null);
  const chatInputRef = useRef(null);
  const gameDashboardRef = useRef(null);

  // Store function reference for loading campaign
  // const _loadCampaignRef = useRef(null);

  // Save campaign ID whenever it changes
  useEffect(() => {
    if (currentCampaignId) {
      localStorage.setItem('lastCampaignId', currentCampaignId);
      console.log('💾 Saved campaign ID to localStorage:', currentCampaignId);
      
      // Update page title with campaign name
      if (campaignName) {
        document.title = `${campaignName} - Gaia D&D`;
      } else {
        document.title = `Campaign: ${currentCampaignId} - Gaia D&D`;
      }
    } else {
      document.title = 'Gaia D&D Campaign Manager';
    }
  }, [currentCampaignId, campaignName]);

  useEffect(() => {
    setVoiceRecordingState((prev) => ({
      ...prev,
      sessionId: currentCampaignId || null,
    }));
  }, [currentCampaignId]);

  useEffect(() => {
    isTranscribingRef.current = isTranscribing;
    setVoiceRecordingState((prev) => ({
      ...prev,
      isRecording: isTranscribing,
    }));
  }, [isTranscribing]);

  useEffect(() => {
    const storedPermission = localStorage.getItem('audioPermissionState');
    if (storedPermission === 'granted' || storedPermission === 'denied') {
      setAudioPermissionState(storedPermission);
    }
  }, []);

  // Old image handling functions removed - now handled by useImageManagement hook

  // Handle copying player suggestion to chat input

  // Old loadRecentImages function removed - now handled by useImageManagement hook

  const getActiveCharacterNameForSession = useCallback(
    (sessionId) => {
      if (!sessionId) {
        return null;
      }

      const data =
        structuredDataBySession?.[sessionId] ||
        (sessionId === currentCampaignId ? latestStructuredData : null);

      if (!data) {
        return null;
      }

      const turnInfo = data.turn_info || data.turnInfo || null;
      if (turnInfo) {
        return (
          turnInfo.character_name ||
          turnInfo.characterName ||
          turnInfo.character_id ||
          null
        );
      }

      return null;
    },
    [structuredDataBySession, currentCampaignId, latestStructuredData],
  );

  // WebSocket message handlers

  // Old queue-based handlers removed - using synchronized streaming instead

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

  // On iOS, try to unlock audio on any user interaction with the page
  useEffect(() => {
    const handleUserInteraction = () => {
      if (audioBlocked) {
        console.log('🎵 [DM] User interaction detected, attempting to unlock audio');
        unlockAudio();
      }
    };

    // Add listeners for common user interactions
    document.addEventListener('touchstart', handleUserInteraction, { passive: true });
    document.addEventListener('click', handleUserInteraction, { passive: true });

    return () => {
      document.removeEventListener('touchstart', handleUserInteraction);
      document.removeEventListener('click', handleUserInteraction);
    };
  }, [audioBlocked, unlockAudio]);

  // Handle audio_available notifications (user queue playback)
  const handleAudioAvailable = useCallback((data, sessionId) => {
    const { campaign_id } = data;
    const targetSessionId = campaign_id || sessionId;

    if (!targetSessionId) {
      console.warn('🎵 [DM] audio_available missing campaign_id');
      return;
    }

    console.log('🎵 [DM] Audio available, fetching user queue for campaign:', targetSessionId);
    fetchUserAudioQueue(targetSessionId);
  }, [fetchUserAudioQueue]);

  // Handle synchronized audio stream start - no-op since audio_available handles queue
  const handleAudioStreamStarted = useCallback((data, sessionId) => {
    const { campaign_id } = data;
    const targetSessionId = campaign_id || sessionId;

    // NOTE: Don't call fetchUserAudioQueue here - audio_available already handles it
    // This event is now just logged for debugging purposes
    console.log('[AUDIO_DEBUG] 📥 Frontend received audio_stream_started | session=%s (no-op, audio_available handles queue)',
      targetSessionId);
  }, []);

  // Handle synchronized audio stream stop
  const handleAudioStreamStopped = useCallback((data, sessionId) => {
    console.log('🎵 [AUDIO STREAM] Received audio_stream_stopped:', data);

    const { campaign_id } = data;
    const targetSessionId = campaign_id || sessionId;

    if (!targetSessionId) {
      console.warn('[AUDIO STREAM] Missing campaign_id for stream stop');
      return;
    }

    console.log(`[AUDIO STREAM] Stopping stream for session ${targetSessionId}`);
    audioStream.stopStream();
  }, [audioStream]);

  const handleAudioQueueCleared = useCallback((data) => {
    setIsClearingAudioQueue(false);
    setAudioQueueStatus({
      clearedCount: data.cleared_count ?? 0,
      pendingAfter: data.pending_after ?? 0,
      timestamp: data.timestamp || new Date().toISOString(),
      error: null,
      pending: false,
    });
    if (audioStream?.clearPendingChunks) {
      audioStream.clearPendingChunks();
    }
  }, [audioStream]);

  const handlePlaybackQueueUpdated = useCallback((data) => {
    console.log('[AUDIO_DEBUG] 📊 Playback queue updated:', {
      pendingCount: data.pending_count,
      currentRequest: data.current_request,
      campaignId: data.campaign_id,
    });
    setPlaybackQueueInfo({
      pendingCount: data.pending_count ?? 0,
      currentRequest: data.current_request ?? null,
      pendingRequests: data.pending_requests ?? [],
      timestamp: new Date().toISOString(),
    });
  }, []);

  const handleNarrativeChunk = useCallback((data, sessionId) => {
    const campaignSessionId = data.campaign_id || sessionId;
    if (!campaignSessionId) return;

    const content = data.content || '';
    logCampaignStartTrace('narrative_chunk received', {
      sessionId: campaignSessionId,
      length: content.length,
      isFinal: data.is_final,
    });
    // updateStreamingNarrative auto-detects whether to append based on current state
    updateStreamingNarrative(campaignSessionId, content, {
      isStreaming: !data.is_final,
      isFinal: data.is_final,
    });
  }, [updateStreamingNarrative]);

  const handleResponseChunk = useCallback((data, sessionId) => {
    const campaignSessionId = data.campaign_id || sessionId;
    if (!campaignSessionId) return;

    const content = data.content || '';
    logCampaignStartTrace('response_chunk received', {
      sessionId: campaignSessionId,
      length: content.length,
      isFinal: data.is_final,
    });
    // updateStreamingResponse auto-detects whether to append based on current state
    updateStreamingResponse(campaignSessionId, content, {
      isStreaming: !data.is_final,
      isFinal: data.is_final,
    });
  }, [updateStreamingResponse]);

  const handleMetadataUpdate = useCallback((metadata, sessionId, campaignId) => {
    const targetSessionId = campaignId || sessionId;
    if (targetSessionId) {
      setSessionStructuredData(targetSessionId, (prev) => ({
        ...(prev || {}),
        ...metadata,
      }));
    }
  }, [setSessionStructuredData]);

  const handleInitializationError = useCallback((data, sessionId, currentCampaign) => {
    const targetSessionId = data.campaign_id || sessionId;
    setPendingInitialNarrative(targetSessionId, false);
    if (targetSessionId === currentCampaign) {
      setIsLoading(false);
      setError(data.error || 'Failed to initialize campaign.');
    }
  }, [setPendingInitialNarrative, setIsLoading, setError]);

  const handleCampaignUpdate = useCallback((data, sessionIdForSocket) => {
    const sessionId = data.campaign_id || data.session_id || sessionIdForSocket;
    const structured = data.structured_data;
    if (!sessionId || !structured) {
      logCampaignStartTrace('handleCampaignUpdate missing structured data', {
        sessionId,
        eventType: data.type,
        hasStructuredData: Boolean(structured),
      });
      setPendingInitialNarrative(sessionId, false);
      return;
    }
    logCampaignStartTrace('handleCampaignUpdate invoked', {
      sessionId,
      eventType: data.type,
      hasStructuredData: Boolean(structured),
    });

    const needsResponseFlag = Boolean(
      data.needs_response ??
        structured.input_needed ??
        structured.needs_response ??
        false
    );
    const transformed = transformStructuredData(structured, {
      needsResponse: needsResponseFlag,
      sessionId,
    });

    if (transformed) {
      setSessionStructuredData(sessionId, transformed);
      logCampaignStartTrace('Structured data applied via handleCampaignUpdate', {
        sessionId,
        hasNarrative: Boolean(transformed?.narrative || transformed?.answer),
      });
      // Don't clear streaming state yet - keep visible until history reloads
      if (
        transformed.generated_image_url ||
        transformed.generated_image_path
      ) {
        handleNewImage(transformed);
      }
      const narrativeText = (transformed.narrative || '').trim();
      if (narrativeText && typeof updateStreamingNarrative === 'function') {
        updateStreamingNarrative(sessionId, narrativeText, {
          append: false,
          isStreaming: false,
          isFinal: true,
        });
      }
      const playerResponseText = (transformed.player_response || '').trim();
      const fallbackAnswerText = (transformed.answer || '').trim();
      const responseText = playerResponseText || (!narrativeText && fallbackAnswerText ? fallbackAnswerText : '');
      if (responseText && typeof updateStreamingResponse === 'function') {
        updateStreamingResponse(sessionId, responseText, {
          append: false,
          isStreaming: false,
          isFinal: true,
        });
      }
    }

    if (data.history_info) {
      setSessionHistoryInfo(sessionId, data.history_info);
      setTimeout(() => setSessionHistoryInfo(sessionId, null), 10000);
    }

    // If this was a streamed response, add the streamed content to history, then clear streaming state.
    // Don't reload from backend - we have the content right here in transformed data.
    const wasStreamed = Boolean(transformed?.streamed || structured?.streamed);
    if (wasStreamed) {
      // Get the final streamed content to add to history
      const dmMessageText = transformed?.narrative || transformed?.answer || '';
      if (dmMessageText.trim()) {
        logCampaignStartTrace('Adding streamed message to history', { sessionId, textLength: dmMessageText.length });
        addDMMessage(sessionId, dmMessageText.trim(), {
          hasAudio: Boolean(transformed?.audio),
          structuredContent: transformed || null,
          isStreamed: true,
        });
      }
      // Now clear the streaming display
      clearStreaming(sessionId);
    }

    const existingMessages =
      messagesBySessionRef.current?.[sessionId] ?? [];
    const hadDmMessageAlready = existingMessages.some(
      (msg) => msg.sender === 'dm'
    );
    const isPendingInitial =
      pendingInitialNarrativeRef.current?.[sessionId] ?? false;
    const dmAnswer = transformed?.answer || transformed?.narrative;
    const shouldShowResume =
      needsResponseFlag &&
      (!isPendingInitial || Boolean(dmAnswer) || hadDmMessageAlready);
    setSessionNeedsResume(sessionId, shouldShowResume);
    if (dmAnswer) {
      setPendingInitialNarrative(sessionId, false);
    }
    logCampaignStartTrace('handleCampaignUpdate completed', {
      sessionId,
      needsResponse: shouldShowResume,
      pendingInitialCleared: Boolean(dmAnswer),
    });

    if (sessionId === currentCampaignId) {
      setIsLoading(false);
    }
  }, [
    currentCampaignId,
    setPendingInitialNarrative,
    transformStructuredData,
    setSessionStructuredData,
    handleNewImage,
    setSessionHistoryInfo,
    reloadHistoryAfterStream,
    messagesBySessionRef,
    pendingInitialNarrativeRef,
    setSessionNeedsResume,
    setIsLoading,
    clearStreaming,
    updateStreamingNarrative,
    updateStreamingResponse,
  ]);

  // Connect to DM Socket.IO using custom hook - use sessionId from URL
  // Ref to hold the Socket.IO socket for passing to child components
  const dmSocketRef = useRef(null);
  const [dmSocketVersion, setDmSocketVersion] = useState(0);

  const {
    socket: dmSocket,
    isConnected: dmIsConnected,
    connectionToken: dmConnectionToken,
    emit: dmEmit,
    sendAudioPlayed: dmSendAudioPlayed,
  } = useGameSocket({
    campaignId: resolvedCampaignIdForSocket,
    getAccessToken: getAccessTokenSilently,
    role: 'dm',
    handlers: {
      audio_available: handleAudioAvailable,
      narrative_chunk: handleNarrativeChunk,
      player_response_chunk: handleResponseChunk,
      metadata_update: handleMetadataUpdate,
      initialization_error: handleInitializationError,
      campaign_updated: handleCampaignUpdate,
      campaign_loaded: handleCampaignUpdate,
      campaign_active: handleCampaignUpdate,
      audio_stream_started: handleAudioStreamStarted,
      audio_stream_stopped: handleAudioStreamStopped,
      audio_queue_cleared: handleAudioQueueCleared,
      playback_queue_updated: handlePlaybackQueueUpdated,
      sfx_available: sfx.handleSfxAvailable,
      // Audio acknowledgment confirmation (for reliable user queue playback)
      audio_played_confirmed: handleAudioPlayedConfirmation,
      // Collaborative editing events (replacing old collab WebSocket)
      player_list: (data) => {
        console.log('[Collab] player_list RAW data:', JSON.stringify(data, null, 2));
        if (Array.isArray(data.players)) {
          // Transform from backend format {playerId, playerName} to {id, name}
          const normalized = data.players.map(p => {
            const id = p.playerId || p.id;
            const name = p.playerName || p.name;
            if (!id) {
              console.error('[Collab] player_list: Player missing playerId:', p);
            }
            return {
              id,
              name,
              isConnected: p.isConnected ?? true,
            };
          });
          console.log('[Collab] player_list normalized:', normalized);
          setCollabPlayers(normalized);
        }
      },
      initial_state: (data) => {
        console.log('[Collab] initial_state RAW data:', JSON.stringify(data, null, 2));
        if (Array.isArray(data.allPlayers)) {
          // Transform from backend format to {id, name}
          const normalized = data.allPlayers.map(p => {
            const id = p.playerId || p.id;
            const name = p.playerName || p.name;
            if (!id) {
              console.error('[Collab] initial_state: Player missing playerId:', p);
            }
            return {
              id,
              name,
              isConnected: p.isConnected ?? true,
            };
          });
          console.log('[Collab] initial_state normalized:', normalized);
          setCollabPlayers(normalized);
        }
      },
      registered: (data) => {
        console.log('[Collab] DM registered via Socket.IO:', data);
        setCollabIsConnected(true);
      },
      // Player action submission - add to DM's player options section
      player_action_submitted: (data) => {
        console.log('[DM] Received player action submission:', data);
        const { character_name, action_text, character_id, timestamp } = data;
        if (action_text && action_text.trim()) {
          setPlayerSubmissions(prev => [
            ...prev,
            {
              id: `${character_id}-${Date.now()}`,
              characterName: character_name || 'Player',
              characterId: character_id,
              actionText: action_text.trim(),
              timestamp: timestamp || new Date().toISOString(),
            }
          ]);
        }
      },
      // Room events - DM view doesn't need these but useGameSocket registers them
      'room.dm_joined': () => {}, // No-op: DM doesn't need to handle their own join event
      'room.dm_left': () => {},   // No-op: DM doesn't need to handle their own leave event
    },
  });

  // Keep the socket ref updated for components that need the ref pattern
  useEffect(() => {
    dmSocketRef.current = dmSocket;
    if (dmSocket) {
      setDmSocketVersion((v) => v + 1);
    }
  }, [dmSocket]);

  // Update socketEmitRef so useUserAudioQueue can use it for reliable acknowledgments
  useEffect(() => {
    socketEmitRef.current = dmEmit;
  }, [dmEmit]);

  // Sync collab connection state with Socket.IO connection
  useEffect(() => {
    setCollabIsConnected(dmIsConnected);
  }, [dmIsConnected]);

  // Set collab player ID from user email
  useEffect(() => {
    if (user?.email) {
      const playerId = `${user.email}:dm`;
      setCollabPlayerId(playerId);
      // Register with backend when connected
      if (dmIsConnected && dmSocket) {
        dmSocket.emit('register', { playerId, playerName: 'DM' });
      }
    }
  }, [user?.email, dmIsConnected, dmSocket]);

  const sendAudioPlayedAck = useCallback((campaignId, chunkIds) => {
    if (!chunkIds || chunkIds.length === 0) {
      return;
    }

    const resolvedCampaignId = campaignId || currentCampaignId;
    const payload = {
      campaign_id: resolvedCampaignId,
      chunk_ids: chunkIds,
      connection_token: dmConnectionToken || undefined,
    };
    // Socket.IO handles buffering/reconnection automatically
    dmEmit('audio_played', payload);
    console.log('[AUDIO_DEBUG] 📤 Sent audio_played acknowledgment via Socket.IO | campaign=%s chunk_ids=%s token=%s',
      resolvedCampaignId, JSON.stringify(chunkIds), dmConnectionToken ? 'present' : 'missing');
  }, [dmEmit, dmConnectionToken, currentCampaignId]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const handleStreamComplete = (event) => {
      const detail = event?.detail || {};
      const chunkIds = detail.chunkIds;
      const campaignId = detail.campaignId || currentCampaignId;

      console.log('[AUDIO_DEBUG] 🏁 Frontend stream completed | campaign=%s chunk_count=%d chunk_ids=%s',
        campaignId, (chunkIds || []).length, JSON.stringify(chunkIds));

      if (!chunkIds || !chunkIds.length) {
        console.log('[AUDIO_DEBUG] No chunk IDs to acknowledge');
        return;
      }

      sendAudioPlayedAck(campaignId, chunkIds);
    };

    window.addEventListener(AUDIO_STREAM_COMPLETED_EVENT, handleStreamComplete);
    return () => {
      window.removeEventListener(AUDIO_STREAM_COMPLETED_EVENT, handleStreamComplete);
    };
  }, [sendAudioPlayedAck, currentCampaignId]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const handleQueuedAudioPlayed = (event) => {
      const detail = event?.detail || {};
      const chunkId = detail.chunk_id;
      const sessionId = detail.campaign_id || currentCampaignId;

      if (!chunkId) {
        return;
      }

      sendAudioPlayedAck(sessionId, [chunkId]);
    };

    window.addEventListener('gaia:audio-played', handleQueuedAudioPlayed);
    return () => {
      window.removeEventListener('gaia:audio-played', handleQueuedAudioPlayed);
    };
  }, [sendAudioPlayedAck, currentCampaignId]);

  // Listen for queued audio playback completion
  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const handleQueuedAudioPlayed = (event) => {
      const detail = event?.detail || {};
      const chunkId = detail.chunk_id;
      const sessionId = detail.campaign_id || currentCampaignId;

      console.log('[AUDIO_DEBUG] 🎵 Queued audio played | session=%s chunk_id=%s',
        sessionId, chunkId);

      if (!chunkId) {
        console.log('[AUDIO_DEBUG] No chunk ID to acknowledge');
        return;
      }

      if (!dmSocket?.connected) {
        console.warn('[AUDIO_DEBUG] ⚠️ Cannot acknowledge chunk - DM socket unavailable');
        return;
      }

      const payload = {
        campaign_id: sessionId,
        chunk_ids: [chunkId],
        connection_token: dmConnectionToken || undefined,
      };
      dmEmit('audio_played', payload);
      console.log('[AUDIO_DEBUG] 📤 Sent queued audio acknowledgment | session=%s chunk_id=%s token=%s',
        sessionId, chunkId, dmConnectionToken ? 'present' : 'missing');
    };

    window.addEventListener('gaia:audio-played', handleQueuedAudioPlayed);
    return () => {
      window.removeEventListener('gaia:audio-played', handleQueuedAudioPlayed);
    };
  }, [dmSocket, dmEmit, dmConnectionToken, currentCampaignId]);

  // Old WebSocket code removed - now handled by useGameSocket hook
  // Control panel ref and keyboard shortcuts now handled by hooks (see above)

  // Voice transcription handler - writes to collaborative editor via Socket.IO
  // NOTE: Must be defined AFTER useGameSocket hook since it uses dmIsConnected and dmEmit
  const handleVoiceTranscription = useCallback((transcribedText, metadata) => {
    console.log('🎤 [DM] Voice transcription received:', transcribedText, metadata);

    if (!isTranscribingRef.current) {
      console.warn('🎤 [DM] Ignoring transcription because mic is not active');
      return;
    }

    if (!dmIsConnected) {
      console.warn('🎤 [DM] Socket.IO not connected, voice text not sent');
      return;
    }

    dmEmit('voice_transcription', {
      text: transcribedText,
      is_partial: metadata?.is_partial ?? false
    });

    console.log('🎤 [DM] Sent voice_transcription via Socket.IO, is_partial:', metadata?.is_partial);
  }, [dmIsConnected, dmEmit]);

  // Toggle DM voice transcription on/off
  const toggleVoiceTranscription = useCallback(async () => {
    if (isTranscribing) {
      setIsTranscribing(false);
      setVoiceActivityLevel(0);
      return;
    }

    const sendVoiceSessionStart = () => {
      if (dmIsConnected) {
        dmEmit('voice_session_start', {});
        console.log('🎤 [DM] Sent voice_session_start via Socket.IO');
      }
    };

    if (audioPermissionState !== 'granted') {
      try {
        console.log('🎤 [DM] Requesting microphone permission for transcription...');
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 16000
          }
        });

        stream.getTracks().forEach(track => track.stop());

        setAudioPermissionState('granted');
        localStorage.setItem('audioPermissionState', 'granted');
        sendVoiceSessionStart();
        setIsTranscribing(true);
      } catch (error) {
        console.error('❌ [DM] Microphone permission denied:', error);
        setAudioPermissionState('denied');
        localStorage.setItem('audioPermissionState', 'denied');
      }
    } else {
      sendVoiceSessionStart();
      setIsTranscribing(true);
    }
  }, [isTranscribing, audioPermissionState, dmIsConnected, dmEmit]);

  useEffect(() => {
    transcriptionRef.current = {
      toggleRecording: toggleVoiceTranscription,
    };
  }, [toggleVoiceTranscription]);

  // Debug logging for isLoading changes
  useEffect(() => {
    console.log("🔄 isLoading changed to:", isLoading);
  }, [isLoading]);

  // Debug logging
  useEffect(() => {
    console.log("🎮 App component mounted");
    // Service debugging (commented out)
    // console.log("🎮 Message service:", messageService);
    // console.log("🎮 Using OpenAPI:", API_CONFIG.USE_OPENAPI);
    console.log("🎮 Current state:", {
      messages: messages.length,
      isLoading,
      hasStructuredData: !!latestStructuredData
    });
  }, [messages, isLoading, latestStructuredData]);

  // Audio acknowledgment removed - synchronized streaming doesn't use chunk-by-chunk acks

  // Add a ref for the chat messages container and scroll to bottom on new messages
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Poll TTS playback status with graceful error handling
  useEffect(() => {
    if (!currentCampaignId) {
      setIsTTSPlaying(false);
      return;
    }

    let failureCount = 0;
    const maxFailures = 3;
    const sessionIdForStatus = currentCampaignId;
    let intervalId = null;

    const checkTTSStatus = async () => {
      try {
        const status = await apiService.getTTSQueueStatus(sessionIdForStatus);
        if (status) {
          setIsTTSPlaying(status.is_playing || status.queue_size > 0);
          failureCount = 0;
        }
      } catch {
        failureCount += 1;
        if (failureCount === maxFailures) {
          console.debug('TTS status endpoint not available');
        }
        setIsTTSPlaying(false);
      }
    };

    const intervalMs = hasPendingAudio ? 5000 : 45000;
    checkTTSStatus();
    intervalId = setInterval(checkTTSStatus, intervalMs);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [currentCampaignId, hasPendingAudio]);

  // Old resetApp function removed - now handled by useCampaignOperations hook

  const handleSendMessage = async (messageText) => {
    // Handle both string messages and event objects
    let message;

    if (typeof messageText === 'string') {
      // Programmatic call with explicit message string - don't clear input
      // Allow empty string for DM "continue" action
      message = messageText;
    } else if (messageText && typeof messageText === 'object' && messageText.preventDefault) {
      // It's an event object, use inputMessage
      messageText.preventDefault();
      message = inputMessage;
    } else {
      // Use inputMessage as fallback (e.g., Enter key)
      message = inputMessage;
    }

    // Ensure message is a string - allow empty string for DM "continue" action
    if (typeof message !== 'string') return;
    // For non-programmatic calls (form submission), require non-empty text
    const isProgrammaticCall = typeof messageText === 'string';
    if (!isProgrammaticCall && !message.trim()) return;
    if (!currentCampaignId) {
      setError('No active campaign selected. Start a new campaign before sending messages.');
      return;
    }

    // Clear input immediately if not a programmatic call
    if (typeof messageText !== 'string') {
      setInputMessage("");
    }

    const sessionId = currentCampaignId;

    console.log("🎮 handleSendMessage called with:", message);
    setIsLoading(true);
    setError(null);
    setSessionNeedsResume(sessionId, false);

    // Add user message to chat with unique ID for correlation
    const messageId = generateMessageId();
    const fallbackCharacterName =
      getActiveCharacterNameForSession(sessionId) || 'Player';
    addUserMessage(sessionId, message, { messageId, characterName: fallbackCharacterName });
    
    try {
      console.log("🎮 Calling message service with campaign ID:", sessionId);
      const result = await messageService.sendMessage(message, sessionId);
      console.log("🎮 Message service result:", result);
      const structData = result.structuredData || result.structured_data || null;
      setSessionStructuredData(sessionId, structData);
      // Audio handled via synchronized streaming (audio_stream_started WebSocket message)
      if (structData?.audio) {
        markLastDmMessageHasAudio(sessionId);
      }

      // Check for generated image
      if (structData && (structData.generated_image_url || structData.generated_image_path)) {
        handleNewImage(structData);
      }
      
      // Check for history info
      if (result.history_info) {
        setSessionHistoryInfo(sessionId, result.history_info);
        // Auto-hide after 10 seconds
        setTimeout(() => setSessionHistoryInfo(sessionId, null), 10000);
      }
      // Only show the 'answer' field in the chat
      const answerText = (structData && structData.answer) ? structData.answer : (result.response || null);

      if (answerText) {
        addDMMessage(sessionId, answerText, {
          hasAudio: Boolean(structData?.audio),
          structuredContent: structData
            ? {
                narrative: structData.narrative || null,
                answer: structData.answer || answerText || null,
                summary: structData.summary || null,
                observations: structData.observations || null,
                perception_checks: structData.perception_checks || null,
                streaming_answer: structData.streaming_answer || null,
              }
            : null,
          isStreamed: Boolean(structData?.streamed),
        });

        // Clear streaming state after adding DM message to prevent duplicate display
        // The message is now in the history, so we don't need the streaming preview
        if (structData?.streamed) {
          clearStreaming(sessionId);
        }
      }

      // Clear player submissions after DM successfully processes a turn
      // This prevents stale submissions from persisting in the DM view
      setPlayerSubmissions([]);
    } catch (error) {
      console.error("❌ Error in handleSendMessage:", error);
      setError(`Failed to send message: ${error.message}`);
      // Add error message to chat
      addSystemError(sessionId, error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Old campaign operations and share functions removed - now handled by hooks

  const handleAddContext = async (contextText) => {
    if (!currentCampaignId) {
      setError('No active campaign selected. Start a campaign before adding context.');
      return;
    }
    const sessionId = currentCampaignId;
    try {
      // Add context as a user message that's marked as context-only
      addContextMessage(sessionId, contextText);

      // Send to backend to add to conversation history without DM response
      console.log('Sending context to backend:', contextText);
      const result = await messageService.addContext(
        contextText,
        sessionId
      );

      if (result.success) {
        console.log('✅ Context saved to campaign history');
      }
    } catch (error) {
      console.error('Failed to add context:', error);
      setError(`Failed to add context: ${error.message}`);
    }
  };

  // Show error if any
  if (error) {
    console.log("❌ App error:", error);
  }

  // Track campaigns we've already attempted to load to prevent retry loops
  const attemptedCampaigns = useRef(new Set());

  // Load campaign from URL session ID
  useEffect(() => {
    const loadCampaignFromUrl = async () => {
      if (sessionId && sessionId !== currentCampaignId) {
        // Check if we've already tried and failed to load this campaign
        if (attemptedCampaigns.current.has(sessionId)) {
          console.log('⚠️ Already attempted to load campaign:', sessionId, '- skipping retry');
          return;
        }

        console.log('📍 Loading campaign from URL:', sessionId);

        // Mark this campaign as attempted BEFORE calling handleSelectCampaign
        attemptedCampaigns.current.add(sessionId);

        try {
          const campaignData = await handleSelectCampaign(sessionId, false); // isNewCampaign = false
          if (campaignData) {
            setCampaignName(campaignData.name || sessionId);
            console.log('✅ Successfully loaded campaign from URL:', sessionId);
            // Remove from attempted set on success so user can retry later
            attemptedCampaigns.current.delete(sessionId);
          }
        } catch (error) {
          console.error('❌ Failed to load campaign from URL:', error);

          // Handle different error types with user-friendly messages
          if (error.message?.includes('404') || error.message?.includes('not found')) {
            setError('Campaign not found');
            // Keep in attempted set - don't retry 404s
          } else if (error.message?.includes('403') || error.message?.includes('unauthorized') || error.message?.includes('Access denied')) {
            setError('Access denied');
            // Keep in attempted set - don't retry access denied
          } else {
            setError('Unable to load campaign');
            // For transient errors, remove from attempted set to allow retry
            attemptedCampaigns.current.delete(sessionId);
          }
        }
      }
    };
    loadCampaignFromUrl();
  }, [sessionId, currentCampaignId, handleSelectCampaign, setCampaignName]);

  // Handle shared session invite tokens from URL
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

    const handleInvite = async () => {
      setIsLoading(true);
      const result = await joinSharedSession(inviteToken);
      if (result?.success) {
        setInfoBanner(result.message || 'Successfully joined shared session.');
      } else if (result?.error) {
        setError(result.error);
      }
      setIsLoading(false);
    };

    handleInvite();
  }, [joinSharedSession, setIsLoading, setError, setInfoBanner]);

  // If there's a critical app error, show it
  if (appError) {
    return (
      <div className="p-5 text-gaia-error bg-red-50 border-2 border-gaia-error m-5 rounded-lg">
        <h2 className="text-xl font-bold mb-3">🚨 Critical App Error!</h2>
        <p className="mb-2"><strong>Type:</strong> {appError.type}</p>
        <p className="mb-2"><strong>Message:</strong> {appError.message}</p>
        <details className="whitespace-pre-wrap">
          <summary className="cursor-pointer hover:text-red-700">Stack Trace</summary>
          <pre className="mt-2">{appError.stack}</pre>
        </details>
        <button 
          onClick={() => window.location.reload()} 
          className="mt-4 px-4 py-2 bg-gaia-error text-white rounded-md hover:bg-red-600 transition-colors"
        >
          🔄 Reload Page
        </button>
      </div>
    );
  }

  return (
    <LoadingProvider>
      <ErrorBoundary>
        <div className="flex flex-col h-screen min-h-0">
        {/* Voice Activity Indicator */}
        <VoiceActivityIndicator 
          sessionId={voiceRecordingState.sessionId}
          isRecording={voiceRecordingState.isRecording}
          voiceActivity={voiceActivityActive}
        />
        
        {/* Header with controls */}
        <SharedHeaderLayout>
            <UnifiedLoadingIndicator />
            {currentCampaignId && <SettingsButton onClick={() => setIsSettingsModalOpen(true)} />}
            <LobbyButton />
            <button onClick={handleArenaQuickStart} className="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700 transition-colors font-semibold" title="Quick start 2v2 arena combat">
              ⚔️ Fight in Arena
            </button>
            {/* Characters button removed - will be added in followup */}
            <button
              onClick={() => setShowShareModal(true)}
              className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!currentCampaignId}
            >
              🤝 Share
            </button>
            <button onClick={() => setShowContextInput(true)} className="px-3 py-1 bg-purple-600 text-white rounded text-xs hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled={!currentCampaignId}>
              📝 Add Context
            </button>
            <button onClick={() => setShowKeyboardHelp(true)} className="px-3 py-1 bg-gaia-light text-white rounded text-xs hover:bg-gaia-border transition-colors" title="Keyboard shortcuts">
              ⌨️ Shortcuts
            </button>
            {currentCampaignId && (
              <>
                <ConnectedPlayers
                  campaignId={currentCampaignId}
                  dmSocket={dmSocket}
                />
                <CampaignNameDisplay name={campaignName || currentCampaignId} />
              </>
            )}
        </SharedHeaderLayout>

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
          <div className="bg-gaia-error text-white px-4 py-3 mx-4 rounded-md font-bold">
            Error: {error}
          </div>
        )}
        {infoBanner && (
          <div className="bg-blue-600 text-white px-4 py-3 mx-4 rounded-md font-semibold">
            {infoBanner}
          </div>
        )}

        {/* Main content */}
        <main className="flex-1 flex flex-row p-4 gap-4 h-full min-h-0 overflow-hidden">
          {/* Game dashboard */}
          <div className="flex-[2] min-h-0 h-full flex overflow-hidden max-h-full gap-4">
            <div className="flex-1 min-w-0">
              <RoomProvider
                campaignId={resolvedCampaignIdForSocket}
                currentUserId={user?.user_id || null}
                currentUserProfile={currentUserProfile}
                socketRef={dmSocketRef}
                webSocketVersion={dmSocketVersion}
                onRoomEvent={handleRoomEvent}
              >
                <GameDashboard
                ref={gameDashboardRef}
                latestStructuredData={latestStructuredData}
                onImageGenerated={handleImageClick}
                campaignId={resolvedCampaignIdForSocket}
                selectedVoice={selectedVoice}
                streamingNarrative={dmStreamingNarrative}
                streamingResponse={dmStreamingResponse}
                isNarrativeStreaming={dmIsNarrativeStreaming}
                isResponseStreaming={dmIsResponseStreaming}
                onDebugStreamPreview={handleDebugStreamPreview}
                messages={messages}
                inputMessage={inputMessage}
                onInputChange={(e) => setInputMessage(e.target.value)}
                onSendMessage={handleSendMessage}
                onKeyDown={handleKeyDown}
                isChatProcessing={isChatProcessing}
                isTranscribing={isTranscribing}
                onToggleTranscription={toggleVoiceTranscription}
                voiceActivityLevel={voiceActivityLevel}
                audioPermissionState={audioPermissionState}
                chatInputRef={chatInputRef}
                // Collaborative editing props (now via Socket.IO)
                collabWebSocket={dmSocket}
                collabPlayerId={collabPlayerId}
                collabPlayerName={collabPlayerName}
                collabAllPlayers={collabPlayers}
                collabIsConnected={collabIsConnected}
                // Player submissions (from player action submissions)
                playerSubmissions={playerSubmissions}
                onCopyPlayerSubmission={(submission) => {
                  // Remove the submission after copying
                  setPlayerSubmissions(prev => prev.filter(s => s.id !== submission.id));
                }}
                />
              </RoomProvider>
            </div>
          </div>

        </main>

        <AudioPlayerBar
          sessionId={currentCampaignId}
          queueInfo={playbackQueueInfo}
          userAudioBlocked={audioBlocked}
          onUnlockUserAudio={unlockAudio}
        />

        {/* Voice Input (hidden background service for DM collaborative editor) */}
        {isTranscribing && (
          <div style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden' }}>
            <VoiceInputScribeV2
              onSendMessage={handleVoiceTranscription}
              conversationalMode={true}
              userEmail={user?.email}
              characterId={null}
              autoStart={true}
              onVoiceLevel={setVoiceActivityLevel}
            />
          </div>
        )}

        {/* Settings Modal */}
        <SettingsModal
          isOpen={isSettingsModalOpen}
          onClose={() => setIsSettingsModalOpen(false)}
          ref={controlPanelRef}
          selectedVoice={selectedVoice}
          onVoiceSelect={setSelectedVoice}
          gameDashboardRef={gameDashboardRef}
          onImageGenerated={handleNewImage}
          campaignId={currentCampaignId}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />

        {/* Campaign Manager Modal */}
        <CampaignManager
          isOpen={showCampaignList}
          currentCampaignId={currentCampaignId}
          onCampaignSelect={handleSelectCampaign}
          onClose={() => setShowCampaignList(false)}
        />

        <Modal
          open={showShareModal}
          onClose={() => setShowShareModal(false)}
          title="Share Session"
          width="max-w-md"
        >
          <div className="space-y-4">
            {shareState.error && (
              <Alert variant="error">{shareState.error}</Alert>
            )}
            {shareState.loading ? (
              <div className="text-gray-300 text-sm">Generating invite link…</div>
            ) : (
              <>
                <div className="space-y-2">
                  <label className="block text-sm font-semibold text-gray-300">Invite Token</label>
                  <Input
                    value={shareState.token || ''}
                    readOnly
                    onFocus={(e) => e.target.select()}
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-semibold text-gray-300">Shareable Link</label>
                  <Input
                    value={inviteLink}
                    readOnly
                    onFocus={(e) => e.target.select()}
                  />
                </div>
                {shareState.expiresAt && (
                  <p className="text-xs text-gray-400">
                    Expires {new Date(shareState.expiresAt).toLocaleString()}
                  </p>
                )}
              </>
            )}
            <div className="flex justify-between gap-2">
              <Button
                variant="secondary"
                onClick={() => fetchInviteToken(true)}
                disabled={shareState.loading || !currentCampaignId}
              >
                Regenerate
              </Button>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setShowShareModal(false)}>
                  Close
                </Button>
                <Button
                  variant="primary"
                  onClick={handleCopyInviteLink}
                  disabled={!shareState.token || shareState.loading}
                >
                  {shareState.copied ? 'Copied!' : 'Copy Link'}
                </Button>
              </div>
            </div>
          </div>
        </Modal>

        {/* Campaign Setup Modal */}
        <CampaignSetup
          isOpen={showCampaignSetup}
          onComplete={(campaignId) => {
            setShowCampaignSetup(false);
            handleSelectCampaign(campaignId, true); // Pass true for new campaign
          }}
          onCancel={() => setShowCampaignSetup(false)}
          onCreateBlank={resetApp}
        />

        {/* Character Management removed - will be added in followup */}
        
        {/* Context Input Modal */}
        <ContextInput
          isOpen={showContextInput}
          onAddContext={handleAddContext}
          onClose={() => setShowContextInput(false)}
        />
        
        {/* History Info Popup */}
        {historyInfo && (
          <div className="history-info-popup">
            <div className="history-info-content">
              <h4>📚 Session History Loaded</h4>
              <p className="history-summary">
                Loaded {historyInfo.total_messages} messages from previous sessions
              </p>
              {historyInfo.last_messages.length > 0 && (
                <div className="history-preview">
                  <h5>Last {historyInfo.last_messages.length} messages:</h5>
                  <ul>
                    {historyInfo.last_messages.map((msg, idx) => (
                      <li key={idx}>
                        <span className={`role-badge ${msg.role}`}>{msg.role}:</span>
                        <span className="message-preview">{msg.preview}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <button 
                className="close-history-info"
                onClick={() => currentCampaignId && setSessionHistoryInfo(currentCampaignId, null)}
                title="Close"
              >
                ✕
              </button>
            </div>
          </div>
        )}
        
        {/* Image Popup */}
        {showImagePopup && currentPopupImage && (
          <ImagePopup
            imageUrl={currentPopupImage.imageUrl}
            imagePath={currentPopupImage.imagePath}
            imagePrompt={currentPopupImage.imagePrompt}
            duration={5000}
            onClose={handleImagePopupClose}
          />
        )}
        
        {/* Keyboard Shortcuts Help */}
        <KeyboardShortcutsHelp
          isOpen={showKeyboardHelp}
          onClose={() => setShowKeyboardHelp(false)}
        />
      </div>
    </ErrorBoundary>
    </LoadingProvider>
  );
}

// Wrap App with AudioStreamProvider and SFXProvider to enable synchronized audio streaming
// and simultaneous sound effects playback
function AppWithAudioStream() {
  return (
    <AudioStreamProvider>
      <SFXProvider>
        <App />
      </SFXProvider>
    </AudioStreamProvider>
  );
}

export default AppWithAudioStream;
