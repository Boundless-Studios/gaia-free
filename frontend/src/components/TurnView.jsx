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
 * When personalized options are available:
 * - Shows options specific to the current character
 * - Displays "Your Turn" indicator for active player
 * - Shows "Observe" indicator for passive players
 */
const TurnView = ({
  turn,
  personalizedPlayerOptions,
  currentCharacterId,
  className = '',
  showHeader = true,
  onPlayStop,
  isPlaying,
  onCopyToChat,
  turnInfo
}) => {
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
      return { turnLines: [], isActive: true, characterName: null };
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

    return { turnLines: lines, isActive: true, characterName: null };
  }, [turn, personalizedPlayerOptions, currentCharacterId]);

  // Don't render if no options
  if (!turnLines || turnLines.length === 0) {
    return null;
  }

  // Determine header text based on active status
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

  // Determine header style class
  const getHeaderClass = () => {
    if (personalizedPlayerOptions && currentCharacterId) {
      return isActive ? 'turn-header--active' : 'turn-header--passive';
    }
    return '';
  };

  return (
    <div className={`turn-view base-view ${className} ${isActive ? 'turn-view--active' : 'turn-view--passive'}`}>
      {showHeader && (
        <div className={`turn-header base-header ${getHeaderClass()}`}>
          <h2 className="turn-title base-title">{getHeaderText()}</h2>
          {personalizedPlayerOptions && currentCharacterId && (
            <span className={`turn-role-badge ${isActive ? 'turn-role-badge--active' : 'turn-role-badge--passive'}`}>
              {isActive ? '⚔️' : '👁️'}
            </span>
          )}
        </div>
      )}
      <div className="turn-content base-content">
        <div className="turn-text base-text">
          {turnLines.map((line, index) => (
            <div
              key={index}
              className={`chat-message-container dm ${isActive ? 'option--active' : 'option--passive'}`}
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
      </div>
    </div>
  );
};

export default TurnView;
