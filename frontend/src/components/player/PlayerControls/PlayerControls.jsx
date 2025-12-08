import { useState, useEffect, useMemo, useCallback } from 'react';
import CollaborativeStackedEditor from '../../collaborative/CollaborativeStackedEditor.jsx';
import MediaGallery from './MediaGallery.jsx';
import './PlayerControls.css';

const PlayerControls = ({
  campaignId,
  structuredData,
  campaignMessages = [],
  imageRefreshTrigger,
  onPlayerAction,
  onVoiceInput,
  isTranscribing = false,
  voiceActivityLevel = 0,
  onLoadCampaignData,
  audioPermissionState = 'pending',
  onToggleTranscription = null,
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
  onSubmitObservation = null
}) => {
  const [activeTab, setActiveTab] = useState('voice');
  const [recentMedia, setRecentMedia] = useState([]);
  const [collabEditorConnected, setCollabEditorConnected] = useState(false);
  // Brief confirmation popup for observation submission
  const [submissionConfirmation, setSubmissionConfirmation] = useState(null);
  // Track selected observations (for active player to include in submission)
  const [selectedObservationIds, setSelectedObservationIds] = useState(new Set());

  // Debug: Log observations props
  console.log('👁️ PlayerControls render:', {
    isActivePlayer,
    pendingObservationsCount: pendingObservations?.length,
    pendingObservations,
    hasOnCopyObservation: !!onCopyObservation
  });

  // Note: Ctrl+Enter is handled by CollaborativeStackedEditor directly

  // Handle voice input
  const handleVoiceSubmit = (text) => {
    if (onVoiceInput) {
      onVoiceInput(text);
    }
  };

  // Handle tab switching
  const handleTabSwitch = (tabId) => {
    setActiveTab(tabId);
  };

  // Fetch recent media
  useEffect(() => {
    // TODO: Implement media fetching from API
    // For now, use placeholder data
    setRecentMedia([
      {
        id: 1,
        type: 'scene',
        url: '/api/placeholder-scene.jpg',
        description: 'Tavern interior with warm lighting'
      },
      {
        id: 2,
        type: 'character',
        url: '/api/placeholder-character.jpg',
        description: 'Mysterious hooded figure'
      }
    ]);
  }, [campaignId]);

  // Toggle observation selection (for active player)
  const toggleObservationSelection = useCallback((observationId) => {
    setSelectedObservationIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(observationId)) {
        newSet.delete(observationId);
      } else {
        newSet.add(observationId);
      }
      return newSet;
    });
  }, []);

  // Get selected observations formatted for submission
  const getSelectedObservationsText = useCallback(() => {
    if (!pendingObservations || selectedObservationIds.size === 0) return '';

    const selected = pendingObservations
      .filter(obs => !obs.included_in_turn)
      .filter(obs => selectedObservationIds.has(`${obs.character_id}-${obs.observation_text}`));

    if (selected.length === 0) return '';

    return selected
      .map(obs => `[${obs.character_name} observes]: ${obs.observation_text}`)
      .join('\n');
  }, [pendingObservations, selectedObservationIds]);

  // Handle player option selection
  const handlePlayerOption = useCallback((option) => {
    // Secondary players: clicking an option directly submits it as an observation
    if (!isActivePlayer && onSubmitObservation) {
      console.log('👁️ Secondary player clicked option, submitting as observation:', option);
      onSubmitObservation(option.trim());
      // Show brief confirmation popup
      setSubmissionConfirmation({
        text: option.length > 50 ? option.substring(0, 50) + '...' : option,
        timestamp: Date.now()
      });
      // Auto-hide after 2 seconds
      setTimeout(() => setSubmissionConfirmation(null), 2000);
      return;
    }

    // Active player: insert into editor (existing behavior)
    if (collabEditorRef?.current) {
      collabEditorRef.current.insertText(option);
    } else {
      console.warn('Collaborative editor not ready');
    }
  }, [isActivePlayer, onSubmitObservation, collabEditorRef]);

  // Handle collaborative text submission
  const handleCollabSubmit = useCallback(async (text) => {
    console.log('🎯 handleCollabSubmit called', {
      textLength: text?.length,
      isActivePlayer,
      hasOnSubmitObservation: !!onSubmitObservation,
      hasOnPlayerAction: !!onPlayerAction
    });

    if (!text || !text.trim()) {
      console.log('🎯 handleCollabSubmit: empty text, returning');
      return;
    }

    // Secondary players submit observations instead of direct messages
    if (!isActivePlayer && onSubmitObservation) {
      console.log('🎯 Submitting as observation (secondary player)');
      onSubmitObservation(text.trim());
      // Clear the editor after submission
      if (collabEditorRef?.current?.clearMySection) {
        collabEditorRef.current.clearMySection();
      }
      return;
    }

    // Active player submits normally
    if (onPlayerAction) {
      console.log('🎯 Submitting as player action (active player)');

      // Include selected observations in the submission
      const observationsText = getSelectedObservationsText();
      let finalMessage = text.trim();
      if (observationsText) {
        finalMessage = `${finalMessage}\n\n${observationsText}`;
        console.log('🎯 Including selected observations in submission');
      }

      try {
        await onPlayerAction({
          type: 'player_message',
          message: finalMessage
        });
        // Clear the editor after successful submission
        if (collabEditorRef?.current?.clearMySection) {
          collabEditorRef.current.clearMySection();
        }
        // Clear selected observations after successful submission
        setSelectedObservationIds(new Set());
        console.log('🎯 Player action submitted and editor cleared');
      } catch (err) {
        console.error('🎯 Failed to submit player action:', err);
      }
    } else {
      console.log('🎯 No onPlayerAction handler available');
    }
  }, [onPlayerAction, isActivePlayer, onSubmitObservation, collabEditorRef, getSelectedObservationsText]);

  // Determine if it's this player's turn (for now, always true since we don't have turn info)
  // TODO: Wire up to actual turn info from structuredData.turn_info
  const isMyTurn = true;

  // Check if combat is active - hide suggestions during combat (combat has its own action system)
  const isInCombat = useMemo(() => {
    if (!structuredData) return false;
    const combatStatus = structuredData.combat_status;
    if (!combatStatus) return false;
    // Check if combat_status has meaningful content (not empty object/array/string)
    if (typeof combatStatus === 'object') {
      return Array.isArray(combatStatus) ? combatStatus.length > 0 : Object.keys(combatStatus).length > 0;
    }
    if (typeof combatStatus === 'string') {
      return combatStatus.trim().length > 0;
    }
    return false;
  }, [structuredData]);

  // Parse player options from structuredData
  // Priority: personalized_player_options > player_options > turn
  const playerOptions = useMemo(() => {
    if (!structuredData) return [];

    // Check for personalized options first (if we have a character ID)
    const personalizedOptions = structuredData.personalized_player_options;
    if (personalizedOptions && personalizedOptions.characters) {
      const candidateIds = [
        currentCharacterId,
        personalizedOptions.active_character_id,
        ...Object.keys(personalizedOptions.characters || {})
      ].filter(Boolean);

      const resolvedId = candidateIds.find(id => personalizedOptions.characters[id]);
      if (resolvedId) {
        const charOptions = personalizedOptions.characters[resolvedId];
        if (charOptions?.options && Array.isArray(charOptions.options)) {
          return charOptions.options.filter(option => option && option.trim().length > 0);
        }
      }
    }

    // Fall back to legacy format
    const optionsData = structuredData.player_options || structuredData.turn || '';

    // Handle both array and string formats
    let parsed = [];
    if (Array.isArray(optionsData)) {
      // Backend sent array - use it directly
      parsed = optionsData.filter(option => option && option.trim().length > 0);
    } else if (typeof optionsData === 'string' && optionsData.length > 0) {
      // Backend sent string - split by newlines
      parsed = optionsData
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0);
    }

    return parsed;
  }, [structuredData, currentCharacterId]);

  const tabs = useMemo(() => [
    {
      id: 'voice',
      name: 'Interact',
      icon: '🎤',
      component: (
        <div className="interact-tab-content">
          {collabWebSocket ? (
            <>
              <div className="collab-editor-wrapper">
                <div className="collab-editor-with-indicator">
                  <span
                    className={`connection-dot-player ${collabEditorConnected ? 'connected' : 'disconnected'}`}
                    title={collabEditorConnected ? 'Connected' : 'Disconnected'}
                  />
                  <CollaborativeStackedEditor
                    ref={collabEditorRef}
                    sessionId={campaignId}
                    playerId={collabPlayerId}
                    characterName={collabPlayerName}
                    allPlayers={collabAllPlayers}
                    isMyTurn={isMyTurn}
                    websocket={collabWebSocket}
                    onSubmit={handleCollabSubmit}
                    showHeader={false}
                    onConnectionChange={setCollabEditorConnected}
                    layout="grid"
                    isTranscribing={isTranscribing}
                    onToggleTranscription={onToggleTranscription}
                    showMicButton={audioPermissionState === 'granted'}
                    voiceLevel={voiceActivityLevel}
                    showInlineSubmit={isActivePlayer}
                  />
                </div>
              </div>

              {/* Observation submission confirmation popup */}
              {submissionConfirmation && (
                <div className="observation-confirmation-popup">
                  <span className="observation-confirmation-icon">✓</span>
                  <span className="observation-confirmation-text">
                    Shared with active player
                  </span>
                </div>
              )}
            </>
          ) : (
            <div className="collab-waiting">
              <p>Connecting to collaborative session...</p>
            </div>
          )}

          {/* Pending Observations (shown to active player as checkboxes) */}
          {isActivePlayer && pendingObservations && pendingObservations.length > 0 && (() => {
            // Deduplicate observations by character_id + observation_text
            const seen = new Set();
            const uniqueObservations = pendingObservations
              .filter(obs => !obs.included_in_turn)
              .filter(obs => {
                const key = `${obs.character_id}-${obs.observation_text}`;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
              });

            if (uniqueObservations.length === 0) return null;

            return (
              <div className="pending-observations-section">
                <div className="observations-header">
                  <span className="observations-icon">👁️</span>
                  <span className="observations-title">Party Observations</span>
                  <span className="observations-count">{uniqueObservations.length}</span>
                  {selectedObservationIds.size > 0 && (
                    <span className="observations-selected-badge">
                      {selectedObservationIds.size} selected
                    </span>
                  )}
                </div>
                <div className="observations-hint">Select observations to include with your action</div>
                <div className="observations-list">
                  {uniqueObservations.map((observation, index) => {
                    const obsId = `${observation.character_id}-${observation.observation_text}`;
                    const isSelected = selectedObservationIds.has(obsId);
                    return (
                      <label
                        key={obsId}
                        className={`observation-item observation-item-selectable ${isSelected ? 'observation-item-selected' : ''}`}
                      >
                        <input
                          type="checkbox"
                          className="observation-checkbox"
                          checked={isSelected}
                          onChange={() => toggleObservationSelection(obsId)}
                        />
                        <span className="observation-content">
                          <span className="observation-author">{observation.character_name}:</span>
                          <span className="observation-text">{observation.observation_text}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })()}

          {/* Player Options - hidden during combat (combat has its own action system) */}
          {!isInCombat && (
            <div className="quick-actions-sidebar">
              {/* Section header for secondary players */}
              {!isActivePlayer && playerOptions.length > 0 && (
                <div className="options-section-header">
                  <span className="options-section-icon">👁️</span>
                  <span className="options-section-title">Observe & Discover</span>
                  <span className="options-section-hint">Click to share with active player</span>
                </div>
              )}
              {playerOptions.length > 0 ? (
                playerOptions.map((option, index) => (
                  <button
                    key={index}
                    className={`quick-action-btn ${!isActivePlayer ? 'observation-option' : ''}`}
                    onClick={() => handlePlayerOption(option)}
                    title={!isActivePlayer ? 'Click to share this observation with the active player' : 'Click to add to your action'}
                  >
                    {option}
                  </button>
                ))
              ) : (
                <div className="no-options-message">
                  {isActivePlayer ? 'Waiting for options...' : 'Observe & Discover - waiting for options...'}
                </div>
              )}
            </div>
          )}
          {isInCombat && (
            <div className="quick-actions-sidebar combat-mode">
              <div className="combat-mode-message">
                <span className="combat-icon">⚔️</span>
                <span>Combat in progress - use the Combat panel for actions</span>
              </div>
            </div>
          )}
        </div>
      )
    },
    {
      id: 'media',
      name: 'Media',
      icon: '🖼️',
      component: (
        <MediaGallery
          campaignId={campaignId}
          recentMedia={recentMedia}
          refreshTrigger={imageRefreshTrigger}
        />
      )
    }
  ], [campaignId, collabWebSocket, collabPlayerId, collabPlayerName, collabAllPlayers, isMyTurn, handleCollabSubmit, handlePlayerOption, recentMedia, imageRefreshTrigger, collabEditorConnected, playerOptions, isActivePlayer, pendingObservations, selectedObservationIds, toggleObservationSelection, submissionConfirmation, isTranscribing, onToggleTranscription, audioPermissionState, voiceActivityLevel, collabEditorRef, isInCombat]);

  return (
    <div className="player-controls" data-testid="player-controls">
      {/* Tab Navigation */}
      <div className="controls-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => handleTabSwitch(tab.id)}
            title={tab.name}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-name">{tab.name}</span>
            {tab.id === 'voice' && isTranscribing && (
              <div className="voice-activity-indicator active" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="controls-content">
        {tabs.find(tab => tab.id === activeTab)?.component}
      </div>
    </div>
  );
};

export default PlayerControls;
