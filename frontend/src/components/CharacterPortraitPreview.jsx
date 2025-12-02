import React, { useState } from 'react';
import { Button } from './base-ui/Button';
import './CharacterPortraitPreview.css';
import useAuthorizedMediaUrl from '../hooks/useAuthorizedMediaUrl.js';

const CharacterPortraitPreview = ({
  character,
  campaignId,
  onPortraitGenerated,
  className = ''
}) => {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const authorizedPortraitUrl = useAuthorizedMediaUrl(character?.portrait_url);
  const portraitSrc = authorizedPortraitUrl || character?.portrait_path || '';
  const hasPortrait = Boolean(character?.portrait_url || character?.portrait_path);
  const placeholderText = generating
    ? 'Generating portrait...'
    : hasPortrait
      ? 'Loading portrait...'
      : 'No portrait yet';

  const handleGeneratePortrait = async () => {
    // Use character_id if available, otherwise use slot_id (during character creation)
    const charId = character?.character_id || `slot_${character?.slot_id}` || character?.name;

    if (!charId || !campaignId) {
      setError('Missing character name or campaign information');
      return;
    }

    if (!character?.name) {
      setError('Please add a character name first');
      return;
    }

    setGenerating(true);
    setError('');

    try {
      const apiService = (await import('../services/apiService')).default;

      // Prepare character data for portrait generation
      const characterData = {
        name: character.name,
        character_class: character.character_class,
        race: character.race,
        level: character.level,
        gender: character.gender,
        age_category: character.age_category,
        build: character.build,
        height_description: character.height_description,
        facial_expression: character.facial_expression,
        facial_features: character.facial_features,
        attire: character.attire,
        primary_weapon: character.primary_weapon,
        distinguishing_feature: character.distinguishing_feature,
        background_setting: character.background_setting,
        pose: character.pose,
        // Include text descriptions for complete character profile
        backstory: character.backstory || '',
        description: character.description || '',
        appearance: character.appearance || '',
        visual_description: character.visual_description || ''
      };

      const result = await apiService.generateCharacterPortrait(
        charId,
        campaignId,
        {
          regenerate: true,
          character_data: characterData
        }
      );

      if (result.success) {
        // Notify parent component
        if (onPortraitGenerated) {
          onPortraitGenerated(result);
        }
      } else {
        setError(result.error || 'Failed to generate portrait');
      }
    } catch (err) {
      console.error('Error generating portrait:', err);
      setError(err.message || 'Failed to generate portrait');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className={`character-portrait-preview ${className}`}>
      <div className="portrait-preview-container">
        {portraitSrc ? (
          <img
            src={portraitSrc}
            alt={`${character.name} portrait`}
            className="portrait-image"
          />
        ) : (
          <div className="portrait-placeholder">
            <div className="portrait-placeholder-icon">🎨</div>
            <p className="portrait-placeholder-text">
              {placeholderText}
            </p>
          </div>
        )}

        {generating && (
          <div className="portrait-generating-overlay">
            <div className="spinner"></div>
            <p>Creating portrait...</p>
          </div>
        )}
      </div>

      <div className="portrait-actions">
        <Button
          onClick={handleGeneratePortrait}
          disabled={generating || !character?.name}
          className="generate-portrait-button"
          title={!character?.name ? 'Add character name first' : ''}
        >
          {generating ? '⏳ Generating...' : hasPortrait ? '🔄 Regenerate' : '🎨 Generate Portrait'}
        </Button>
      </div>

      {error && (
        <div className="portrait-error">
          ⚠️ {error}
        </div>
      )}

      {character?.portrait_prompt && (
        <div className="portrait-prompt-info">
          <small>Prompt: {character.portrait_prompt}</small>
        </div>
      )}
    </div>
  );
};

export default CharacterPortraitPreview;
