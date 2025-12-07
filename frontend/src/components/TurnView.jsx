import React, { useMemo } from 'react';
import './TurnView.css';
import './ChatMessage.css';

/**
 * TurnView - Displays player options for the current character.
 *
 * Supports two formats:
 * 1. Legacy: `turn` prop is an array or string of options (shared across all players)
 * 2. Personalized: `personalizedPlayerOptions` prop contains per-character options
 *
 * Also displays pending observations from other players when the user is the active player.
 */
const TurnView = ({
  turn,
  personalizedPlayerOptions,
  currentCharacterId,
  pendingObservations = [],
  isActivePlayer = true,
  onCopyObservation,
  className = '',
  showHeader = true,
  onPlayStop,
  isPlaying,
  onCopyToChat,
  turnInfo,
  // Player submissions (from players clicking "Submit Action")
  playerSubmissions = [],
  onCopyPlayerSubmission,
}) => {
  // Debug: Log what TurnView receives
  console.log('📋 TurnView render:', {
    playerSubmissionsCount: playerSubmissions?.length,
    playerSubmissions,
    pendingObservationsCount: pendingObservations?.length,
    isActivePlayer
  });
  // Determine which options to display and whether user is active
  const { turnLines, isActive, characterName } = useMemo(() => {
    // If personalized options are available and we have a character ID, use those
    if (personalizedPlayerOptions && currentCharacterId) {
      const charOptions = personalizedPlayerOptions.characters?.[currentCharacterId];
      if (charOptions) {
        return {
          turnLines: charOptions.options || [],
          isActive: charOptions.is_active || false,
          characterName: charOptions.character_name || 'You'
        };
      }
      // Character not found in personalized options - check if active character exists
      if (personalizedPlayerOptions.active_character_id) {
        const activeOptions = personalizedPlayerOptions.characters?.[personalizedPlayerOptions.active_character_id];
        if (activeOptions) {
          // Show active player's options with indication it's not their turn
          return {
            turnLines: activeOptions.options || [],
            isActive: false,
            characterName: activeOptions.character_name || 'Active Player'
          };
        }
      }
    }

    // Fall back to legacy format
    if (!turn) {
      return { turnLines: [], isActive: isActivePlayer, characterName: null };
    }

    let processedTurn = turn;
    let lines = [];

    // Handle different turn formats
    if (Array.isArray(turn)) {
      lines = turn.filter(line => line && line.trim());
    } else if (typeof turn === 'string') {
      // If turn is a string that looks like JSON, try to parse it
      if (turn.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(turn);
          if (typeof parsed === 'object') {
            processedTurn = Object.entries(parsed)
              .map(([key, value]) => `${key}: ${value}`)
              .join('\n');
          }
        } catch {
          processedTurn = turn;
        }
      }
      lines = processedTurn.split('\n').filter(line => line.trim());
    }

    return { turnLines: lines, isActive: isActivePlayer, characterName: null };
  }, [turn, personalizedPlayerOptions, currentCharacterId, isActivePlayer]);

  // Filter pending observations that haven't been included yet
  const unincludedObservations = useMemo(() => {
    if (!pendingObservations || !isActive) return [];
    return pendingObservations.filter(obs => !obs.included_in_turn);
  }, [pendingObservations, isActive]);

  // Don't render if no options, no observations, and no player submissions
  if ((!turnLines || turnLines.length === 0) && unincludedObservations.length === 0 && (!playerSubmissions || playerSubmissions.length === 0)) {
    return null;
  }

  // Determine header text
  const getHeaderText = () => {
    if (personalizedPlayerOptions && currentCharacterId) {
      if (isActive) {
        return characterName ? `${characterName}'s Turn` : 'Your Turn';
      } else {
        return 'Observe & Discover';
      }
    }
    return 'Player Options';
  };

  return (
    <div className={`turn-view base-view ${className}`}>
      {showHeader && (
        <div className="turn-header base-header">
          <h2 className="turn-title base-title">{getHeaderText()}</h2>
        </div>
      )}
      <div className="turn-content base-content">
        {/* Player submissions (from players clicking "Submit Action") */}
        {playerSubmissions.length > 0 && (
          <div className="turn-submissions-section">
            <div className="turn-submissions-header">
              <span className="turn-submissions-icon">📝</span>
              <span className="turn-submissions-title">Player Submissions</span>
              <span className="turn-submissions-count">{playerSubmissions.length}</span>
            </div>
            <div className="turn-submissions-list">
              {playerSubmissions.map((submission) => (
                <div
                  key={submission.id}
                  className="turn-submission-item"
                  onClick={() => onCopyPlayerSubmission && onCopyPlayerSubmission(submission)}
                  style={onCopyPlayerSubmission ? { cursor: 'pointer' } : {}}
                  title={onCopyPlayerSubmission ? "Click to copy to input" : ""}
                >
                  <span className="turn-submission-author">{submission.characterName}:</span>
                  <span className="turn-submission-text">{submission.actionText}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pending observations from other players (shown to active player) */}
        {unincludedObservations.length > 0 && (
          <div className="turn-observations-section">
            <div className="turn-observations-header">
              <span className="turn-observations-icon">👁️</span>
              <span className="turn-observations-title">Party Observations</span>
              <span className="turn-observations-count">{unincludedObservations.length}</span>
            </div>
            <div className="turn-observations-list">
              {unincludedObservations.map((observation, index) => (
                <div
                  key={`obs-${observation.character_id}-${index}`}
                  className="turn-observation-item"
                  onClick={() => onCopyObservation && onCopyObservation(observation)}
                  style={onCopyObservation ? { cursor: 'pointer' } : {}}
                  title={onCopyObservation ? "Click to add to your turn" : ""}
                >
                  <span className="turn-observation-author">{observation.character_name}:</span>
                  <span className="turn-observation-text">{observation.observation_text}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Player options */}
        {turnLines.length > 0 && (
          <div className="turn-text base-text">
            {turnLines.map((line, index) => (
              <div
                key={index}
                className="chat-message-container dm"
                onClick={() => onCopyToChat && onCopyToChat(line)}
                style={onCopyToChat ? { cursor: 'pointer' } : {}}
                title={onCopyToChat ? "Click to copy to chat input" : ""}
              >
                <div className="chat-message-content">
                  {line}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default TurnView;
