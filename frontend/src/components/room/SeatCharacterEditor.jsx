import React, { useMemo } from 'react';
import { Input } from '../base-ui/Input.jsx';
import { Textarea } from '../base-ui/Textarea.jsx';
import { Select } from '../base-ui/Select.jsx';
import { DatalistInput } from '../base-ui/DatalistInput.jsx';
import Button from '../base-ui/Button.jsx';
import VisualCustomizationForm from '../VisualCustomizationForm.jsx';
import CharacterPortraitPreview from '../CharacterPortraitPreview.jsx';

const CLASS_OPTIONS = [
  'Artificer', 'Barbarian', 'Bard', 'Cleric', 'Druid', 'Fighter',
  'Monk', 'Paladin', 'Ranger', 'Rogue', 'Sorcerer', 'Warlock', 'Wizard',
];

const RACE_OPTIONS = [
  'Dark Elf', 'Dragonborn', 'Dwarf', 'Genasi', 'Gnome', 'Goliath',
  'Half-Elf', 'Half-Orc', 'Halfling', 'High Elf', 'Human', 'Orc', 'Tiefling',
];

const SeatCharacterEditor = ({
  title,
  seat,
  character = {},
  campaignId,
  availableVoices = [],
  showVoiceSelect = true,
  headerContent = null,
  onFieldChange,
  onBulkChange,
  onGenerateBackstory,
  generatingBackstory = false,
}) => {
  const seatTitle = title
    || (seat?.slot_index !== undefined && seat?.slot_index !== null
      ? `Seat ${seat.slot_index + 1}`
      : 'Player Seat');

  const handleFieldChange = (field, value) => {
    if (onFieldChange) {
      onFieldChange(field, value);
      return;
    }
    if (onBulkChange) {
      onBulkChange({ [field]: value });
    }
  };

  const handleBulkChange = (updates) => {
    if (onBulkChange) {
      onBulkChange(updates);
      return;
    }
    if (onFieldChange) {
      Object.entries(updates).forEach(([field, value]) => {
        onFieldChange(field, value);
      });
    }
  };

  const voiceOptions = useMemo(() => ([
    { value: '', label: 'Auto-assign' },
    ...availableVoices.map((voice) => ({
      value: voice.id,
      label: voice.name || voice.id,
    })),
  ]), [availableVoices]);

  const canGenerateBackstory = Boolean(onGenerateBackstory && character?.description);

  const handlePortraitGenerated = (result) => {
    handleBulkChange({
      portrait_url: result?.image_url
        || result?.portrait_url
        || character?.portrait_url
        || null,
      portrait_path: result?.local_path
        || result?.portrait_path
        || character?.portrait_path
        || null,
      portrait_prompt: result?.prompt
        || result?.portrait_prompt
        || character?.portrait_prompt
        || null,
    });
  };

  const handleVisualChange = (updatedCharacter) => {
    const fields = [
      'gender',
      'age_category',
      'build',
      'height_description',
      'facial_expression',
      'facial_features',
      'attire',
      'primary_weapon',
      'distinguishing_feature',
      'background_setting',
      'pose',
    ];
    const updates = {};
    fields.forEach((field) => {
      if (updatedCharacter[field] !== character[field]) {
        updates[field] = updatedCharacter[field];
      }
    });
    if (Object.keys(updates).length > 0) {
      handleBulkChange(updates);
    }
  };

  return (
    <div className={`character-slot ${character?.is_filled ? 'filled' : ''}`}>
      <div className="character-slot-header">
        <h3>{seatTitle}</h3>
        {headerContent && (
          <div className="flex items-center gap-2 flex-wrap">
            {headerContent}
          </div>
        )}
      </div>

      <div className="character-basics-section">
        <div className="character-grid">
          <div className="form-group">
            <label>Character Name *</label>
            <Input
              type="text"
              value={character?.name || ''}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              placeholder="e.g., Elara Moonshadow"
              className="character-input"
            />
          </div>

          <div className="form-group">
            <label>Class *</label>
            <DatalistInput
              value={character?.character_class || ''}
              onChange={(value) => handleFieldChange('character_class', value)}
              placeholder="Type or select..."
              className="character-input"
              options={CLASS_OPTIONS.map((value) => ({ value, label: value }))}
            />
          </div>

          <div className="form-group">
            <label>Race *</label>
            <DatalistInput
              value={character?.race || ''}
              onChange={(value) => handleFieldChange('race', value)}
              placeholder="Type or select..."
              className="character-input"
              options={RACE_OPTIONS.map((value) => ({ value, label: value }))}
            />
          </div>

          <div className="form-group">
            <label>Gender *</label>
            <Select
              value={character?.gender || ''}
              onChange={(value) => handleFieldChange('gender', value)}
              className="character-select"
              options={[
                { value: '', label: 'Select...' },
                { value: 'Male', label: 'Male' },
                { value: 'Female', label: 'Female' },
                { value: 'Non-binary', label: 'Non-binary' }
              ]}
              forceNative={true}
            />
          </div>

          <div className="form-group">
            <label>Age *</label>
            <Select
              value={character?.age_category || ''}
              onChange={(value) => handleFieldChange('age_category', value)}
              className="character-select"
              options={[
                { value: '', label: 'Select...' },
                { value: 'Young', label: 'Young (18-25)' },
                { value: 'Adult', label: 'Adult (26-40)' },
                { value: 'Middle-aged', label: 'Middle-aged (41-60)' },
                { value: 'Elderly', label: 'Elderly (60+)' }
              ]}
              forceNative={true}
            />
          </div>
        </div>

        <div className="portrait-section">
          <CharacterPortraitPreview
            character={character}
            campaignId={campaignId}
            onPortraitGenerated={handlePortraitGenerated}
          />
        </div>
      </div>

      <div className="form-group">
        <label>Description</label>
        <Textarea
          value={character?.description || ''}
          onChange={(e) => handleFieldChange('description', e.target.value)}
          placeholder="Describe the character's appearance and personality..."
          className="character-textarea"
          rows={3}
        />
      </div>

      <div className="form-group">
        <label className="flex items-center gap-2">
          Backstory
          {canGenerateBackstory && (
            <Button
              onClick={onGenerateBackstory}
              disabled={generatingBackstory}
              variant="secondary"
              size="sm"
            >
              {generatingBackstory ? 'Generating...' : '✨ Generate with AI'}
            </Button>
          )}
        </label>
        <Textarea
          value={character?.backstory || ''}
          onChange={(e) => handleFieldChange('backstory', e.target.value)}
          placeholder="Where do they come from? Why are they adventuring?"
          className="character-textarea"
          rows={4}
        />
      </div>

      <div className="form-group">
        <label>Personality / Appearance Notes</label>
        <Textarea
          value={character?.appearance || ''}
          onChange={(e) => handleFieldChange('appearance', e.target.value)}
          placeholder="Catchphrases, quirks, distinguishing traits."
          className="character-textarea"
          rows={3}
        />
      </div>

      <div className="character-visual-section">
        <VisualCustomizationForm
          character={character}
          onChange={handleVisualChange}
          showVoiceSelect={showVoiceSelect}
          voiceOptions={voiceOptions}
          onFieldChange={handleFieldChange}
        />
      </div>
    </div>
  );
};

export default SeatCharacterEditor;
