import { forwardRef, useEffect, useRef, useCallback, useState } from 'react';
import TurnView from './TurnView';
import CombatStatusView from './CombatStatusView';
import ImageGalleryWithPolling from './ImageGalleryWithPolling';
import SceneImagesMiniGallery from './SceneImagesMiniGallery';
import PlayerAndTurnList from './PlayerAndTurnList/PlayerAndTurnList';
import CollaborativeStackedEditor from './collaborative/CollaborativeStackedEditor.jsx';
import apiService from '../services/apiService';
import './GameDashboard.css';
import StreamingNarrativeView from './player/StreamingNarrativeView.jsx';
import { useRoom } from '../contexts/RoomContext.jsx';
import RoomManagementDrawer from './dm/RoomManagementDrawer.jsx';
import Button from './base-ui/Button.jsx';

const GameDashboard = forwardRef(
  ({
    latestStructuredData,
    onImageGenerated,
    campaignId,
    streamingNarrative = '',
    streamingResponse = '',
    isNarrativeStreaming = false,
    isResponseStreaming = false,
    onDebugStreamPreview,
    messages = [],
    // Chat input props
    inputMessage = '',
    onInputChange,
    onSendMessage,
    onKeyDown,
    isChatProcessing = false,
    isTranscribing = false,
    onToggleTranscription = null,
    chatInputRef,
    voiceActivityLevel = 0,
    audioPermissionState = 'pending',
    // Collaborative editing props
    collabWebSocket = null,
    collabPlayerId = '',
    collabPlayerName = 'DM',
    collabAllPlayers = [],
    collabIsConnected = false,
    // Personalized player options props
    currentCharacterId = null,
    isActivePlayer = true, // True if current user is the turn-taker
    pendingObservations = [], // Observations from other players
    onSubmitObservation = null, // Callback for secondary players to submit observations
    onCopyObservation = null, // Callback for primary player to copy an observation
    // Player submissions (from player action submissions)
    playerSubmissions = [],
    onCopyPlayerSubmission = null,
  }, ref) => {
  // Debug: Log player submissions received by GameDashboard
  console.log('📋 GameDashboard render:', {
    playerSubmissionsCount: playerSubmissions?.length,
    playerSubmissions,
    hasPlayerOptions: !!(latestStructuredData?.player_options || latestStructuredData?.turn),
    isActivePlayer,
    pendingObservationsCount: pendingObservations?.length
  });

  // Audio now handled by synchronized streaming via WebSocket
  const sessionForRequest = campaignId || 'default-session';

  // Track collaborative editor connection state
  const [collabEditorConnected, setCollabEditorConnected] = useState(false);
  const [collabEditorHasDraft, setCollabEditorHasDraft] = useState(false);
  const collabEditorRef = useRef(null);

  // Room management state (optional - only if RoomProvider is available)
  const [showRoomDrawer, setShowRoomDrawer] = useState(false);
  let roomContext = null;
  try {
    roomContext = useRoom();
  } catch (e) {
    // RoomProvider not available - room features disabled
  }
  const { isDMSeated, roomState } = roomContext || {};
  const isCampaignSetup = Boolean(roomContext && roomState?.campaign_status === 'setup');

  // Auto-TTS on production when streaming completes
  const prevStreamingRef = useRef({ isNarrativeStreaming: false, isResponseStreaming: false });

  useEffect(() => {
    const autoTtsEnabled = import.meta.env.VITE_AUTO_TTS_ENABLED === 'true';

    if (!autoTtsEnabled) return;

    const wasStreaming = prevStreamingRef.current.isNarrativeStreaming || prevStreamingRef.current.isResponseStreaming;
    const isNowStreaming = isNarrativeStreaming || isResponseStreaming;

    // Trigger TTS when streaming just finished - backend handles enqueueing and playback
    if (wasStreaming && !isNowStreaming && (streamingNarrative || streamingResponse)) {
      const textToSpeak = streamingNarrative || streamingResponse;

      if (textToSpeak.trim() && campaignId) {
        apiService.synthesizeTTS(
          {
            text: textToSpeak,
            voice: 'nathaniel',
            speed: 1.0,
          },
          sessionForRequest,
        ).then(() => {
          console.log('Auto-TTS triggered - backend will handle synchronized streaming');
        }).catch((error) => {
          console.error('Auto-TTS Error:', error);
        });
      }
    }

    prevStreamingRef.current = { isNarrativeStreaming, isResponseStreaming };
  }, [isNarrativeStreaming, isResponseStreaming, streamingNarrative, streamingResponse, campaignId, sessionForRequest]);


  const structuredData = latestStructuredData || {};
  const turnInfo = structuredData.turn_info || {};
  const combatStatus = structuredData.combat_status || {};

  const handlePlayStopOptions = async () => {
    try {
      // Backend handles audio queue via database and synchronized streaming
      const textToSpeak = structuredData.player_options || structuredData.turn || '';

      if (!textToSpeak.trim()) {
        console.warn('No text to speak');
        return;
      }

      await apiService.synthesizeTTS(
        {
          text: textToSpeak,
          voice: 'nathaniel',
          speed: 1.0,
        },
        sessionForRequest,
      );
      console.log('TTS request sent - backend will handle synchronized streaming');
    } catch (error) {
      console.error('TTS Error:', error);
    }
  };

  const formatStatusLabel = (status) => {
    if (!status) return 'Unknown';
    return status.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const roomStatusColor = roomState?.room_status === 'active' ? 'text-green-400' : 'text-yellow-400';
  const campaignStatusColor = roomState?.campaign_status === 'active' ? 'text-green-400' : 'text-yellow-400';
  const roomStatusLabel = roomState?.room_status ? formatStatusLabel(roomState.room_status) : 'Waiting';
  const campaignStatusLabel = roomState?.campaign_status ? formatStatusLabel(roomState.campaign_status) : 'Setup';

  const streamingNarrativeText = (streamingNarrative || '').trim();
  const streamingResponseText = (streamingResponse || '').trim();
  const streamingHasContent = Boolean(streamingNarrativeText || streamingResponseText);
  const streamingInProgress = Boolean(isNarrativeStreaming || isResponseStreaming);
  const hasPlayerOptions = Boolean(
    (latestStructuredData?.turn && String(latestStructuredData.turn).trim()) ||
    (latestStructuredData?.player_options && String(latestStructuredData.player_options).trim()) ||
    (latestStructuredData?.personalized_player_options?.characters &&
     Object.keys(latestStructuredData.personalized_player_options.characters).length > 0)
  );

  // Handle collaborative text submission
  // DM can submit empty text (means "continue")
  const handleCollabSubmit = useCallback((text) => {
    if (onSendMessage && typeof text === 'string') {
      onSendMessage(text);
      setCollabEditorHasDraft(false);
    }
  }, [onSendMessage]);

  const handleCollabButtonClick = useCallback(() => {
    collabEditorRef.current?.submitMyInput?.();
  }, []);

  const handleCollabContentChange = useCallback((content) => {
    setCollabEditorHasDraft(Boolean(content && content.trim().length));
  }, []);

  // Handle clicking player options to copy to chat input
  const handleCopyPlayerOptionToChat = useCallback((optionText) => {
    if (collabWebSocket && collabEditorRef.current?.insertText) {
      // Using collaborative editor - insert via ref
      collabEditorRef.current.insertText(optionText);
    } else if (onInputChange) {
      // Fallback to regular input - append to existing message
      const separator = inputMessage.trim() ? ' ' : '';
      onInputChange({ target: { value: inputMessage + separator + optionText } });
    }
  }, [collabWebSocket, onInputChange, inputMessage]);

  // Handle copying an observation from a secondary player to the primary player's input
  const handleCopyObservationToChat = useCallback((observation) => {
    // Format: "[CharacterName observes]: observation text"
    const formattedObservation = `[${observation.character_name} observes]: ${observation.observation_text}`;

    if (collabWebSocket && collabEditorRef.current?.insertText) {
      // Using collaborative editor - insert via ref
      collabEditorRef.current.insertText(formattedObservation);
    } else if (onInputChange) {
      // Fallback to regular input - append to existing message
      const separator = inputMessage.trim() ? '\n\n' : '';
      onInputChange({ target: { value: inputMessage + separator + formattedObservation } });
    }
  }, [collabWebSocket, onInputChange, inputMessage]);

  // Handle copying a player submission to the DM's input
  const handleCopyPlayerSubmission = useCallback((submission) => {
    if (!submission) return;

    // Format: "[CharacterName]: action text"
    const formattedAction = `[${submission.characterName}]: ${submission.actionText}`;

    if (collabWebSocket && collabEditorRef.current?.insertText) {
      // Using collaborative editor - insert via ref
      collabEditorRef.current.insertText(formattedAction);
    } else if (onInputChange) {
      // Fallback to regular input - append to existing message
      const separator = inputMessage.trim() ? '\n\n' : '';
      onInputChange({ target: { value: inputMessage + separator + formattedAction } });
    }

    // Remove the submission after copying
    if (onCopyPlayerSubmission) {
      onCopyPlayerSubmission(submission);
    }
  }, [collabWebSocket, onInputChange, inputMessage, onCopyPlayerSubmission]);

  const streamingPanel = (
    <div className="dashboard-streaming-panel">
      <div className="streaming-panel-header">
        <div
          className={`streaming-panel-status${streamingInProgress ? ' streaming-panel-status--active' : ''}`}
        >
          {streamingInProgress ? 'Streaming…' : 'Idle'}
        </div>
      </div>
      <div className="streaming-panel-body">
        <StreamingNarrativeView
          narrative={streamingNarrativeText}
          playerResponse={streamingResponseText}
          isNarrativeStreaming={isNarrativeStreaming}
          isResponseStreaming={isResponseStreaming}
          messages={messages}
          onImageGenerated={onImageGenerated}
          campaignId={campaignId}
        />
      </div>
    </div>
  );

  const setupPlaceholder = (
    <div className="dashboard-placeholder">
      <div className="placeholder-icon">🛠️</div>
      <h3>Campaign Setup In Progress</h3>
      <p>Invite players, create characters, then start the campaign from Room Management when everyone is ready.</p>
      {roomContext && (
        <Button
          variant="secondary"
          className="mt-4"
          onClick={() => setShowRoomDrawer(true)}
        >
          Open Room Management
        </Button>
      )}
    </div>
  );

  const readyPlaceholder = (
    <div className="dashboard-placeholder">
      <div className="placeholder-icon">🎲</div>
      <h3>Ready for Adventure</h3>
      <p>Start a new campaign, or load an existing one to view structured data.</p>
      {roomContext && (
        <Button
          variant="secondary"
          className="mt-4"
          onClick={() => setShowRoomDrawer(true)}
        >
          Open Room Management
        </Button>
      )}
    </div>
  );

  const malformedPlaceholder = (
    <div className="dashboard-placeholder">
      <div className="placeholder-icon">⚠️</div>
      <h3>No Structured Data Available</h3>
      <p>The AI response didn't contain properly formatted sections yet.</p>
    </div>
  );

  const renderRoomDrawer = () => (
    roomContext ? (
      <RoomManagementDrawer
        campaignId={campaignId}
        isOpen={showRoomDrawer}
        onClose={() => setShowRoomDrawer(false)}
      />
    ) : null
  );

  const hasAnyStructuredData = Boolean(
    structuredData &&
    (
      (structuredData.narrative && String(structuredData.narrative).trim()) ||
      (structuredData.turn && String(structuredData.turn).trim()) ||
      (structuredData.player_options && String(structuredData.player_options).trim()) ||
      (structuredData.characters && String(structuredData.characters).trim()) ||
      (structuredData.status && String(structuredData.status).trim()) ||
      (structuredData.answer && String(structuredData.answer).trim())
    )
  );

  const placeholderContent = !latestStructuredData
    ? (isCampaignSetup ? setupPlaceholder : readyPlaceholder)
    : (!hasAnyStructuredData ? (isCampaignSetup ? setupPlaceholder : malformedPlaceholder) : null);
  
  return (
    <div className="game-dashboard" ref={ref}>
      {/* Placeholder banner */}
      {placeholderContent && (
        <div className="dashboard-placeholder-banner">
          {placeholderContent}
        </div>
      )}

      {/* Room Management Section - Only shown when RoomProvider is available */}
      {roomContext && (
        <>
          <div className="px-4 pt-4 flex items-center justify-between">
            <div className="text-sm text-gray-400 flex flex-col sm:flex-row sm:items-center gap-2">
              <span>
                Room:{' '}
                <span className={`font-medium ${roomStatusColor}`}>
                  {roomStatusLabel}
                </span>
              </span>
              <span>
                Campaign:{' '}
                <span className={`font-medium ${campaignStatusColor}`}>
                  {campaignStatusLabel}
                </span>
              </span>
            </div>
            <Button
              onClick={() => setShowRoomDrawer(true)}
              variant="secondary"
              size="small"
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              }
            >
              Manage Room
            </Button>
          </div>

          {/* Room Management Drawer */}
          {renderRoomDrawer()}
        </>
      )}

      {/* Character List Section - At the top */}
      <div className="dashboard-character-list-panel">
        <PlayerAndTurnList
          campaignId={campaignId}
          turnInfo={turnInfo}
          orientation="horizontal"
        />
      </div>

      {/* Image Gallery Section - Full width */}
      <div className="dashboard-gallery-panel">
        <ImageGalleryWithPolling
          maxImages={20}
          campaignId={campaignId}
          pollingInterval={30000}
          onImageClick={onImageGenerated}
        />
      </div>

      {/* Scene Images Mini Gallery - For DM to show generated scene images to players */}
      <div className="dashboard-scene-images-panel">
        <SceneImagesMiniGallery
          campaignId={campaignId}
          onShowToPlayers={onImageGenerated}
          pollingInterval={5000}
        />
      </div>

      {/* Combined Bottom Panel: Live DM Stream (75%) + Player Options (25%) */}
      <div className="dashboard-combined-bottom-panel">
        {/* Streaming DM output - Left side 75% */}
        <div className="dashboard-streaming-section">
          {streamingPanel}
        </div>

        {/* Player Options + Input - Right side 25% */}
        <div className="dashboard-player-options-section">
          <div className="dashboard-player-options-list">
            {hasPlayerOptions || (isActivePlayer && pendingObservations.length > 0) || playerSubmissions.length > 0 ? (
              <TurnView
                turn={latestStructuredData.player_options || latestStructuredData.turn}
                personalizedPlayerOptions={latestStructuredData.personalized_player_options}
                currentCharacterId={currentCharacterId}
                pendingObservations={pendingObservations}
                isActivePlayer={isActivePlayer}
                onCopyObservation={onCopyObservation || handleCopyObservationToChat}
                showHeader={true}
                onPlayStop={handlePlayStopOptions}
                isPlaying={false}
                onCopyToChat={handleCopyPlayerOptionToChat}
                turnInfo={latestStructuredData.turn_info}
                playerSubmissions={playerSubmissions}
                onCopyPlayerSubmission={handleCopyPlayerSubmission}
                isDMView={true}
              />
            ) : (
              <div className="dashboard-player-options-empty">
                <p>No player options yet — send a message to prompt the DM.</p>
              </div>
            )}
          </div>

          {/* Collaborative Text Input */}
          <div className={`dashboard-chat-input ${collabAllPlayers.length <= 1 ? 'dm-solo' : ''}`}>
            {collabWebSocket ? (
              <>
                <CollaborativeStackedEditor
                  ref={collabEditorRef}
                  sessionId={campaignId}
                  playerId={collabPlayerId}
                  characterName={collabPlayerName}
                  allPlayers={collabAllPlayers}
                  isMyTurn={true}
                  onSubmit={handleCollabSubmit}
                  websocket={collabWebSocket}
                  showHeader={false}
                  onConnectionChange={setCollabEditorConnected}
                  onMySectionChange={handleCollabContentChange}
                  isTranscribing={isTranscribing}
                  onToggleTranscription={onToggleTranscription}
                  showMicButton={audioPermissionState === 'granted'}
                  voiceLevel={voiceActivityLevel}
                />
                <div className="dashboard-input-buttons">
                  <div className="dashboard-input-status">
                    <span
                      className={`connection-dot-inline ${collabEditorConnected ? 'connected' : 'disconnected'}`}
                      title={collabEditorConnected ? 'Connected' : 'Disconnected'}
                    />
                    <span className="dashboard-input-status-text">
                      {collabEditorConnected ? 'Live collaboration' : 'Reconnecting…'}
                    </span>
                  </div>
                  <div className="dashboard-input-actions">
                    {isActivePlayer ? (
                      <button
                        onClick={handleCollabButtonClick}
                        className="dashboard-submit-button"
                        title="Submit your turn to the DM (empty = continue)"
                        disabled={isChatProcessing}
                      >
                        Submit
                      </button>
                    ) : (
                      <button
                        onClick={() => {
                          // Secondary player: submit as observation to primary player
                          if (onSubmitObservation && collabEditorRef.current?.getMyContent) {
                            const content = collabEditorRef.current.getMyContent();
                            if (content && content.trim()) {
                              onSubmitObservation(content.trim());
                              collabEditorRef.current.clearMySection?.();
                            }
                          } else {
                            // Fallback to regular submit
                            handleCollabButtonClick();
                          }
                        }}
                        className="dashboard-submit-button dashboard-submit-button--observation"
                        title="Share your observation with the active player"
                        disabled={!collabEditorHasDraft || isChatProcessing}
                      >
                        Share Observation
                      </button>
                    )}
                    {onToggleTranscription && (
                      <button
                        onClick={onToggleTranscription}
                        className="dashboard-transcription-button"
                        type="button"
                      >
                        🎙️ {isTranscribing ? 'Stop Listening' : 'Transcription'}
                      </button>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <>
                <textarea
                  ref={chatInputRef}
                  value={inputMessage}
                  onChange={onInputChange}
                  onKeyDown={onKeyDown}
                  placeholder="Type your action or message..."
                  disabled={isChatProcessing}
                  rows={1}
                  className="dashboard-textarea"
                />
                <div className="dashboard-input-buttons">
                  <div className="dashboard-input-actions">
                    <button
                      onClick={onSendMessage}
                      disabled={isChatProcessing || !inputMessage.trim()}
                    className="dashboard-send-button"
                    type="button"
                  >
                    Send
                  </button>
                  {onToggleTranscription && (
                    <button
                      onClick={onToggleTranscription}
                      className="dashboard-transcription-button"
                      type="button"
                    >
                      🎙️ {isTranscribing ? 'Stop Listening' : 'Transcription'}
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
          </div>
        </div>
      </div>

      {/* Combat Status Section */}
      <div className="dashboard-combat-status-panel">
        {combatStatus && Object.keys(combatStatus).length > 0 && (
          <CombatStatusView
            combatStatus={combatStatus}
            turnInfo={turnInfo}
            showHeader={true}
          />
        )}
      </div>

      {/* Debug information */}
      {/* (Removed raw structured data debug panel) */}

      {/* Additional information sections - temporarily removed */}
    </div>
  );
});

GameDashboard.displayName = 'GameDashboard';

export default GameDashboard;
