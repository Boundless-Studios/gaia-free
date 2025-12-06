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
  onCopyObservation = null
}) => {
  const [activeTab, setActiveTab] = useState('voice');
  const [recentMedia, setRecentMedia] = useState([]);
  const [collabEditorConnected, setCollabEditorConnected] = useState(false);

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

  // Handle player option selection
  const handlePlayerOption = (option) => {
    if (collabEditorRef.current) {
      collabEditorRef.current.insertText(option);
    } else {
      console.warn('Collaborative editor not ready');
    }
  };

  // Handle collaborative text submission
  const handleCollabSubmit = useCallback((text) => {
    if (onPlayerAction) {
      onPlayerAction({
        type: 'player_message',
        message: text
      });
    }
  }, [onPlayerAction]);

  // Determine if it's this player's turn (for now, always true since we don't have turn info)
  // TODO: Wire up to actual turn info from structuredData.turn_info
  const isMyTurn = true;

  // Parse player options from structuredData
  // Priority: personalized_player_options > player_options > turn
  const playerOptions = useMemo(() => {
    if (!structuredData) return [];

    // Check for personalized options first (if we have a character ID)
    const personalizedOptions = structuredData.personalized_player_options;
    if (personalizedOptions && currentCharacterId) {
      const charOptions = personalizedOptions.characters?.[currentCharacterId];
      if (charOptions?.options && Array.isArray(charOptions.options)) {
        return charOptions.options.filter(option => option && option.trim().length > 0);
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
                />
              </div>
            </>
          ) : (
            <div className="collab-waiting">
              <p>Connecting to collaborative session...</p>
            </div>
          )}

          {/* Pending Observations (shown to active player) */}
          {isActivePlayer && pendingObservations && pendingObservations.length > 0 && (
            <div className="pending-observations-section">
              <div className="observations-header">
                <span className="observations-icon">👁️</span>
                <span className="observations-title">Party Observations</span>
                <span className="observations-count">{pendingObservations.length}</span>
              </div>
              <div className="observations-list">
                {pendingObservations.filter(obs => !obs.included_in_turn).map((observation, index) => (
                  <div
                    key={`obs-${observation.character_id}-${index}`}
                    className="observation-item"
                    onClick={() => onCopyObservation && onCopyObservation(observation)}
                    style={onCopyObservation ? { cursor: 'pointer' } : {}}
                    title={onCopyObservation ? "Click to add to your turn" : ""}
                  >
                    <span className="observation-author">{observation.character_name}:</span>
                    <span className="observation-text">{observation.observation_text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Player Options */}
          <div className="quick-actions-sidebar">
            {playerOptions.length > 0 ? (
              playerOptions.map((option, index) => (
                <button
                  key={index}
                  className="quick-action-btn"
                  onClick={() => handlePlayerOption(option)}
                >
                  {option}
                </button>
              ))
            ) : (
              <div className="no-options-message">
                {isActivePlayer ? 'Waiting for options...' : 'Observe & Discover'}
              </div>
            )}
          </div>
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
  ], [campaignId, collabWebSocket, collabPlayerId, collabPlayerName, collabAllPlayers, isMyTurn, handleCollabSubmit, handlePlayerOption, recentMedia, imageRefreshTrigger, collabEditorConnected, playerOptions]);

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
