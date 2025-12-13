import React, { useState, useEffect, useRef, useCallback } from 'react';
import PlayerAndTurnList from '../PlayerAndTurnList/PlayerAndTurnList';
import PlayerNarrativeView from './PlayerNarrativeView/PlayerNarrativeView.jsx';
import PlayerControls from './PlayerControls/PlayerControls.jsx';
import CombatStatusView from '../CombatStatusView.jsx';
import './PlayerView.css';

const PlayerView = ({
  campaignId,
  playerId,
  characterData,
  latestStructuredData,
  campaignMessages = [],
  turns = [],
  imageRefreshTrigger,
  onPlayerAction,
  onLoadCampaignData,
  streamingNarrative = '',
  streamingResponse = '',
  isNarrativeStreaming = false,
  isResponseStreaming = false,
  // Event-driven processing indicator (set by turn_started socket event)
  isProcessing = false,
  // Voice input props
  audioPermissionState = 'pending',
  userEmail = null,
  isTranscribing = false,
  onToggleTranscription = null,
  voiceActivityLevel = 0,
  // Collaborative editing props
  collabWebSocket = null,
  collabPlayerId = '',
  collabPlayerName = '',
  collabAllPlayers = [],
  collabIsConnected = false,
  collabEditorRef = null,
  // Personalized player options props
  currentCharacterId = null,
  isActivePlayer = true,
  pendingObservations = [],
  onCopyObservation = null,
  // Secondary player observation submission
  onSubmitObservation = null,
  // Audio unlock props (for iOS mobile support)
  userAudioBlocked = false,
  onUnlockUserAudio = null,
}) => {
  // Debug: Log observations props received by PlayerView
  console.log('👁️ PlayerView render:', {
    isActivePlayer,
    pendingObservationsCount: pendingObservations?.length,
    hasOnCopyObservation: !!onCopyObservation
  });

  const [error, setError] = useState(null);
  const [currentCharacter] = useState(characterData);
  const [gameState, setGameState] = useState(latestStructuredData);
  const [showCombatStatus, setShowCombatStatus] = useState(false);
  const userViewOverrideRef = useRef(false);

  // Tab state management for auto-switching based on streaming
  const [activeTab, setActiveTab] = useState('voice');
  const [highlightInteract, setHighlightInteract] = useState(false);
  const wasStreamingRef = useRef(false);

  // Check if any turn is currently streaming (from turn-based events)
  const isAnyTurnStreaming = turns.some(turn => turn.isStreaming);

  // Determine if currently streaming - check multiple event sources
  // 1. isProcessing: Set immediately by turn_started socket event (most reliable for remote clients)
  // 2. Turn-based streaming: turn_message events set turn.isStreaming
  // 3. Legacy streaming: narrative_chunk/player_response_chunk events set isNarrativeStreaming/isResponseStreaming
  const isCurrentlyStreaming = isProcessing || isNarrativeStreaming || isResponseStreaming || isAnyTurnStreaming;

  // Debug logging for streaming state
  console.log('🔄 PlayerView streaming state:', {
    isProcessing,
    isNarrativeStreaming,
    isResponseStreaming,
    isAnyTurnStreaming,
    isCurrentlyStreaming,
    wasStreaming: wasStreamingRef.current,
    activeTab,
  });

  // Auto-switch to history tab when streaming starts
  useEffect(() => {
    console.log('🔄 PlayerView useEffect triggered:', { isCurrentlyStreaming, wasStreaming: wasStreamingRef.current });
    if (isCurrentlyStreaming && !wasStreamingRef.current) {
      // Streaming just started - switch to history tab
      console.log('🔄 Switching to history tab');
      setActiveTab('history');
      setHighlightInteract(false);
    } else if (!isCurrentlyStreaming && wasStreamingRef.current) {
      // Streaming just ended - highlight interact tab
      console.log('🔄 Highlighting interact tab');
      setHighlightInteract(true);
    }
    wasStreamingRef.current = isCurrentlyStreaming;
  }, [isCurrentlyStreaming]);

  // Clear highlight when user switches to interact tab
  const handleTabChange = useCallback((tabId) => {
    setActiveTab(tabId);
    if (tabId === 'voice') {
      setHighlightInteract(false);
    }
  }, []);

  const hasCombatStatusData = (state) => {
    if (!state) {
      return false;
    }

    const nextInteractionType = state.next_interaction_type
      || state.original_data?.next_interaction_type;
    if (typeof nextInteractionType === 'string' && nextInteractionType.toLowerCase() === 'default') {
      return false;
    }

    if (state.is_combat_active === false) {
      return false;
    }

    if (!state.combat_status) {
      return false;
    }

    // Check if combat_state indicates combat has ended (is_active = false)
    // This handles the case where combat ends (VICTORIOUS/DEFEATED) but combat_status still has data
    if (state.combat_state && state.combat_state.is_active === false) {
      console.log('🎮 Combat ended (is_active=false), hiding combat view');
      return false;
    }

    const status = state.combat_status;

    if (typeof status === 'string') {
      const trimmed = status.trim();
      if (!trimmed) {
        return false;
      }
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
          const parsed = JSON.parse(trimmed);
          return hasCombatStatusData({ combat_status: parsed, combat_state: state.combat_state });
        } catch (error) {
          console.warn('Failed to parse combat status string:', status, error);
          return false;
        }
      }
      return false;
    }

    if (Array.isArray(status)) {
      return status.length > 0;
    }

    if (typeof status === 'object') {
      return Object.keys(status).length > 0;
    }

    return false;
  };

  // Update game state when new structured data arrives
  useEffect(() => {
    if (latestStructuredData) {
      console.log('🎮 PlayerView received structured data:', latestStructuredData);
      console.log('🎮 Combat status:', latestStructuredData.combat_status);
      setGameState(latestStructuredData);
    }
  }, [latestStructuredData]);

  const combatStatusAvailable = hasCombatStatusData(gameState);

  useEffect(() => {
    if (!combatStatusAvailable) {
      if (showCombatStatus) {
        setShowCombatStatus(false);
      }
      if (userViewOverrideRef.current) {
        userViewOverrideRef.current = false;
      }
      return;
    }

    if (!userViewOverrideRef.current && !showCombatStatus) {
      setShowCombatStatus(true);
    }
  }, [combatStatusAvailable, showCombatStatus]);

  // Handle player actions (voice input, dice rolls, etc.)
  const handlePlayerAction = (action) => {
    if (!campaignId) {
      setError('No campaign ID provided');
      return;
    }

    // Send suggestion to parent (PlayerPage) instead of calling LLM
    if (onPlayerAction) {
      onPlayerAction(action);
    }

    // Show feedback to player
    console.log('📤 Player action sent as suggestion:', action);
  };

  // If no character data, show character creation/selection
  if (!currentCharacter) {
    return (
      <div className="player-view" data-testid="player-view">
        <div className="player-view-loading">
          <div className="loading-icon">🧙‍♂️</div>
          <h2>Create Your Character</h2>
          <p>Please create or select a character to join the campaign.</p>
          {error && (
            <div className="error-message" data-testid="error-message">
              ⚠️ {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="player-view" data-testid="player-view">
      {/* Error Display */}
      {error && (
        <div className="player-error" data-testid="error-message">
          <span className="error-icon">⚠️</span>
          <span className="error-text">{error}</span>
          <button
            className="error-dismiss"
            onClick={() => setError(null)}
          >
            ✕
          </button>
        </div>
      )}


      {/* Main Player View Layout */}
      <div className="player-view-grid">

        {/* Left Panel: Party List or Combat Status */}
        <div className="player-view-character" data-testid="character-sheet">
          {/* Toggle button for combat status - only show if combat_status exists */}
          {combatStatusAvailable && (
            <div className="view-toggle-container">
              <button
                className={`view-toggle-button ${!showCombatStatus ? 'active' : ''}`}
                onClick={() => {
                  userViewOverrideRef.current = true;
                  setShowCombatStatus(false);
                }}
              >
                👥 Party
              </button>
              <button
                className={`view-toggle-button ${showCombatStatus ? 'active' : ''}`}
                onClick={() => {
                  userViewOverrideRef.current = false;
                  setShowCombatStatus(true);
                }}
              >
                ⚔️ Combat
              </button>
            </div>
          )}

          {/* Conditional rendering based on toggle */}
          {showCombatStatus && gameState?.combat_status ? (
            <CombatStatusView
              combatStatus={gameState.combat_status}
              turnInfo={gameState.turn_info}
              showHeader={false}
            />
          ) : (
            <PlayerAndTurnList
              campaignId={campaignId}
              currentPlayerId={playerId}
              turnInfo={gameState?.turn_info}
              compact={true}
            />
          )}
        </div>

        {/* Center Panel: Narrative View - shows scene image with navigation */}
        <div className="player-view-narrative" data-testid="player-narrative">
          <PlayerNarrativeView
            structuredData={gameState}
            campaignId={campaignId}
            isLoading={isCurrentlyStreaming}
          />
        </div>

        {/* Bottom Panel: Player Controls */}
        <div className="player-view-controls" data-testid="player-controls">
          <PlayerControls
            campaignId={campaignId}
            structuredData={gameState}
            campaignMessages={campaignMessages}
            imageRefreshTrigger={imageRefreshTrigger}
            onPlayerAction={handlePlayerAction}
            onVoiceInput={(text) => handlePlayerAction({ message: text })}
            voiceActivityLevel={voiceActivityLevel}
            onLoadCampaignData={onLoadCampaignData}
            // Voice input props
            audioPermissionState={audioPermissionState}
            userEmail={userEmail}
            isTranscribing={isTranscribing}
            onToggleTranscription={onToggleTranscription}
            // Collaborative editing props
            collabWebSocket={collabWebSocket}
            collabPlayerId={collabPlayerId}
            collabPlayerName={collabPlayerName}
            collabAllPlayers={collabAllPlayers}
            collabIsConnected={collabIsConnected}
            // Ref for voice transcription integration
            collabEditorRef={collabEditorRef}
            // Personalized player options props
            currentCharacterId={currentCharacterId}
            isActivePlayer={isActivePlayer}
            pendingObservations={pendingObservations}
            onCopyObservation={onCopyObservation}
            // Secondary player observation submission
            onSubmitObservation={onSubmitObservation}
            // Audio unlock props (for inline indicator)
            userAudioBlocked={userAudioBlocked}
            onUnlockUserAudio={onUnlockUserAudio}
            // Turn-based history props
            turns={turns}
            streamingNarrative={streamingNarrative}
            streamingResponse={streamingResponse}
            isNarrativeStreaming={isNarrativeStreaming}
            isResponseStreaming={isResponseStreaming}
            // Controlled tab state
            activeTab={activeTab}
            onTabChange={handleTabChange}
            highlightInteract={highlightInteract}
          />
        </div>
      </div>
    </div>
  );
};

export default PlayerView;
