import React, { useState } from 'react';
import CharacterPortrait from './CharacterPortrait.jsx';
import StatsDisplay from './StatsDisplay.jsx';
import AbilitiesPanel from './AbilitiesPanel.jsx';
import './CharacterSheet.css';

const CharacterSheet = ({ character, campaignId}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Default character data if none provided
  const defaultCharacter = {
    name: 'Gaius',
    class: 'Barbarian',
    level: 1,
    stats: {
      strength: 20,
      dexterity: 16,
      constitution: 18,
      intelligence: 14,
      wisdom: 15,
      charisma: 11
    },
    abilities: [],
    portrait: null
  };

  const currentCharacter = character || defaultCharacter;

  return (
    <div className="character-sheet" data-testid="character-sheet">
      {/* Header */}
      <div className="character-sheet-header">
        <div className="character-sheet-icon">⚔️</div>
        <h2 className="character-sheet-title">Character Sheet</h2>
        <button
          className="character-sheet-toggle"
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? '📖' : '📋'}
        </button>
      </div>

      {/* Character Portrait */}
      <div className="character-portrait-section">
        <CharacterPortrait
          character={currentCharacter}
          size="large"
        />
      </div>

      {/* Character Identity */}
      <div className="character-identity">
        <div className="character-name" data-testid="character-name">
          {currentCharacter.name}
        </div>
        <div className="character-class-level">
          <span className="character-class">{currentCharacter.class}</span>
          {currentCharacter.level && (
            <span className="character-level">Lv. {currentCharacter.level}</span>
          )}
        </div>
      </div>

      {/* Stats Display */}
      <div className="character-stats-section">
        <h3 className="section-title">
          <span className="section-icon">📊</span>
          Stats
        </h3>
        <StatsDisplay
          stats={currentCharacter.stats}
          isCompact={!isExpanded}
        />
      </div>

      {/* Abilities Panel (Expandable) */}
      {(isExpanded || currentCharacter.abilities?.length > 0) && (
        <div className="character-abilities-section">
          <h3 className="section-title">
            <span className="section-icon">✨</span>
            Abilities
          </h3>
          <AbilitiesPanel
            abilities={currentCharacter.abilities || []}
            isExpanded={isExpanded}
          />
        </div>
      )}

      {/* Additional Info (Expandable) */}
      {isExpanded && (
        <div className="character-additional-info">
          {currentCharacter.hitPoints && (
            <div className="character-info-row">
              <span className="info-label">HP:</span>
              <span className="info-value">
                {currentCharacter.hitPoints.current}/{currentCharacter.hitPoints.max}
              </span>
            </div>
          )}

          {currentCharacter.armorClass && (
            <div className="character-info-row">
              <span className="info-label">AC:</span>
              <span className="info-value">{currentCharacter.armorClass}</span>
            </div>
          )}

          {currentCharacter.background && (
            <div className="character-info-row">
              <span className="info-label">Background:</span>
              <span className="info-value">{currentCharacter.background}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CharacterSheet;