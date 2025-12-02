import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useAuth } from './contexts/Auth0Context.jsx';
import { UserMenu } from './AppWithAuth0.jsx';
import GameDashboard from './components/GameDashboard.jsx';
import AudioPlayerBar from './components/audio/AudioPlayerBar.jsx';
import ControlPanel from "./components/ControlPanel.jsx";
import CampaignManager from './components/CampaignManager.jsx';
import CampaignSetup from "./components/CampaignSetup.jsx";
// CharacterManagement removed - will be added in followup
import ContextInput from './components/ContextInput.jsx';
import ContinuousTranscription from './components/ContinuousTranscription.jsx';
import VoiceActivityIndicator from "./components/VoiceActivityIndicator.jsx";
import ImagePopup from "./components/ImagePopup.jsx";
import KeyboardShortcutsHelp from "./components/KeyboardShortcutsHelp.jsx";
import SettingsButton from './components/SettingsButton.jsx';
import SettingsModal from './components/SettingsModal.jsx';
import ConnectedPlayers from './components/ConnectedPlayers.jsx';
import { LoadingProvider } from './contexts/LoadingContext.jsx';
import UnifiedLoadingIndicator from './components/UnifiedLoadingIndicator.jsx';
import { API_CONFIG } from './config/api.js';
// Import API service
import apiService from "./services/apiService.js"; // OpenAPI service
import { useAudioQueue } from './context/audioQueueContext.jsx';
import { Modal } from './components/base-ui/Modal.jsx';
import { Button } from './components/base-ui/Button.jsx';
import { Input } from './components/base-ui/Input.jsx';
import { Alert } from './components/base-ui/Alert.jsx';

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

const IMAGE_DISMISS_TTL_MS = 60 * 1000;

