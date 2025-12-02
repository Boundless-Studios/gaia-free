import React, { useEffect, useState } from 'react';
import CharacterViewer from './CharacterViewer';
import useAuthorizedMediaUrl from '../../hooks/useAuthorizedMediaUrl.js';

/**
 * CharacterCard Component
 *
 * Displays a single character card with large portrait (160px) only.
 * Shows a gold border when it's the character's turn.
 * Opens a full CharacterViewer modal on click.
 */
const CharacterCard = ({
  character,
  isActiveTurn = false,
  isCurrentPlayer = false,
  compact = false
}) => {
  const [showViewer, setShowViewer] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Get portrait URL or use null (will show fallback UI)
  const portraitUrl = useAuthorizedMediaUrl(character.portrait_url) || character.portrait_path || null;

  useEffect(() => {
    // Reset error state whenever the resolved portrait changes
    setHasError(false);
  }, [portraitUrl]);

  const handleClick = (e) => {
    e.stopPropagation();
    setShowViewer(true);
  };

  return (
    <div
      className={`character-card ${isActiveTurn ? 'active-turn' : ''} ${isCurrentPlayer ? 'current-player' : ''} ${compact ? 'compact' : ''}`}
      onClick={handleClick}
    >
      {/* Character portrait - only element visible on card */}
      <div className="character-portrait-container">
        {portraitUrl ? (
          <>
            <img
              src={portraitUrl}
              alt={character.name}
              className="character-portrait"
              onLoad={() => setHasError(false)}
              onError={() => setHasError(true)}
              style={{ display: hasError ? 'none' : 'block' }}
            />
            <div
              className="character-portrait-placeholder"
              style={{ display: hasError ? 'flex' : 'none' }}
            >
              🧙
            </div>
          </>
        ) : (
          <div className="character-portrait-placeholder">
            🧙
          </div>
        )}
      </div>

      {/* Character Viewer Modal */}
      {showViewer && (
        <CharacterViewer
          character={character}
          onClose={() => setShowViewer(false)}
        />
      )}
    </div>
  );
};

export default CharacterCard;
