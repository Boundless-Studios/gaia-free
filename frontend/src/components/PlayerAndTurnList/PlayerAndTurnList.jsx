import React, { useState, useEffect } from 'react';
import './PlayerAndTurnList.css';
import CharacterCard from './CharacterCard';

/**
 * PlayerAndTurnList Component
 *
 * Displays character portraits and turn information for both DM and Player views.
 * - Shows character portraits (small size, 80x80px)
 * - Displays turn indicator (gold border for active character)
 * - Shows turn number at the top
 * - Tooltip on hover with full character details
 * - Polls for character updates every 10 seconds
 * - Supports both vertical (default) and horizontal orientations
 */
const PlayerAndTurnList = ({
  campaignId,
  turnInfo = null,
  currentPlayerId = null,
  compact = false,
  orientation = 'vertical' // 'vertical' or 'horizontal'
}) => {
  const [characters, setCharacters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch characters from API
  const fetchCharacters = async () => {
    try {
      const response = await fetch(`/api/campaigns/${campaignId}/characters`);
      const data = await response.json();

      if (data.success && data.characters) {
        setCharacters(data.characters);
        setError(null);
      } else {
        console.error('Failed to load characters:', data);
        setError('Failed to load characters');
      }
    } catch (err) {
      console.error('Error fetching characters:', err);
      setError(`Failed to load characters: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Fetch characters on mount and when campaignId changes
  useEffect(() => {
    if (campaignId) {
      fetchCharacters();
    }
  }, [campaignId]);

  // Poll for character updates every 10 seconds
  useEffect(() => {
    if (!campaignId) return;

    const interval = setInterval(fetchCharacters, 10000);
    return () => clearInterval(interval);
  }, [campaignId]);

  // Get current turn character info
  const currentTurnCharacterId = turnInfo?.character_id || null;
  const currentTurnCharacter = turnInfo?.character_name || null;
  const currentTurn = turnInfo?.turn_number || turnInfo?.current_turn || 0;

  if (loading) {
    return (
      <div className="player-and-turn-list">
        <div className="loading-message">Loading characters...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="player-and-turn-list">
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (characters.length === 0) {
    return (
      <div className="player-and-turn-list">
        <div className="empty-message">No characters in this campaign</div>
      </div>
    );
  }

  return (
    <div className={`player-and-turn-list ${compact ? 'compact' : ''} ${orientation}`}>
      {/* Turn header */}
      <div className="turn-header">
        <div className="turn-number">🎯 Turn {currentTurn || 1}</div>
        {currentTurnCharacter && (
          <div className="turn-character-name">
            {currentTurnCharacter}'s Turn
          </div>
        )}
      </div>

      {/* Character list */}
      <div className={`character-list ${orientation}`}>
        {characters.map((character) => {
          // Match by character_id first (most reliable), then fall back to name matching (case-insensitive)
          const isActiveTurn = currentTurnCharacterId
            ? character.character_id === currentTurnCharacterId
            : currentTurnCharacter
              ? character.name?.toLowerCase() === currentTurnCharacter.toLowerCase()
              : false;

          return (
            <CharacterCard
              key={character.character_id}
              character={character}
              isActiveTurn={isActiveTurn}
              isCurrentPlayer={character.character_id === currentPlayerId}
              compact={compact}
            />
          );
        })}
      </div>
    </div>
  );
};

export default PlayerAndTurnList;