function App() {
  const { handleAuthError, getAccessTokenSilently, refreshAccessToken } = useAuth();
  const {
    enqueue: enqueueAudio,
    clear: clearAudioQueue,
    play: playAudio,
    enableAudio,
    needsUserGesture,
    queues,
    isPlaying: queueIsPlaying,
    currentTrack,
  } = useAudioQueue();
  const playAudioRef = useRef(playAudio);
  useEffect(() => {
    playAudioRef.current = playAudio;
  }, [playAudio]);
  const [messagesBySession, setMessagesBySession] = useState({});
  const messagesBySessionRef = useRef(messagesBySession);
  const [structuredDataBySession, setStructuredDataBySession] = useState({});
  const [historyInfoBySession, setHistoryInfoBySession] = useState({});
  const [needsResumeBySession, setNeedsResumeBySession] = useState({});
  const [pendingInitialNarrativeBySession, setPendingInitialNarrativeBySession] = useState({});
  const [playerSuggestionBySession, setPlayerSuggestionBySession] = useState({});
  const [dmStreamingNarrativeBySession, setDmStreamingNarrativeBySession] = useState({});
  const [dmStreamingResponseBySession, setDmStreamingResponseBySession] = useState({});
  const [dmIsNarrativeStreamingBySession, setDmIsNarrativeStreamingBySession] = useState({});
  const [dmIsResponseStreamingBySession, setDmIsResponseStreamingBySession] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const initialSessionId = typeof window !== 'undefined' ? localStorage.getItem('lastCampaignId') : null;
  const [inputMessage, setInputMessage] = useState("");

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
  const [error, setError] = useState(null);
  const [appError, setAppError] = useState(null);
  const [currentCampaignId, setCurrentCampaignId] = useState(initialSessionId);
  const [campaigns, setCampaigns] = useState([]);
  const [showCampaignList, setShowCampaignList] = useState(false);
  const [showContextInput, setShowContextInput] = useState(false);
  const [showAudioRecorder, setShowAudioRecorder] = useState(false);
  const [isTTSPlaying, setIsTTSPlaying] = useState(false);
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState(''); // Will be set dynamically by ControlPanel
  const [selectedProvider, setSelectedProvider] = useState(''); // Will be set dynamically by TTSProviderSelector
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const dmWebSocketRef = useRef(null);
  const dmReconnectTimerRef = useRef(null);
  const dmIsConnectingRef = useRef(false); // Track if DM WebSocket connection is in progress
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareState, setShareState] = useState({
    loading: false,
    token: '',
    expiresAt: null,
    error: null,
    copied: false
  });
  const [infoBanner, setInfoBanner] = useState(null);

  const messages = currentCampaignId ? messagesBySession[currentCampaignId] || [] : [];
  const latestStructuredData = currentCampaignId
    ? structuredDataBySession[currentCampaignId] ?? null
    : null;
  const historyInfo = currentCampaignId ? historyInfoBySession[currentCampaignId] ?? null : null;
  const isInitialNarrativePending = currentCampaignId ? Boolean(pendingInitialNarrativeBySession[currentCampaignId]) : false;
  const isChatProcessing = isLoading || isInitialNarrativePending;
  const playerSuggestion = currentCampaignId
    ? playerSuggestionBySession[currentCampaignId] ?? null
    : null;
  const dmStreamingNarrative = currentCampaignId
    ? dmStreamingNarrativeBySession[currentCampaignId] || ''
    : '';
  const dmStreamingResponse = currentCampaignId
    ? dmStreamingResponseBySession[currentCampaignId] || ''
    : '';
  const dmIsNarrativeStreaming = currentCampaignId
    ? dmIsNarrativeStreamingBySession[currentCampaignId] || false
    : false;
  const dmIsResponseStreaming = currentCampaignId
    ? dmIsResponseStreamingBySession[currentCampaignId] || false
    : false;

  const handleDebugStreamPreview = useCallback((sessionId, narrative, playerResponse) => {
    if (!sessionId) {
      return;
    }

    if (typeof narrative === 'string') {
      setDmStreamingNarrativeBySession((prev) => ({
        ...prev,
        [sessionId]: narrative,
      }));
      if (narrative.trim()) {
        setDmIsNarrativeStreamingBySession((prev) => ({
          ...prev,
          [sessionId]: true,
        }));
        setTimeout(() => {
          setDmIsNarrativeStreamingBySession((prev) => {
            if (!prev[sessionId]) {
              return prev;
            }
            return {
              ...prev,
              [sessionId]: false,
            };
          });
        }, 1000);
      }
    }

    if (typeof playerResponse === 'string') {
      setDmStreamingResponseBySession((prev) => ({
        ...prev,
        [sessionId]: playerResponse,
      }));
      if (playerResponse.trim()) {
        setDmIsResponseStreamingBySession((prev) => ({
          ...prev,
          [sessionId]: true,
        }));
        setTimeout(() => {
          setDmIsResponseStreamingBySession((prev) => {
            if (!prev[sessionId]) {
              return prev;
            }
            return {
              ...prev,
              [sessionId]: false,
            };
          });
        }, 1000);
      }
    }
  }, [
    setDmStreamingNarrativeBySession,
    setDmStreamingResponseBySession,
    setDmIsNarrativeStreamingBySession,
    setDmIsResponseStreamingBySession,
  ]);

  const hasPendingAudio = useMemo(() => {
    if (queueIsPlaying) {
      return true;
    }
    if (currentTrack) {
      return true;
    }
    return Object.values(queues || {}).some((items) => (items?.length || 0) > 0);
  }, [queueIsPlaying, currentTrack, queues]);

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
        const updated = { ...previous, [sessionId]: next };
        messagesBySessionRef.current = updated;
        return updated;
      });
    },
    [setMessagesBySession, messagesBySessionRef]
  );

  const normalizeMessageText = useCallback((value) => {
    if (typeof value !== 'string') {
      return value;
    }
    return value.replace(/\s+/g, ' ').trim();
  }, []);

  useEffect(() => {
    messagesBySessionRef.current = messagesBySession;
  }, [messagesBySession]);

  const pendingInitialNarrativeRef = useRef(pendingInitialNarrativeBySession);
  useEffect(() => {
    pendingInitialNarrativeRef.current = pendingInitialNarrativeBySession;
  }, [pendingInitialNarrativeBySession]);

  const dmIsNarrativeStreamingRef = useRef(dmIsNarrativeStreamingBySession);
  useEffect(() => {
    dmIsNarrativeStreamingRef.current = dmIsNarrativeStreamingBySession;
  }, [dmIsNarrativeStreamingBySession]);

  const dmIsResponseStreamingRef = useRef(dmIsResponseStreamingBySession);
  useEffect(() => {
    dmIsResponseStreamingRef.current = dmIsResponseStreamingBySession;
  }, [dmIsResponseStreamingBySession]);

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
        return { ...previous, [sessionId]: next };
      });
    },
    [setStructuredDataBySession]
  );

  const setSessionHistoryInfo = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setHistoryInfoBySession((previous) => {
        if (previous[sessionId] === value) {
          return previous;
        }
        return { ...previous, [sessionId]: value };
      });
    },
    [setHistoryInfoBySession]
  );

  const setSessionNeedsResume = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setNeedsResumeBySession((previous) => {
        const normalized = Boolean(value);
        if (previous[sessionId] === normalized) {
          return previous;
        }
        return { ...previous, [sessionId]: normalized };
      });
    },
    [setNeedsResumeBySession]
  );

  const setPendingInitialNarrative = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setPendingInitialNarrativeBySession((previous) => {
        const normalized = Boolean(value);
        const current = Boolean(previous[sessionId]);
        if (normalized === current) {
          return previous;
        }
        if (!normalized) {
          const next = { ...previous };
          delete next[sessionId];
          return next;
        }
        return { ...previous, [sessionId]: true };
      });
    },
    [setPendingInitialNarrativeBySession]
  );

  const setSessionPlayerSuggestion = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setPlayerSuggestionBySession((previous) => {
        if (previous[sessionId] === value) {
          return previous;
        }
        return { ...previous, [sessionId]: value };
      });
    },
    [setPlayerSuggestionBySession]
  );

  const transformStructuredData = useCallback(
    (structuredData, { needsResponse = false, sessionId = null } = {}) => {
      if (!structuredData || typeof structuredData !== 'object') {
        return null;
      }
      const parseField = (value) => (value ? apiService.parseField(value) : value);
      const narrative = structuredData.narrative || structuredData.answer || '';
      const streamingAnswer = structuredData.streaming_answer || structuredData.streamingAnswer || '';
      const streamingToolEvents = parseField(
        structuredData.streaming_tool_events || structuredData.streamingToolEvents
      ) || [];
      const observations = parseField(structuredData.observations) || [];
      const summary = structuredData.summary || '';
      const rawPlayerOptions =
        structuredData.player_options ??
        structuredData.turn ??
        structuredData.player_response ??
        null;
      const transformed = {
        narrative,
        turn: structuredData.turn || '',
        player_options: parseField(rawPlayerOptions) || '',
        characters: parseField(structuredData.characters) || '',
        status: parseField(structuredData.status) || '',
        environmental_conditions: structuredData.environmental_conditions || '',
        immediate_threats: structuredData.immediate_threats || '',
        story_progression: structuredData.story_progression || '',
        answer: structuredData.answer || narrative,
        summary,
        observations,
        streaming_answer: streamingAnswer,
        streaming_tool_events: streamingToolEvents,
        streamed: Boolean(structuredData.streamed),
        input_needed: needsResponse || Boolean(structuredData.input_needed),
        turn_info: parseField(structuredData.turn_info) || null,
        combat_status: parseField(structuredData.combat_status) || null,
        combat_state: structuredData.combat_state || null,
        action_breakdown: parseField(structuredData.action_breakdown) || null,
        turn_resolution: parseField(structuredData.turn_resolution) || null,
        generated_image_url: structuredData.generated_image_url || '',
        generated_image_path: structuredData.generated_image_path || '',
        generated_image_prompt: structuredData.generated_image_prompt || '',
        generated_image_type: structuredData.generated_image_type || '',
        original_data: structuredData,
        perception_checks:
          parseField(structuredData.metadata?.perception_checks) ||
          parseField(structuredData.perception_checks) ||
          observations,
      };

      if (structuredData.audio) {
        const audioPayload = apiService.mapAudioPayload(structuredData.audio, sessionId);
        if (audioPayload?.url) {
          transformed.audio = audioPayload;
        }
      }

      return transformed;
    },
    []
  );
  
  // Set up Auth0 access token provider for apiService
  useEffect(() => {
    console.log('🔐 App.jsx: Setting up Auth0 access token provider');
    console.log('🔐 getAccessTokenSilently function available:', !!getAccessTokenSilently);
    // Pass a wrapper that always uses the current Auth0 context
    apiService.setTokenProvider(async () => {
      try {
        console.log('🔐 Token wrapper: Fetching token from current Auth0 context');
        return await getAccessTokenSilently();
      } catch (error) {
        console.warn('🔐 Token wrapper: Auth0 context not available:', error);
        return null;
      }
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

  // Auto-enable audio on first user interaction (browser autoplay policy)
  useEffect(() => {
    if (!needsUserGesture) {
      return undefined;
    }

    const handleUserInteraction = () => {
      try {
        enableAudio();
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
  }, [needsUserGesture, enableAudio]);
  
  // Choose the service based on feature flag
  const messageService = apiService; // Always use OpenAPI now
  
  // Log which service is being used
  useEffect(() => {
    console.log(`📡 Using ${API_CONFIG.USE_OPENAPI ? 'OpenAPI/JSON' : 'Protobuf'} service for communication`);
  }, []);


  const [_generatedImages, setGeneratedImages] = useState([]);
  const [showImagePopup, setShowImagePopup] = useState(false);
  const [currentPopupImage, setCurrentPopupImage] = useState(null);
  const [showCampaignSetup, setShowCampaignSetup] = useState(false);
  // Character management removed - will be added in followup
  const [voiceRecordingState, setVoiceRecordingState] = useState({ isRecording: false, sessionId: initialSessionId });
  const [voiceActivityActive, setVoiceActivityActive] = useState(null); // null = unknown, boolean when known
  const chatEndRef = useRef(null);
  const chatInputRef = useRef(null);
  const gameDashboardRef = useRef(null);
  const displayedImageUrlsRef = useRef(new Set());
  const dismissedImageKeysRef = useRef(new Map());
  const transcriptionRef = useRef(null);

  // Store function reference for loading campaign
  // const _loadCampaignRef = useRef(null);

  // Save campaign ID whenever it changes
  useEffect(() => {
    if (currentCampaignId) {
      localStorage.setItem('lastCampaignId', currentCampaignId);
      console.log('💾 Saved campaign ID to localStorage:', currentCampaignId);
      
      // Update page title with campaign name
      const campaign = campaigns.find(c => c.id === currentCampaignId);
      if (campaign) {
        document.title = `${campaign.name} - Gaia D&D`;
      }
    } else {
      document.title = 'Gaia D&D Campaign Manager';
    }
  }, [currentCampaignId, campaigns]);

  useEffect(() => {
    setVoiceRecordingState((prev) => ({
      ...prev,
      sessionId: currentCampaignId || null,
    }));
  }, [currentCampaignId]);
  
  // Helper function to handle new generated images
  const handleNewImage = useCallback((imageData, forceShow = false) => {
    if (!imageData) return;
    
    // Ensure we have a proper URL
    let fullImageUrl = imageData.generated_image_url;

    // If backend provided a direct image URL (e.g., /api/images/...), prefer it.
    // Fall back to session media route only when necessary.
    try {
      const provided = String(fullImageUrl || '');
      const isProvidedUsable = provided.startsWith('/api/images/') || provided.startsWith('http');
      if (!isProvidedUsable) {
        const filenameFromUrl = (() => {
          const raw = imageData.generated_image_url || imageData.generated_image_path || '';
          const last = String(raw).split('/').pop();
          return last && last.includes('.') ? last : null;
        })();
        if (currentCampaignId && filenameFromUrl) {
          fullImageUrl = `/api/media/${encodeURIComponent(currentCampaignId)}/images/${encodeURIComponent(filenameFromUrl)}`;
        }
      }
    } catch (_) {
      // Fallback to provided URL construction below
    }

    if (fullImageUrl && !fullImageUrl.startsWith('http')) {
      fullImageUrl = `${API_CONFIG.BACKEND_URL}${fullImageUrl}`;
    }

    const imageKey = fullImageUrl || imageData.generated_image_path || '';

    if (imageKey) {
      const dismissedMap = dismissedImageKeysRef.current;
      const now = Date.now();

      if (forceShow) {
        dismissedMap.delete(imageKey);
      } else {
        const dismissalExpiry = dismissedMap.get(imageKey);
        if (typeof dismissalExpiry === 'number') {
          if (dismissalExpiry > now) {
            console.log('handleNewImage - image dismissed by user, skipping popup:', imageKey);
            return;
          }
          dismissedMap.delete(imageKey);
        }
        if (displayedImageUrlsRef.current.has(imageKey)) {
          console.log('handleNewImage - image already displayed, skipping popup:', imageKey);
          return;
        }
      }

      displayedImageUrlsRef.current.add(imageKey);
      dismissedImageKeysRef.current.delete(imageKey);
    }

    const newImage = {
      id: Date.now(),
      imageUrl: fullImageUrl,
      imagePath: imageData.generated_image_path,
      imagePrompt: imageData.generated_image_prompt,
      imageType: imageData.generated_image_type,
      timestamp: new Date().toISOString(),
      imageKey,
    };
    
    console.log('handleNewImage - created image object:', newImage);
    
    // Add to images array (only if not already there)
    setGeneratedImages(prev => {
      const exists = prev.some((img) => {
        if (img.imageKey && newImage.imageKey) {
          return img.imageKey === newImage.imageKey;
        }
        return img.imageUrl === newImage.imageUrl;
      });
      if (exists) {
        return prev; // Don't add duplicates
      }
      return [newImage, ...prev];
    });
    
    // Show popup
    setCurrentPopupImage(newImage);
    setShowImagePopup(true);
  }, [currentCampaignId]);

  // Separate function for handling clicked images from gallery
  const handleImageClick = useCallback((imageData) => {
    console.log('🖼️ handleImageClick called with:', imageData);
    // Force show the popup even if image was already displayed
    handleNewImage(imageData, true);
  }, [handleNewImage]);

  const handleImagePopupClose = useCallback((reason = 'auto') => {
    const now = Date.now();
    setCurrentPopupImage((previous) => {
      if (previous?.imageKey && reason === 'manual') {
        dismissedImageKeysRef.current.set(previous.imageKey, now + IMAGE_DISMISS_TTL_MS);
      }
      return null;
    });
    setShowImagePopup(false);
  }, []);

  // Handle copying player suggestion to chat input
  const handleCopyToChat = (suggestionText) => {
    if (!currentCampaignId) {
      return;
    }
    const sessionId = currentCampaignId;
    if (suggestionText === null) {
      // Dismiss without copying
      setSessionPlayerSuggestion(sessionId, null);
      console.log('❌ Dismissed player suggestion');
    } else {
      // Copy to chat and dismiss
      setInputMessage(prev => {
        const separator = prev.trim() ? ' ' : '';
        return prev + separator + suggestionText;
      });
      setSessionPlayerSuggestion(sessionId, null);
      console.log('📝 Appended player suggestion to chat:', suggestionText);
    }
  };

  // Load recent images on startup - moved here to fix hoisting issue
  const loadRecentImages = useCallback(async (campaignId = null) => {
    if (!campaignId) {
      setGeneratedImages([]);
      return;
    }

    console.log('🖼️ Loading recent images...');
    const images = await messageService.fetchRecentImages(20, campaignId);
    
    if (images && images.length > 0) {
      console.log(`🖼️ Found ${images.length} recent images`);
      
      // Convert to the format expected by ImageGallery
      const formattedImages = images.map(img => {
        // Extract a meaningful prompt from the filename
        let prompt = img.filename;
        
        // Handle gemini_image_TIMESTAMP.png format
        if (prompt.startsWith('gemini_image_')) {
          prompt = 'D&D Scene'; // Generic name for gemini images
        } else {
          // Remove common prefixes and suffixes
          prompt = prompt
            .replace(/^(gemini_image_|test_scroll_|\d+_)/, '')
            .replace(/\.(png|jpg|jpeg|webp)$/i, '')
            .replace(/_/g, ' ')
            .replace(/\d{10,}/g, '') // Remove timestamps
            .trim();
        }
        
        // If prompt is empty or just numbers, use generic name
        if (!prompt || /^\d+$/.test(prompt)) {
          prompt = 'D&D Scene';
        }
        
        return {
          id: img.filename,
          imageUrl: `${API_CONFIG.BACKEND_URL}${img.path}`,
          imagePath: img.filename,
          imagePrompt: prompt,
          timestamp: img.timestamp
        };
      });
      
      // Add all images to the generatedImages state
      setGeneratedImages(formattedImages);
      
      // Mark all images as already displayed to prevent automatic popups
      formattedImages.forEach(img => {
        displayedImageUrlsRef.current.add(img.imageUrl);
      });
    }
  }, []);
  
  // Connect to DM WebSocket for receiving player suggestions and state updates
  useEffect(() => {
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
      dmIsConnectingRef.current = false; // Clear connecting flag on cleanup
    };

    if (!currentCampaignId) {
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

      const sessionIdForSocket = currentCampaignId;
      let token = null;
      try {
        token = await getAccessTokenSilently();
        if (!token && typeof getAccessTokenSilently === 'function') {
          const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
          if (audience) {
            try {
              token = await getAccessTokenSilently({
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
        dmIsConnectingRef.current = false; // Clear flag before retry
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

      const wsUrl = `${wsBase}/ws/campaign/dm?session_id=${encodeURIComponent(sessionIdForSocket)}`;

      console.log('🎭 Connecting DM WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      dmWebSocketRef.current = ws;

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
          console.log('🔍 DEBUG: type=' + data.type + ', has chunk=' + !!data.chunk);

          if (data.type === 'player_suggestion' && data.suggestion) {
            console.log('📩 Received player suggestion:', data.suggestion);
            setSessionPlayerSuggestion(sessionIdForSocket, data.suggestion);

            // Add player's message to chat history so it appears before DM response
            const characterName = data.suggestion.metadata?.character_name || 'Player';
            const messageId = data.suggestion.metadata?.message_id || generateMessageId();
            const playerMessage = {
              id: Date.now(),
              message_id: messageId,
              text: data.suggestion.content,
              sender: 'user',
              timestamp: data.suggestion.metadata?.timestamp || new Date().toISOString(),
              characterName: characterName,
              isLocal: true  // Mark as local until confirmed by backend
            };
            setSessionMessages(sessionIdForSocket, (prev) => [...prev, playerMessage]);
          } else if (data.type === 'audio_available' && data.audio) {
            try {
              const mapped = apiService.mapAudioPayload(data.audio, sessionIdForSocket);
              if (mapped?.url) {
                enqueueAudio(mapped);
                setTimeout(() => {
                  playAudioRef.current?.();
                }, 0);
                markLastDmMessageHasAudio(sessionIdForSocket);
              }
            } catch (error) {
              console.warn('🎭 Failed to enqueue DM audio payload:', error);
            }
          } else if (data.type === 'audio_chunk_ready' && data.chunk) {
            console.log('🎵 [DM VIEW] Received audio_chunk_ready event:', data);
            try {
              const chunk = data.chunk;
              const mapped = apiService.mapAudioPayload(chunk, sessionIdForSocket);
              if (mapped?.url) {
                const chunkId = chunk?.id || mapped.id || `${sessionIdForSocket}_chunk_${chunk.chunk_number}_${Date.now()}`;
                const track = {
                  ...mapped,
                  id: chunkId,
                  chunkNumber: chunk?.chunk_number ?? null,
                  totalChunks: chunk?.total_chunks ?? null,
                  sequenceNumber: chunk?.sequence_number ?? data.sequence_number ?? 0,
                  playbackGroup: chunk?.playback_group ?? data.playback_group ?? 'default',
                };
                console.log('🎵 [DM VIEW] Mapped audio chunk:', track);
                enqueueAudio(track);
                setTimeout(() => {
                  playAudioRef.current?.();
                }, 0);
                markLastDmMessageHasAudio(sessionIdForSocket);
              } else {
              console.warn('🎭 [DM VIEW] Audio chunk payload missing URL, skipping enqueue');
              }
            } catch (error) {
              console.error('🎭 [DM VIEW] Failed to enqueue audio chunk:', error);
            }
          } else if (data.type === 'narrative_chunk') {
            const sessionId = data.campaign_id || sessionIdForSocket;
            if (sessionId) {
              const content = data.content || '';
              if (content) {
                setDmStreamingNarrativeBySession((prev) => {
                  const previousContent = prev[sessionId] || '';
                  const isCurrentlyStreaming =
                    dmIsNarrativeStreamingRef.current?.[sessionId] || false;
                  const nextContent = isCurrentlyStreaming
                    ? previousContent + content
                    : content;
                  return {
                    ...prev,
                    [sessionId]: nextContent,
                  };
                });
              } else if (!content && !dmIsNarrativeStreamingRef.current?.[sessionId]) {
                setDmStreamingNarrativeBySession((prev) => {
                  if (!prev[sessionId]) {
                    return prev;
                  }
                  return { ...prev, [sessionId]: prev[sessionId] };
                });
              }

              if (data.is_final) {
                setDmIsNarrativeStreamingBySession((prev) => ({
                  ...prev,
                  [sessionId]: false,
                }));
              } else {
                setDmIsNarrativeStreamingBySession((prev) => ({
                  ...prev,
                  [sessionId]: true,
                }));
              }
            }
          } else if (data.type === 'player_response_chunk') {
            const sessionId = data.campaign_id || sessionIdForSocket;
            if (sessionId) {
              const content = data.content || '';
              if (content) {
                setDmStreamingResponseBySession((prev) => {
                  const previousContent = prev[sessionId] || '';
                  const isCurrentlyStreaming =
                    dmIsResponseStreamingRef.current?.[sessionId] || false;
                  const nextContent = isCurrentlyStreaming
                    ? previousContent + content
                    : content;
                  return {
                    ...prev,
                    [sessionId]: nextContent,
                  };
                });
              } else if (!content && !dmIsResponseStreamingRef.current?.[sessionId]) {
                setDmStreamingResponseBySession((prev) => {
                  if (!prev[sessionId]) {
                    return prev;
                  }
                  return { ...prev, [sessionId]: prev[sessionId] };
                });
              }

              if (data.is_final) {
                setDmIsResponseStreamingBySession((prev) => ({
                  ...prev,
                  [sessionId]: false,
                }));
              } else {
                setDmIsResponseStreamingBySession((prev) => ({
                  ...prev,
                  [sessionId]: true,
                }));
              }
            }
          } else if (data.type === 'metadata_update' && data.metadata) {
            const sessionId = data.campaign_id || sessionIdForSocket;
            if (sessionId) {
              setSessionStructuredData(sessionId, (prev) => ({
                ...(prev || {}),
                ...data.metadata,
              }));
            }
          } else if (data.type === 'initialization_error') {
            const sessionId = data.campaign_id || sessionIdForSocket;
            setPendingInitialNarrative(sessionId, false);
            if (sessionId === currentCampaignId) {
              setIsLoading(false);
              setError(data.error || 'Failed to initialize campaign.');
            }
          } else if (
            data.type === 'campaign_updated' ||
            data.type === 'campaign_loaded' ||
            data.type === 'campaign_active'
          ) {
            const sessionId = data.campaign_id || data.session_id || sessionIdForSocket;
            const structured = data.structured_data;
            if (!sessionId || !structured) {
              setPendingInitialNarrative(sessionId, false);
              return;
            }

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
              // Don't clear streaming state yet - keep visible until history reloads
              if (
                transformed.generated_image_url ||
                transformed.generated_image_path
              ) {
                handleNewImage(transformed);
              }
            }

            if (data.history_info) {
              setSessionHistoryInfo(sessionId, data.history_info);
              setTimeout(() => setSessionHistoryInfo(sessionId, null), 10000);
            }

            // If this was a streamed response, reload chat history from backend and merge with local messages
            const wasStreamed = Boolean(transformed?.streamed || structured?.streamed);
            if (wasStreamed) {
              console.log('🔄 Reloading chat history after streamed response');
              // Reload campaign to get updated message history
              apiService.loadSimpleCampaign(sessionId)
                .then((campaignData) => {
                  if (campaignData?.messages) {
                    const localMessages = messagesBySessionRef.current?.[sessionId] || [];

                    // Convert backend messages to frontend format
                    const backendMessages = campaignData.messages.map((msg, index) => {
                      let text = msg.content;
                      let structuredContent = null;

                      if (msg.role === 'assistant' && typeof msg.content === 'object') {
                        structuredContent = {
                          narrative: msg.content.narrative || null,
                          answer: msg.content.answer || null,
                        };
                        text = msg.content.answer || msg.content.narrative || JSON.stringify(msg.content);
                      } else if (typeof msg.content !== 'string') {
                        text = JSON.stringify(msg.content);
                      }

                      return {
                        id: Date.now() + index,
                        message_id: msg.message_id,
                        text,
                        structuredContent,
                        sender: msg.role === 'assistant' ? 'dm' : msg.role,
                        timestamp: msg.timestamp || new Date().toISOString(),
                        isLocal: false
                      };
                    });

                    // Merge local messages with backend history
                    const mergedMessages = mergeMessages(localMessages, backendMessages);
                    setSessionMessages(sessionId, mergedMessages);
                    console.log('✅ Chat history merged:', mergedMessages.length, 'messages (', localMessages.length, 'local +', backendMessages.length, 'backend)');

                    // Clear streaming state after history has loaded
                    setDmIsNarrativeStreamingBySession((prev) => ({
                      ...prev,
                      [sessionId]: false,
                    }));
                    setDmIsResponseStreamingBySession((prev) => ({
                      ...prev,
                      [sessionId]: false,
                    }));
                    setDmStreamingNarrativeBySession((prev) => {
                      const updated = { ...prev };
                      delete updated[sessionId];
                      return updated;
                    });
                    setDmStreamingResponseBySession((prev) => {
                      const updated = { ...prev };
                      delete updated[sessionId];
                      return updated;
                    });
                  }
                })
                .catch((error) => {
                  console.error('Failed to reload chat history:', error);
                  // On error, still clear streaming state
                  setDmIsNarrativeStreamingBySession((prev) => ({
                    ...prev,
                    [sessionId]: false,
                  }));
                  setDmIsResponseStreamingBySession((prev) => ({
                    ...prev,
                    [sessionId]: false,
                  }));
                });
            }

            const existingMessages =
              messagesBySessionRef.current?.[sessionId] ?? [];
            const hadDmMessageAlready = existingMessages.some(
              (msg) => msg.sender === 'dm'
            );
            const isPendingInitial =
              pendingInitialNarrativeRef.current?.[sessionId] ?? false;
            const shouldShowResume =
              needsResponseFlag &&
              (!isPendingInitial || Boolean(dmAnswer) || hadDmMessageAlready);
            setSessionNeedsResume(sessionId, shouldShowResume);
            setSessionPlayerSuggestion(sessionId, null);
            if (dmAnswer) {
              setPendingInitialNarrative(sessionId, false);
            }

            if (sessionId === currentCampaignId) {
              setIsLoading(false);
            }
          }
        } catch (error) {
          console.error('🎭 DM WebSocket message parse error:', error);
        }
      };

      ws.onerror = (error) => {
        if (disposed) return;
        console.error('🎭 DM WebSocket error:', error);
        // Clear connecting flag on error
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
        setSessionPlayerSuggestion(sessionIdForSocket, null);

        if (dmWebSocketRef.current === ws) {
          dmWebSocketRef.current = null;
        } else {
          console.log('🎭 Stale DM socket closed, ignoring');
          return;
        }

        clearReconnectTimer();

        if ([4401, 4403, 4404].includes(closeCode)) {
          if (closeCode === 4401) {
            try {
              const refreshed = await refreshAccessToken?.();
              if (refreshed) {
                console.log('🎭 Refreshed token after 4401; reconnecting');
                connect();
              } else {
                console.log('🎭 Refresh token unavailable; prompted reauthentication');
              }
            } catch (e) {
              console.warn('🎭 Token refresh failed after 4401; not reconnecting');
            }
          }
          return;
        }

        const supersededByNewDm =
          closeCode === 1012 && closeReason === "Superseded DM connection";

        if (supersededByNewDm) {
          console.log("🎭 DM WebSocket superseded by another connection; skipping auto-reconnect.");
          return;
        }

        const shouldRetry =
          currentCampaignId &&
          dmWebSocketRef.current === null &&
          !disposed;

        if (shouldRetry) {
          const nextDelay = Math.min(retryDelay, 30000);
          retryDelay = Math.min(retryDelay * 2, 30000);

          console.log(`🎭 Will retry DM connection in ${nextDelay}ms`);
          dmReconnectTimerRef.current = setTimeout(() => {
            if (disposed) return;
            if (!dmWebSocketRef.current && currentCampaignId) {
              console.log('🎭 Retrying DM connection after disconnect');
              connect();
            }
          }, nextDelay);
        }
      };
    };

    connect();

    return cleanup;
  }, [
    currentCampaignId,
    enqueueAudio,
    getAccessTokenSilently,
    handleNewImage,
    markLastDmMessageHasAudio,
    playAudioRef,
    refreshAccessToken,
    setError,
    setIsLoading,
    setPendingInitialNarrative,
    setSessionHistoryInfo,
    setSessionMessages,
    setSessionNeedsResume,
    setSessionPlayerSuggestion,
    setSessionStructuredData,
    transformStructuredData,
    normalizeMessageText,
  ]);

  // Control panel ref for keyboard shortcuts
  const controlPanelRef = useRef(null);
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event) => {

      // Check for Ctrl+G (Generate Image)
      if (event.ctrlKey && (event.key === 'g' || event.key === 'G')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering image generation via keyboard shortcut');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGeneration) {
          controlPanelRef.current.triggerImageGeneration();
        } else {
          console.log('❌ Cannot trigger image generation - control panel ref not available');
        }
      }

      // Check for Alt+S (Generate Scene Image)
      if (event.altKey && (event.key === 's' || event.key === 'S')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering scene image generation via Alt+S');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('scene');
        }
      }

      // Check for Alt+C (Generate Character Image)
      if (event.altKey && (event.key === 'c' || event.key === 'C')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering character image generation via Alt+C');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('character');
        }
      }

      // Check for Alt+P (Generate Portrait Image)
      if (event.altKey && (event.key === 'p' || event.key === 'P')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering portrait image generation via Alt+P');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('portrait');
        }
      }

      // Check for Alt+I (Generate Item Image)
      if (event.altKey && (event.key === 'i' || event.key === 'I')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering item image generation via Alt+I');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('item');
        }
      }

      // Check for Alt+B (Generate Beast Image)
      if (event.altKey && (event.key === 'b' || event.key === 'B')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering beast image generation via Alt+B');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('beast');
        }
      }

      // Check for Alt+M (Generate Moment Image)
      if (event.altKey && (event.key === 'm' || event.key === 'M')) {
        event.preventDefault();
        event.stopPropagation();

        console.log('🎨 Triggering moment image generation via Alt+M');

        if (controlPanelRef.current && controlPanelRef.current.triggerImageGenerationWithType) {
          controlPanelRef.current.triggerImageGenerationWithType('moment');
        }
      }

      // Check for Ctrl+/ (Toggle Recording)
      if (event.ctrlKey && event.key === '/') {
        event.preventDefault();

        console.log('🎤 Toggling recording via keyboard shortcut');

        if (transcriptionRef.current) {
          transcriptionRef.current.toggleRecording();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Global error handler
  useEffect(() => {
    const handleGlobalError = (event) => {
      console.error("🚨 Global error caught:", event.error);
      setAppError({
        message: event.error?.message || 'Unknown error occurred',
        stack: event.error?.stack || '',
        type: 'Global Error'
      });
    };

    const handleUnhandledRejection = (event) => {
      console.error("🚨 Unhandled promise rejection:", event.reason);
      setAppError({
        message: event.reason?.message || 'Unhandled promise rejection',
        stack: event.reason?.stack || '',
        type: 'Promise Rejection'
      });
    };

    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleGlobalError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

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

  // Reset function to create blank campaign
  const resetApp = async () => {
    const confirmReset = window.confirm(
      "📋 Create Blank Campaign?\n\n" +
      "This will:\n" +
      "• Start a fresh campaign with no initial DM message\n" +
      "• Clear the current game state\n" +
      "• Allow you to paste in existing game state\n\n" +
      "Continue?"
    );
    
    if (!confirmReset) {
      return;
    }
    
    console.log("📋 Creating blank campaign...");
    setIsLoading(true);
    setError(null);
    setInputMessage("");
    clearAudioQueue(currentCampaignId);
    try {
      const result = await messageService.sendBlankCampaignRequest();
      console.log("📋 Blank campaign created:", result);
      
      if (result.sessionId) {
        const newSessionId = result.sessionId;
        const initialStructured = result.structuredData || result.structured_data || null;
        setCurrentCampaignId(newSessionId);
        localStorage.setItem('lastCampaignId', newSessionId);
        setSessionStructuredData(newSessionId, initialStructured);
        setSessionNeedsResume(newSessionId, false);
        setSessionHistoryInfo(newSessionId, null);
        setSessionPlayerSuggestion(newSessionId, null);

        if (initialStructured?.audio) {
          enqueueAudio(initialStructured.audio);
          markLastDmMessageHasAudio(newSessionId);
        }

        // Add a system message
        setSessionMessages(newSessionId, [{
          id: Date.now(),
          text: "📋 Blank campaign created. Paste your game state or start playing.",
          sender: 'system',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (error) {
      console.error("❌ Error creating blank campaign:", error);
      setError(`Failed to create blank campaign: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // const _handleNewCampaign = async () => {

  const handleSendMessage = async (messageText) => {
    // Handle both string messages and event objects
    let message;

    if (typeof messageText === 'string') {
      // Programmatic call with explicit message string - don't clear input
      message = messageText;
    } else if (messageText && typeof messageText === 'object' && messageText.preventDefault) {
      // It's an event object, use inputMessage
      messageText.preventDefault();
      message = inputMessage;
    } else {
      // Use inputMessage as fallback (e.g., Enter key)
      message = inputMessage;
    }

    // Ensure message is a string
    if (!message || typeof message !== 'string' || !message.trim()) return;
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
    const userMessage = {
      id: Date.now(),
      message_id: messageId,
      text: message,
      sender: 'user',
      timestamp: new Date().toISOString(),
      isLocal: true  // Mark as local until confirmed by backend
    };
    setSessionMessages(sessionId, (prev) => [...prev, userMessage]);
    
    try {
      console.log("🎮 Calling message service with campaign ID:", sessionId);
      const result = await messageService.sendMessage(message, sessionId);
      console.log("🎮 Message service result:", result);
      const structData = result.structuredData || result.structured_data || null;
      setSessionStructuredData(sessionId, structData);
      if (structData?.audio) {
        enqueueAudio(structData.audio);
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
        const timestamp = new Date().toISOString();
        const normalizedAnswer = normalizeMessageText(answerText);
        setSessionMessages(sessionId, (prev) => {
          const hasDuplicate = prev.some((msg) => {
            if (msg.sender !== 'dm') {
              return false;
            }
            const candidateText = normalizeMessageText(msg.text);
            if (candidateText !== normalizedAnswer) {
              return false;
            }
            if (!msg.timestamp) {
              return false;
            }
            return new Date(msg.timestamp).getTime() === new Date(timestamp).getTime();
          });

          if (hasDuplicate) {
            return prev;
          }

          const dmMessage = {
            id: Date.now() + 1,
            text: answerText,
            sender: 'dm',
            timestamp,
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
          };
          return [...prev, dmMessage];
        });
      }
    } catch (error) {
      console.error("❌ Error in handleSendMessage:", error);
      setError(`Failed to send message: ${error.message}`);
      // Add error message to chat
      const errorMessage = {
        id: Date.now() + 1,
        text: `Error: ${error.message}`,
        sender: 'system',
        timestamp: new Date().toISOString()
      };
      setSessionMessages(sessionId, (prev) => [...prev, errorMessage]);
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

  const handleSelectCampaign = useCallback(async (campaignId, isNewCampaign = false) => {
    console.log('🎮 Selecting campaign:', campaignId, 'isNew:', isNewCampaign);
    const previousCampaignId = currentCampaignId;
    setCurrentCampaignId(campaignId);
    setShowCampaignList(false);
    if (campaignId) {
      clearAudioQueue(campaignId);
    }

    if (!campaignId) {
      return;
    }
    const sessionId = campaignId;

    if (isNewCampaign) {
      setPendingInitialNarrative(sessionId, true);
      setSessionNeedsResume(sessionId, false);
      setIsLoading(true);
    } else {
      setPendingInitialNarrative(sessionId, false);
      setIsLoading(false);
    }

    await loadRecentImages(campaignId);

    try {
      const data = await apiService.loadSimpleCampaign(campaignId);
      if (!data) {
        console.error('Failed to load simple campaign');
        setError('Failed to load simple campaign');
        return;
      }

      console.log('🎮 Loaded simple campaign:', data);

      if (!data.success || !data.activated) {
        console.error('Failed to activate simple campaign');
        setError('Failed to activate simple campaign');
        return;
      }

      const structuredData = data.structured_data;
      if (structuredData) {
        console.log('🎮 Received structured data from simple campaign:', structuredData);
        const transformedData = transformStructuredData(structuredData, {
          needsResponse: Boolean(data.needs_response),
          sessionId,
        });
        if (transformedData) {
          setSessionStructuredData(sessionId, transformedData);
          if (transformedData.audio) {
            enqueueAudio(transformedData.audio);
            markLastDmMessageHasAudio(sessionId);
          }
        } else {
          setSessionStructuredData(sessionId, null);
        }
      } else {
        setSessionStructuredData(sessionId, null);
      }

      if (data.history_info) {
        setSessionHistoryInfo(sessionId, data.history_info);
        setTimeout(() => setSessionHistoryInfo(sessionId, null), 10000);
      } else {
        setSessionHistoryInfo(sessionId, null);
      }

      let convertedMessages = [];
      if (data.messages) {
        convertedMessages = data.messages.map((msg, index) => {
          let text = msg.content;
          let structuredContent = null;

          if (msg.role === 'assistant' && typeof msg.content === 'object') {
            // Store both narrative and answer in structured content
            structuredContent = {
              narrative: msg.content.narrative || null,
              answer: msg.content.answer || null,
            };
            // Fallback text for backwards compatibility
            text = msg.content.answer || msg.content.narrative || JSON.stringify(msg.content);
          } else if (typeof msg.content !== 'string') {
            text = JSON.stringify(msg.content);
          }

          return {
            id: Date.now() + index,
            text,
            structuredContent,
            sender: msg.role === 'assistant' ? 'dm' : msg.role,
            timestamp: msg.timestamp || new Date().toISOString(),
          };
        });
        setSessionMessages(sessionId, convertedMessages);
      } else {
        setSessionMessages(sessionId, []);
      }

      if (!isNewCampaign) {
        const systemMessage = {
          id: Date.now() + convertedMessages.length,
          text: `Loaded simple campaign: ${campaignId} (${data.message_count} messages)${structuredData ? ' - Game state loaded' : ''}`,
          sender: 'system',
          timestamp: new Date().toISOString(),
        };
        setSessionMessages(sessionId, (prev) => [systemMessage, ...prev]);
      }

      setSessionPlayerSuggestion(sessionId, null);

      const hasDmMessage = convertedMessages.some((msg) => msg.sender === 'dm');
      if (isNewCampaign && !hasDmMessage) {
        setSessionNeedsResume(sessionId, false);
        setPendingInitialNarrative(sessionId, true);
        setIsLoading(true);
      } else {
        setSessionNeedsResume(
          sessionId,
          Boolean(data.needs_response) &&
            (hasDmMessage || !isNewCampaign)
        );
        setPendingInitialNarrative(sessionId, false);
        setIsLoading(false);
      }
    } catch (error) {
      console.error('Error loading simple campaign:', error);
      setError(`Failed to load simple campaign: ${error.message}`);
      if (error.message?.includes('404')) {
        localStorage.removeItem('lastCampaignId');
      }
      if (!previousCampaignId) {
        setCurrentCampaignId(null);
      } else {
        setCurrentCampaignId(previousCampaignId);
        localStorage.setItem('lastCampaignId', previousCampaignId);
      }
      setPendingInitialNarrative(sessionId, false);
      setIsLoading(false);
    }
  }, [
    currentCampaignId,
    enqueueAudio,
    handleNewImage,
    loadRecentImages,
    markLastDmMessageHasAudio,
    setPendingInitialNarrative,
    setSessionNeedsResume,
    setSessionMessages,
    setSessionStructuredData,
    setSessionHistoryInfo,
    setSessionPlayerSuggestion,
    setIsLoading,
    setError,
    transformStructuredData,
  ]);

  const handleArenaQuickStart = async () => {
    try {
      setIsLoading(true);
      setError(null);
      console.log('Starting arena quick combat...');

      // Call the arena quick-start endpoint
      const response = await apiService.makeRequest('/api/arena/quick-start', {
        player_count: 2,
        npc_count: 2,
        difficulty: 'medium'
      });

      if (response.success && response.campaign_id) {
        console.log('Arena campaign created:', response.campaign_id);

        // Load the created campaign
        await handleSelectCampaign(response.campaign_id, true);

        // Show success message
        const successMsg = response.message || 'Arena combat initiated!';
        console.log(successMsg);
      } else {
        throw new Error('Failed to create arena campaign');
      }
    } catch (error) {
      console.error('Arena quick-start error:', error);
      setError(`Failed to start arena combat: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchInviteToken = useCallback(
    async (regenerate = false) => {
      if (!currentCampaignId) {
        setShareState((prev) => ({
          ...prev,
          loading: false,
          token: '',
          expiresAt: null,
          error: 'Select a campaign before sharing.',
          copied: false
        }));
        return;
      }
      setShareState((prev) => ({
        ...prev,
        loading: true,
        error: null,
        copied: false
      }));
      try {
        const response = await apiService.createSessionInvite(currentCampaignId, {
          regenerate,
        });
        setShareState({
          loading: false,
          token: response.invite_token,
          expiresAt: response.expires_at || null,
          error: null,
          copied: false,
        });
      } catch (err) {
        setShareState((prev) => ({
          ...prev,
          loading: false,
          token: '',
          expiresAt: null,
          error: err.message || 'Failed to create invite token',
          copied: false,
        }));
      }
    },
    [currentCampaignId]
  );

  useEffect(() => {
    if (!showShareModal) {
      return;
    }
    fetchInviteToken(false);
  }, [showShareModal, fetchInviteToken]);

  const handleCopyInviteLink = useCallback(async () => {
    if (!shareState.token) {
      return;
    }
    try {
      const inviteLink = `${window.location.origin}/player?invite=${shareState.token}`;
      await navigator.clipboard.writeText(inviteLink);
      setShareState((prev) => ({ ...prev, copied: true }));
      setInfoBanner('Invite link copied to clipboard.');
    } catch (err) {
      setShareState((prev) => ({
        ...prev,
        error: 'Failed to copy invite link',
        copied: false,
      }));
    }
  }, [shareState.token]);

  const handleAddContext = async (contextText) => {
    if (!currentCampaignId) {
      setError('No active campaign selected. Start a campaign before adding context.');
      return;
    }
    const sessionId = currentCampaignId;
    try {
      // Add context as a user message that's marked as context-only
      const contextMessage = {
        id: Date.now(),
        text: `[CONTEXT] ${contextText}`,
        sender: 'user',
        timestamp: new Date().toISOString(),
        isContext: true
      };
      setSessionMessages(sessionId, (prev) => [...prev, contextMessage]);
      
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

  // Function moved earlier in file to fix hoisting issue

  // Load last campaign from localStorage OR auto-load newest campaign
  useEffect(() => {
    const autoLoadCampaign = async () => {
      console.log('🎮 AUTO-LOAD: Starting campaign auto-load logic');

      // Load recent images on startup
      await loadRecentImages();

      // Clear any stale loading flag from previous session
      const wasLoading = sessionStorage.getItem('campaignLoadInProgress');
      if (wasLoading === 'true') {
        console.log('🎮 AUTO-LOAD: Clearing stale loading flag from previous session');
        sessionStorage.removeItem('campaignLoadInProgress');
      }

      // Mark that we're starting a load to prevent infinite loops
      sessionStorage.setItem('campaignLoadInProgress', 'true');
      console.log('🎮 AUTO-LOAD: Marked load as in progress');

      const lastCampaignId = localStorage.getItem('lastCampaignId');
      console.log('🎮 AUTO-LOAD: Last campaign ID from localStorage:', lastCampaignId);

      if (lastCampaignId) {
        // Try to restore last played campaign
        console.log('🎮 AUTO-LOAD: Attempting to restore last campaign:', lastCampaignId);
        try {
          await handleSelectCampaign(lastCampaignId);
          console.log('🎮 AUTO-LOAD: Successfully restored last campaign');
          sessionStorage.removeItem('campaignLoadInProgress');
          return; // Success, we're done
        } catch (error) {
          console.error('🎮 AUTO-LOAD: Failed to restore campaign:', error);
          localStorage.removeItem('lastCampaignId');
          // Continue to auto-load newest campaign
        }
      }

      // No last campaign or it failed - fetch newest campaign
      try {
        console.log('🎮 AUTO-LOAD: Fetching campaigns list to auto-load newest...');
        let data = await apiService.listSimpleCampaigns({ ownedOnly: true });
        console.log('🎮 AUTO-LOAD: Received campaigns data (ownedOnly):', data);

        // Fallback: if no owned campaigns found, try unfiltered list
        if (!data?.campaigns || data.campaigns.length === 0) {
          console.log('🎮 AUTO-LOAD: No owned campaigns found, trying unfiltered list...');
          try {
            data = await apiService.listSimpleCampaigns({ ownedOnly: false });
            console.log('🎮 AUTO-LOAD: Received campaigns data (unfiltered):', data);
          } catch (fallbackErr) {
            console.error('🎮 AUTO-LOAD: Unfiltered campaigns fetch failed:', fallbackErr);
          }
        }

        if (data?.campaigns && data.campaigns.length > 0) {
          console.log(`🎮 AUTO-LOAD: Found ${data.campaigns.length} campaigns`);

          // Sort by last_played (most recent first)
          const sortedCampaigns = [...data.campaigns].sort((a, b) => {
            const aTime = new Date(a.last_played || a.updated_at || a.created_at || 0).getTime();
            const bTime = new Date(b.last_played || b.updated_at || b.created_at || 0).getTime();
            return bTime - aTime; // Descending order (newest first)
          });

          const newestCampaign = sortedCampaigns[0];
          console.log('🎮 AUTO-LOAD: Auto-loading newest campaign:', newestCampaign);
          await handleSelectCampaign(newestCampaign.id);
          console.log('🎮 AUTO-LOAD: Successfully loaded newest campaign');
        } else {
          console.log('🎮 AUTO-LOAD: No campaigns found to auto-load');
        }
      } catch (error) {
        console.error('🎮 AUTO-LOAD: Failed to auto-load newest campaign:', error);
      } finally {
        // Clear the in-progress flag when done (success or failure)
        sessionStorage.removeItem('campaignLoadInProgress');
        console.log('🎮 AUTO-LOAD: Cleared in-progress flag');
      }
    };

    // Small delay to ensure component is fully mounted and auth token is ready
    const timer = setTimeout(autoLoadCampaign, 1000);
    return () => clearTimeout(timer);
  }, [handleSelectCampaign, loadRecentImages]); // Include dependencies to ensure they're ready

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

    const joinSharedSession = async () => {
      try {
        setIsLoading(true);
        const response = await apiService.joinSessionByInvite(inviteToken);
        setInfoBanner('Successfully joined shared session.');
        await handleSelectCampaign(response.session_id, true);
      } catch (err) {
        console.error('Failed to join session via invite:', err);
        setError(`Failed to join shared session: ${err.message}`);
      } finally {
        setIsLoading(false);
      }
    };

    joinSharedSession();
  }, [handleSelectCampaign]);

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

  const inviteLink = shareState.token && typeof window !== 'undefined'
    ? `${window.location.origin}/player?invite=${shareState.token}`
    : '';

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
        <header className="bg-gaia-border px-3 py-1 border-b-2 border-gaia-border flex justify-between items-center">
          <h1 className="text-sm font-semibold text-gaia-success m-0">Fable Table</h1>
          <div className="flex gap-2 items-center">
            <UnifiedLoadingIndicator />
            {currentCampaignId && <SettingsButton onClick={() => setIsSettingsModalOpen(true)} />}
            <button onClick={() => setShowCampaignList(true)} className="px-3 py-1 bg-indigo-500 text-white rounded text-xs hover:bg-indigo-600 transition-colors font-medium">
              📋 Campaigns
            </button>
            <button onClick={() => setShowCampaignSetup(true)} className="px-3 py-1 bg-gaia-success text-black rounded text-xs hover:bg-green-500 transition-colors font-semibold">
              🎲 New Campaign
            </button>
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
                  dmWebSocket={dmWebSocketRef.current}
                />
                {(() => {
                  const c = campaigns.find(c => c.id === currentCampaignId);
                  const name = c?.name || currentCampaignId;
                  return (
                    <span className="text-xs text-gray-400 font-mono">Campaign: {name}</span>
                  );
                })()}
              </>
            )}
            <UserMenu />
          </div>
        </header>

        {/* Error display */}
        {error && (
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
              <GameDashboard
              ref={gameDashboardRef}
              latestStructuredData={latestStructuredData}
              onImageGenerated={handleImageClick}
              campaignId={currentCampaignId}
              selectedVoice={selectedVoice}
              playerSuggestion={playerSuggestion}
              onCopyToChat={handleCopyToChat}
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
              showAudioRecorder={showAudioRecorder}
              onToggleAudioRecorder={() => setShowAudioRecorder(!showAudioRecorder)}
              chatInputRef={chatInputRef}
              />
            </div>
          </div>

        </main>

        <AudioPlayerBar sessionId={currentCampaignId} />

        {/* Floating Transcription Modal - positioned to the right of the Close button */}
        {showAudioRecorder && (
          <div className="fixed bottom-4 left-[470px] z-[1000] transition-all duration-300 animate-in slide-in-from-left fade-in">
            <ContinuousTranscription
              ref={transcriptionRef}
              onSendMessage={handleSendMessage}
              isTTSPlaying={isTTSPlaying}
              onRecordingStateChange={setVoiceRecordingState}
              onVoiceActivityChange={setVoiceActivityActive}
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
          onCampaignsLoaded={setCampaigns}
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

export default App;
