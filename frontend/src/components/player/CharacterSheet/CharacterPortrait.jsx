import React from 'react';
import useAuthorizedMediaUrl from '../../../hooks/useAuthorizedMediaUrl.js';

const CharacterPortrait = ({ character, size = 'medium' }) => {
  const defaultPortrait = {
    Barbarian: '🏔️',
    Fighter: '⚔️',
    Wizard: '🔮',
    Rogue: '🗡️',
    Cleric: '✨',
    Ranger: '🏹',
    Paladin: '🛡️',
    Sorcerer: '⚡',
    Warlock: '🌙',
    Bard: '🎭',
    Druid: '🌿',
    Monk: '👊'
  };

  const portraitClass = `character-portrait character-portrait-${size}`;

  // Check for generated portrait URL or path
  const authorizedPortraitUrl = useAuthorizedMediaUrl(character.portrait_url);
  const hasGeneratedPortrait = Boolean(character.portrait_url || character.portrait_path);
  const portraitSrc = authorizedPortraitUrl || character.portrait_path || character.portrait;

  // Fallback to emoji if no portrait
  const portraitContent = defaultPortrait[character.class || character.character_class] || '🧙‍♂️';

  return (
    <div className={portraitClass}>
      {hasGeneratedPortrait || character.portrait ? (
        <img
          src={portraitSrc}
          alt={`${character.name} portrait`}
          className="portrait-image"
          onError={(e) => {
            // Fallback to emoji if image fails to load
            e.target.style.display = 'none';
            e.target.nextSibling.style.display = 'flex';
          }}
        />
      ) : (
        <div className="portrait-placeholder" style={{ display: hasGeneratedPortrait ? 'none' : 'flex' }}>
          <span className="portrait-emoji">{portraitContent}</span>
        </div>
      )}

      {/* Hidden fallback placeholder for image load errors */}
      {(hasGeneratedPortrait || character.portrait) && (
        <div className="portrait-placeholder" style={{ display: 'none' }}>
          <span className="portrait-emoji">{portraitContent}</span>
        </div>
      )}

      {/* Mystical glow effect */}
      <div className="portrait-glow"></div>
    </div>
  );
};

export default CharacterPortrait;
