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
 * - Automatically detects orientation: portrait → horizontal, landscape → vertical
 */
const PlayerAndTurnList = ({
  campaignId,
  turnInfo = null,
  currentPlayerId = null,
  compact = false,
  orientation = null // Optional override, null = auto-detect based on screen orientation
}) => {
  const [characters, setCharacters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detectedOrientation, setDetectedOrientation] = useState('vertical');

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

  // Detect screen orientation and update layout accordingly
  useEffect(() => {
    const handleOrientationChange = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const isPortrait = height > width;

      // Layout decision based on device size and orientation:
      // - Desktop/Laptop (>1100px): Always vertical (we have space)
      // - iPad landscape (1025-1100px): Always vertical
      // - iPad portrait / tablets (768-1024px portrait): Horizontal to save vertical space
      // - Mobile (<768px): Always horizontal

      if (width > 1100) {
        // Desktop/Laptop - always vertical
        setDetectedOrientation('vertical');
      } else if (width >= 1025 && width <= 1100) {
        // iPad landscape - always vertical
        setDetectedOrientation('vertical');
      } else if (width >= 768 && width <= 1024) {
        // Tablets - horizontal if portrait, vertical if landscape
        setDetectedOrientation(isPortrait ? 'horizontal' : 'vertical');
      } else {
        // Mobile - always horizontal
        setDetectedOrientation('horizontal');
      }
    };

    // Set initial orientation
    handleOrientationChange();

    // Listen for orientation changes (both resize and orientationchange events)
    window.addEventListener('resize', handleOrientationChange);
    window.addEventListener('orientationchange', handleOrientationChange);

    return () => {
      window.removeEventListener('resize', handleOrientationChange);
      window.removeEventListener('orientationchange', handleOrientationChange);
    };
  }, []);

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

  // Use provided orientation prop, or fall back to detected orientation
  const effectiveOrientation = orientation || detectedOrientation;

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
    <div className={`player-and-turn-list ${compact ? 'compact' : ''} ${effectiveOrientation}`}>
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
      <div className={`character-list ${effectiveOrientation}`}>
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
