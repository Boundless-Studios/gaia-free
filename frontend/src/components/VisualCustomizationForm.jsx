import React, { useState } from 'react';
import { Select } from './base-ui/Select';
import { DatalistInput } from './base-ui/DatalistInput';
import { Input } from './base-ui/Input';
import { Textarea } from './base-ui/Textarea';
import './VisualCustomizationForm.css';

const VisualCustomizationForm = ({
  character,
  onChange,
  className = '',
  showVoiceSelect = false,
  voiceOptions = [],
  onFieldChange
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleFieldChange = (field, value) => {
    // For voice and level, use the onFieldChange prop directly (doesn't go through onChange)
    if ((field === 'voice_id' || field === 'level') && onFieldChange) {
      onFieldChange(field, value);
      return;
    }

    if (onChange) {
      onChange({ ...character, [field]: value });
    }
  };

  return (
    <div className={`visual-customization-form ${className}`}>
      {/* Advanced Visual Fields - Expandable */}
      <div className="visual-form-section">
        <button
          type="button"
          className="section-toggle"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
          <h4 className="section-title">Advanced Customization</h4>
        </button>

        {isExpanded && (
          <div className="advanced-fields">
            {/* Row 1: Level + Voice */}
            <div className="form-row">
              <div className="form-group">
                <label>Level</label>
                <Input
                  type="number"
                  value={character?.level || 1}
                  min="1"
                  max="20"
                  onChange={(e) => handleFieldChange('level', parseInt(e.target.value, 10) || 1)}
                  className="character-input"
                />
              </div>

              {showVoiceSelect && (
                <div className="form-group">
                  <label>Voice</label>
                  <Select
                    value={character?.voice_id || ''}
                    onChange={(value) => handleFieldChange('voice_id', value)}
                    className="character-select"
                    options={voiceOptions}
                    forceNative={true}
                  />
                </div>
              )}
            </div>

            {/* Row 2: Build + Height */}
            <div className="form-row">
              <div className="form-group">
                <label>Build</label>
                <Select
                  value={character?.build || ''}
                  onChange={(value) => handleFieldChange('build', value)}
                  options={[
                    { value: '', label: 'Select...' },
                    { value: 'Slender', label: 'Slender' },
                    { value: 'Athletic', label: 'Athletic' },
                    { value: 'Muscular', label: 'Muscular' },
                    { value: 'Stocky', label: 'Stocky' },
                    { value: 'Heavyset', label: 'Heavyset' }
                  ]}
                  forceNative={true}
                />
              </div>

              <div className="form-group">
                <label>Height</label>
                <Input
                  type="text"
                  value={character?.height_description || ''}
                  onChange={(e) => handleFieldChange('height_description', e.target.value)}
                  placeholder="e.g., tall, average, short"
                />
              </div>
            </div>

            {/* Row 3: Facial Expression + Primary Weapon */}
            <div className="form-row">
              <div className="form-group">
                <label>Facial Expression</label>
                <DatalistInput
                  value={character?.facial_expression || ''}
                  onChange={(value) => handleFieldChange('facial_expression', value)}
                  options={[
                    { value: 'Calm', label: 'Calm' },
                    { value: 'Confident', label: 'Confident' },
                    { value: 'Determined', label: 'Determined' },
                    { value: 'Excited', label: 'Excited' },
                    { value: 'Fierce', label: 'Fierce' },
                    { value: 'Friendly', label: 'Friendly' },
                    { value: 'Haunted', label: 'Haunted' },
                    { value: 'Joyful', label: 'Joyful' },
                    { value: 'Mysterious', label: 'Mysterious' },
                    { value: 'Serene', label: 'Serene' },
                    { value: 'Stern', label: 'Stern' },
                    { value: 'Wise', label: 'Wise' },
                    { value: 'Brooding', label: 'Brooding' }
                  ]}
                  placeholder="Type or select..."
                />
              </div>

              <div className="form-group">
                <label>Primary Weapon/Item</label>
                <Input
                  type="text"
                  value={character?.primary_weapon || ''}
                  onChange={(e) => handleFieldChange('primary_weapon', e.target.value)}
                  placeholder="e.g., greatsword, staff, daggers"
                />
              </div>
            </div>

            {/* Row 4: Facial Features + Attire */}
            <div className="form-row">
              <div className="form-group">
                <label>Facial Features</label>
                <Textarea
                  value={character?.facial_features || ''}
                  onChange={(e) => handleFieldChange('facial_features', e.target.value)}
                  placeholder="e.g., thick beard, blue eyes, scar"
                  rows={2}
                />
              </div>

              <div className="form-group">
                <label>Attire/Clothing</label>
                <Textarea
                  value={character?.attire || ''}
                  onChange={(e) => handleFieldChange('attire', e.target.value)}
                  placeholder="e.g., leather armor, robes"
                  rows={2}
                />
              </div>
            </div>

            {/* Row 5: Distinguishing Feature + Background Setting */}
            <div className="form-row">
              <div className="form-group">
                <label>Distinguishing Feature</label>
                <Textarea
                  value={character?.distinguishing_feature || ''}
                  onChange={(e) => handleFieldChange('distinguishing_feature', e.target.value)}
                  placeholder="e.g., arcane tattoos, scars"
                  rows={2}
                />
              </div>

              <div className="form-group">
                <label>Background/Setting</label>
                <Input
                  type="text"
                  value={character?.background_setting || ''}
                  onChange={(e) => handleFieldChange('background_setting', e.target.value)}
                  placeholder="e.g., misty forest, library"
                />
              </div>
            </div>

            {/* Row 6: Pose */}
            <div className="form-row">
              <div className="form-group">
                <label>Pose/Action</label>
                <Select
                  value={character?.pose || ''}
                  onChange={(value) => handleFieldChange('pose', value)}
                  options={[
                    { value: '', label: 'Select...' },
                    { value: 'Standing Confident', label: 'Standing Confident' },
                    { value: 'Arms Crossed', label: 'Arms Crossed' },
                    { value: 'Weapon Ready', label: 'Weapon Ready' },
                    { value: 'Casting Spell', label: 'Casting Spell' },
                    { value: 'Seated Thoughtful', label: 'Seated Thoughtful' },
                    { value: 'Looking Over Shoulder', label: 'Looking Over Shoulder' }
                  ]}
                  forceNative={true}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VisualCustomizationForm;
