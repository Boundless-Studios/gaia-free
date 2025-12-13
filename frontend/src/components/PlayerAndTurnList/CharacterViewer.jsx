import React from 'react';
import ReactDOM from 'react-dom';
import './CharacterViewer.css';
import { getHPColor, getHPPercentage, getFormattedAbilityModifier } from '../../utils/characterUtils';
import useAuthorizedMediaUrl from '../../hooks/useAuthorizedMediaUrl.js';

/**
 * CharacterViewer Component
 *
 * Full-screen modal viewer for character details.
 * Displays a large 600px portrait and all character information.
 * Follows the same pattern as ImageGallery modal.
 */
const CharacterViewer = ({ character, onClose }) => {
  // Use utility functions for HP calculations
  const hpPercentage = getHPPercentage(character.hit_points_current, character.hit_points_max);
  const hpColor = getHPColor(character.hit_points_current, character.hit_points_max);
  const portraitUrl = useAuthorizedMediaUrl(character.portrait_url) || character.portrait_path || null;

  const handleBackdropClick = (e) => {
    // Stop propagation to prevent React event bubbling to parent components
    e.stopPropagation();
    // Only close if clicking directly on the modal backdrop, not on content
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleCloseClick = (e) => {
    e.stopPropagation();
    onClose();
  };

  const modalContent = (
    <div
      className="character-viewer-modal"
      onClick={handleBackdropClick}
    >
      <div
        className="character-viewer-content"
      >
        {/* Close Button */}
        <button
          className="character-viewer-close"
          onClick={handleCloseClick}
          aria-label="Close character viewer"
        >
          ✕
        </button>

        {/* Main Content */}
        <div className="character-viewer-grid">
          {/* Left: Large Portrait */}
          <div className="character-viewer-portrait-section">
            {portraitUrl ? (
              <img
                src={portraitUrl}
                alt={character.name}
                className="character-viewer-portrait"
              />
            ) : (
              <div className="character-viewer-portrait-placeholder">
                🧙
              </div>
            )}
          </div>

          {/* Right: Character Information */}
          <div className="character-viewer-info-section">
            {/* Header */}
            <div className="character-viewer-header">
              <h2 className="character-viewer-name">{character.name}</h2>
              <div className="character-viewer-subtitle">
                {character.race} {character.character_class} • Level {character.level}
              </div>
            </div>

            {/* HP Bar */}
            <div className="character-viewer-hp-section">
              <div className="hp-label">Hit Points</div>
              <div className="hp-bar-container">
                <div
                  className="hp-bar-fill"
                  style={{
                    width: `${hpPercentage}%`,
                    backgroundColor: hpColor
                  }}
                />
              </div>
              <div className="hp-text" style={{ color: hpColor }}>
                {character.hit_points_current} / {character.hit_points_max}
              </div>
            </div>

            {/* Combat Stats */}
            <div className="character-viewer-section">
              <h3 className="section-title">Combat Stats</h3>
              <div className="stats-grid">
                <div className="stat-box">
                  <div className="stat-label">Armor Class</div>
                  <div className="stat-value">{character.armor_class}</div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">Status</div>
                  <div className="stat-value status">{character.status || 'Healthy'}</div>
                </div>
              </div>
            </div>

            {/* Ability Scores */}
            <div className="character-viewer-section">
              <h3 className="section-title">Ability Scores</h3>
              <div className="abilities-grid">
                <div className="ability-box">
                  <div className="ability-label">STR</div>
                  <div className="ability-value">{character.strength || 10}</div>
                  <div className="ability-modifier">
                    {getFormattedAbilityModifier(character.strength)}
                  </div>
                </div>
                <div className="ability-box">
                  <div className="ability-label">DEX</div>
                  <div className="ability-value">{character.dexterity || 10}</div>
                  <div className="ability-modifier">
                    {getFormattedAbilityModifier(character.dexterity)}
                  </div>
                </div>
                <div className="ability-box">
                  <div className="ability-label">CON</div>
                  <div className="ability-value">{character.constitution || 10}</div>
                  <div className="ability-modifier">
                    {getFormattedAbilityModifier(character.constitution)}
                  </div>
                </div>
                <div className="ability-box">
                  <div className="ability-label">INT</div>
                  <div className="ability-value">{character.intelligence || 10}</div>
                  <div className="ability-modifier">
                    {getFormattedAbilityModifier(character.intelligence)}
                  </div>
                </div>
                <div className="ability-box">
                  <div className="ability-label">WIS</div>
                  <div className="ability-value">{character.wisdom || 10}</div>
                  <div className="ability-modifier">
                    {getFormattedAbilityModifier(character.wisdom)}
                  </div>
                </div>
                <div className="ability-box">
                  <div className="ability-label">CHA</div>
                  <div className="ability-value">{character.charisma || 10}</div>
                  <div className="ability-modifier">
                    {getFormattedAbilityModifier(character.charisma)}
                  </div>
                </div>
              </div>
            </div>

            {/* Appearance & Details */}
            {(character.gender || character.age_category || character.build || character.facial_expression || character.location) && (
              <div className="character-viewer-section">
                <h3 className="section-title">Details</h3>
                <div className="details-grid">
                  {character.gender && (
                    <div className="detail-item">
                      <span className="detail-label">Gender:</span>
                      <span className="detail-value">{character.gender}</span>
                    </div>
                  )}
                  {character.age_category && (
                    <div className="detail-item">
                      <span className="detail-label">Age:</span>
                      <span className="detail-value">{character.age_category}</span>
                    </div>
                  )}
                  {character.build && (
                    <div className="detail-item">
                      <span className="detail-label">Build:</span>
                      <span className="detail-value">{character.build}</span>
                    </div>
                  )}
                  {character.facial_expression && (
                    <div className="detail-item">
                      <span className="detail-label">Expression:</span>
                      <span className="detail-value">{character.facial_expression}</span>
                    </div>
                  )}
                  {character.location && (
                    <div className="detail-item">
                      <span className="detail-label">Location:</span>
                      <span className="detail-value">{character.location}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Backstory */}
            {character.backstory && (
              <div className="character-viewer-section">
                <h3 className="section-title">Backstory</h3>
                <div className="backstory-text">
                  {character.backstory}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  // Use React Portal to render at document body level
  return ReactDOM.createPortal(modalContent, document.body);
};

export default CharacterViewer;
