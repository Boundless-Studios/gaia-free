import React from 'react';
import '../styles/TurnIndicator.css';

const TurnIndicator = ({ turnInfo }) => {
  if (!turnInfo) return null;

  const turnNumber = turnInfo.turn_number ?? turnInfo.turnNumber;
  const characterName = turnInfo.character_name || turnInfo.characterName || turnInfo.character_id || 'Unknown';

  return (
    <div className="turn-indicator" data-testid="turn-indicator">
      <div className="turn-indicator__dot" />
      <div className="turn-indicator__text">
        <span className="turn-indicator__label">Current Turn</span>
        <span className="turn-indicator__value">
          {typeof turnNumber === 'number' ? `#${turnNumber}` : ''}
          {typeof turnNumber === 'number' ? ' — ' : ''}
          {characterName}
        </span>
      </div>
    </div>
  );
};

export default TurnIndicator;

