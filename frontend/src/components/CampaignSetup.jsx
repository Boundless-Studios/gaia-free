import React, { useState, useEffect } from 'react';
import apiService from '../services/apiService';
import { Modal } from './base-ui/Modal';
import { Button } from './base-ui/Button';
import { Input } from './base-ui/Input';
import { Select } from './base-ui/Select';
import { Textarea } from './base-ui/Textarea';
import SeatCharacterEditor from './room/SeatCharacterEditor.jsx';
import './CampaignSetup.css';

// Centralized validation helper functions
const isCharacterComplete = (slot) => {
  // Empty slot (no name) is valid - DMs can skip
  if (!slot.name || slot.name.trim() === '') {
    return true;
  }

  // If slot has a name, check all required fields
  const hasClass = slot.character_class && slot.character_class.trim() !== '';
  const hasRace = slot.race && slot.race.trim() !== '';
  const hasGender = slot.gender && slot.gender.trim() !== '';
  const hasAge = slot.age_category && slot.age_category.trim() !== '';
  const hasPortrait = slot.portrait_url || slot.portrait_path;

  return hasClass && hasRace && hasGender && hasAge && hasPortrait;
};

const getIncompleteSlotsValidation = (slots) => {
  const namedSlots = slots.filter(slot => slot.name && slot.name.trim() !== '');
  const incompleteSlots = [];

  namedSlots.forEach(slot => {
    const missingFields = [];
    if (!slot.character_class || slot.character_class.trim() === '') missingFields.push('Class');
    if (!slot.race || slot.race.trim() === '') missingFields.push('Race');
    if (!slot.gender || slot.gender.trim() === '') missingFields.push('Gender');
    if (!slot.age_category || slot.age_category.trim() === '') missingFields.push('Age');
    if (!slot.portrait_url && !slot.portrait_path) missingFields.push('Portrait');

    if (missingFields.length > 0) {
      incompleteSlots.push({
        name: slot.name,
        missingFields
      });
    }
  });

  return {
    isValid: incompleteSlots.length === 0,
    incompleteSlots,
    hasAnyNamedCharacters: namedSlots.length > 0,
    allSlotsEmpty: namedSlots.length === 0
  };
};

const CampaignSetup = ({ isOpen, onComplete, onCancel, onCreateBlank }) => {
  const [step, setStep] = useState(1); // 1: Campaign Info, 2: Player Count, 3: Character Creation
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Campaign info - includes full data from auto-generation
  const [campaignInfo, setCampaignInfo] = useState({
    title: '',
    description: '',
    game_style: 'balanced',
    setting: '',
    theme: '',
    starting_location: '',
    main_conflict: '',
    key_npcs: [],
    potential_quests: []
  });

  // Track if campaign was pre-generated
  const [campaignWasPregenerated, setCampaignWasPregenerated] = useState(false);

  // Campaign setup mode
  const [_setupMode, _setSetupMode] = useState('new'); // new, blank, existing
  const [campaignId, setCampaignId] = useState(null);

  // Player setup
  const [playerCount, setPlayerCount] = useState(4);
  const [characterSlots, setCharacterSlots] = useState([]);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [generatingBackstory, setGeneratingBackstory] = useState({});
  const [pregeneratedCharacters, setPregeneratedCharacters] = useState([]);
  const [selectedCharacters, setSelectedCharacters] = useState({}); // slotId -> characterName

  // Track original pre-generated character data to detect modifications
  const [originalPregenData, setOriginalPregenData] = useState({});

  // Load available voices and pregenerated characters
  useEffect(() => {
    loadAvailableVoices();
    loadPregeneratedCharacters();
  }, []);

  const loadAvailableVoices = async () => {
    try {
      const data = await apiService.getTTSVoices();
      if (data.voices) {
        setAvailableVoices(data.voices);
      }
    } catch (error) {
      console.error('Error loading voices:', error);
    }
  };

  const loadPregeneratedCharacters = async () => {
    try {
      const data = await apiService.getPregeneratedCharacters();
      console.log('Loaded pregenerated characters:', data);
      if (data.characters) {
        setPregeneratedCharacters(data.characters);
        console.log('Set pregenerated characters count:', data.characters.length);
      }
    } catch (error) {
      console.error('Error loading pregenerated characters:', error);
    }
  };

  // Step 1: Create Campaign
  const createCampaign = async (count = playerCount) => {
    setLoading(true);
    setError('');

    try {
      const data = await apiService.createCampaign({
        name: campaignInfo.title,
        description: campaignInfo.description,
        game_style: campaignInfo.game_style,
        setup_characters: true,
        player_count: count
      });

      if (data.id) {
        setCampaignId(data.id);
        // Initialize character slots
        await loadCharacterSetup(data.id, count);
        setStep(3); // Skip to character creation
      } else {
        setError('Failed to create campaign');
      }
    } catch (error) {
      console.error('Error creating campaign:', error);
      setError('Error creating campaign: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Auto-fill all characters with generated data
  const autoFillAllCharacters = async () => {
    setLoading(true);
    setError('');

    try {
      const updatedSlots = [];

      for (let i = 0; i < characterSlots.length; i++) {
        const data = await apiService.generateCharacter({
          slot_id: i
        });

        if (data.success && data.character) {
          const char = data.character;
          const slotData = {
            ...characterSlots[i],
            name: char.name || `Player ${i + 1}`,
            character_class: char.character_class || 'Fighter',
            race: char.race || 'Human',
            level: char.level || 1,
            description: char.description || '',
            backstory: char.backstory || '',
            // Visual metadata fields for portrait generation
            gender: char.gender || '',
            age_category: char.age_category || '',
            build: char.build || '',
            height_description: char.height_description || '',
            facial_expression: char.facial_expression || '',
            facial_features: char.facial_features || '',
            attire: char.attire || '',
            primary_weapon: char.primary_weapon || '',
            distinguishing_feature: char.distinguishing_feature || '',
            background_setting: char.background_setting || '',
            pose: char.pose || '',
            is_filled: true,
            was_pregenerated: true  // Mark as pre-generated
          };
          updatedSlots.push(slotData);

          // Store original pre-generated data for comparison
          setOriginalPregenData(prev => ({
            ...prev,
            [i]: { ...char }
          }));
        } else {
          // Keep the original slot if generation failed
          updatedSlots.push(characterSlots[i]);
        }
      }

      setCharacterSlots(updatedSlots);
    } catch (error) {
      console.error('Error generating characters:', error);
      setError('Error generating characters: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Auto-fill campaign with generated data
  const autoFillCampaign = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await apiService.generateCampaign({});

      if (data.success && data.campaign) {
        setCampaignInfo({
          title: data.campaign.name || data.campaign.title || '',
          description: data.campaign.description || '',
          game_style: 'balanced',
          setting: data.campaign.setting || '',
          theme: data.campaign.theme || '',
          starting_location: data.campaign.starting_location || '',
          main_conflict: data.campaign.main_conflict || '',
          key_npcs: data.campaign.key_npcs || [],
          potential_quests: data.campaign.potential_quests || []
        });
        // Mark campaign as pre-generated
        setCampaignWasPregenerated(true);
      } else {
        setError('Failed to generate campaign');
      }
    } catch (error) {
      console.error('Error generating campaign:', error);
      setError('Error generating campaign: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Load character setup slots
  const loadCharacterSetup = async (campaignId, count) => {
    try {
      let seatIdMap = {};
      try {
        const seatResponse = await apiService.listSeats(campaignId);
        const playerSeats = seatResponse?.seats?.filter((seat) => seat.seat_type === 'player') || [];
        playerSeats.forEach((seat) => {
          if (seat.slot_index !== undefined && seat.slot_index !== null) {
            seatIdMap[seat.slot_index] = seat.seat_id;
          }
        });
      } catch (seatError) {
        console.warn('Failed to fetch room seats for campaign setup:', seatError);
      }

      // Create empty character slots based on player count
      const slots = Array.from({ length: count || playerCount }, (_, index) => ({
        slot_id: index,
        seat_id: seatIdMap[index] || null,
        name: '',
        character_class: '',
        race: '',
        level: 1,
        voice_id: '',
        description: '',
        backstory: '',
        is_filled: false
      }));

      setCharacterSlots(slots);
    } catch (error) {
      console.error('Error loading character setup:', error);
    }
  };

  // Update character slot
  const updateCharacterSlot = (slotId, field, value) => {
    setCharacterSlots(slots =>
      slots.map(slot => {
        if (slot.slot_id === slotId) {
          const updated = {
            ...slot,
            [field]: value,
            is_filled: field === 'name' ? value.trim() !== '' : slot.is_filled
          };

          // If this was a pre-generated character and user is modifying it,
          // check if the value differs from the original
          if (slot.was_pregenerated && originalPregenData[slotId]) {
            const original = originalPregenData[slotId];
            // Check if any field has been modified from original
            const isModified =
              (field === 'name' && value !== original.name) ||
              (field === 'character_class' && value !== original.character_class) ||
              (field === 'race' && value !== original.race) ||
              (field === 'level' && value !== original.level) ||
              (field === 'description' && value !== original.description) ||
              (field === 'backstory' && value !== original.backstory);

            if (isModified) {
              updated.is_modified = true;
            }
          }

          return updated;
        }
        return slot;
      })
    );
  };

  // Handle character selection from dropdown - instantly fill details
  const handleCharacterSelection = (slotId, characterName) => {
    // Update selected character
    setSelectedCharacters(prev => ({ ...prev, [slotId]: characterName }));

    // If empty string, clear the slot
    if (!characterName) {
      setCharacterSlots(slots =>
        slots.map(s =>
          s.slot_id === slotId
            ? {
              ...s,
              name: '',
              character_class: '',
              race: '',
              level: 1,
              description: '',
              backstory: '',
              appearance: '',
              visual_description: '',
              gender: '',
              age_category: '',
              build: '',
              height_description: '',
              facial_expression: '',
              facial_features: '',
              attire: '',
              primary_weapon: '',
              distinguishing_feature: '',
              background_setting: '',
              pose: '',
              is_filled: false,
              was_pregenerated: false
            }
            : s
        )
      );
      return;
    }

    // Find the character in pregeneratedCharacters
    const selectedChar = pregeneratedCharacters.find(c => c.name === characterName);
    if (selectedChar) {
      // Immediately populate the slot with character data
      setCharacterSlots(slots =>
        slots.map(s =>
          s.slot_id === slotId
            ? {
              ...s,
              name: selectedChar.name || '',
              character_class: selectedChar.character_class || '',
              race: selectedChar.race || '',
              level: selectedChar.level || 1,
              description: selectedChar.description || '',
              backstory: selectedChar.backstory || '',
              appearance: selectedChar.appearance || '',
              visual_description: selectedChar.visual_description || '',
              gender: selectedChar.gender || '',
              age_category: selectedChar.age_category || '',
              build: selectedChar.build || '',
              height_description: selectedChar.height_description || '',
              facial_expression: selectedChar.facial_expression || '',
              facial_features: selectedChar.facial_features || '',
              attire: selectedChar.attire || '',
              primary_weapon: selectedChar.primary_weapon || '',
              distinguishing_feature: selectedChar.distinguishing_feature || '',
              background_setting: selectedChar.background_setting || '',
              pose: selectedChar.pose || '',
              is_filled: true,
              was_pregenerated: true
            }
            : s
        )
      );

      // Store original pre-generated data for comparison
      setOriginalPregenData(prev => ({
        ...prev,
        [slotId]: { ...selectedChar }
      }));
    }
  };

  // Auto-fill character using AI (random generation via API)
  const autoFillCharacter = async (slotId) => {
    const slot = characterSlots.find(s => s.slot_id === slotId);
    if (!slot) return;

    setGeneratingBackstory(prev => ({ ...prev, [slotId]: true }));

    try {
      // Always pass null for character_name to get random character from API
      const data = await apiService.generateCharacter({
        slot_id: slotId,
        character_name: null
      });

      if (data.character) {
        // Update all fields with generated data including visual metadata
        setCharacterSlots(slots =>
          slots.map(s =>
            s.slot_id === slotId
              ? {
                ...s,
                name: data.character.name || s.name,
                character_class: data.character.character_class || s.character_class,
                race: data.character.race || s.race,
                level: data.character.level || s.level,
                description: data.character.description || s.description,
                backstory: data.character.backstory || s.backstory,
                // Visual metadata fields for portrait generation
                gender: data.character.gender || s.gender,
                age_category: data.character.age_category || s.age_category,
                build: data.character.build || s.build,
                height_description: data.character.height_description || s.height_description,
                facial_expression: data.character.facial_expression || s.facial_expression,
                facial_features: data.character.facial_features || s.facial_features,
                attire: data.character.attire || s.attire,
                primary_weapon: data.character.primary_weapon || s.primary_weapon,
                distinguishing_feature: data.character.distinguishing_feature || s.distinguishing_feature,
                background_setting: data.character.background_setting || s.background_setting,
                pose: data.character.pose || s.pose,
                is_filled: true,
                was_pregenerated: true  // Mark as pre-generated
              }
              : s
          )
        );

        // Store original pre-generated data for comparison
        setOriginalPregenData(prev => ({
          ...prev,
          [slotId]: { ...data.character }
        }));

        // Clear the dropdown selection since this was random
        setSelectedCharacters(prev => ({ ...prev, [slotId]: '' }));
      }
    } catch (error) {
      console.error('Error generating character:', error);
      setError('Failed to generate character. Please try again.');
    } finally {
      setGeneratingBackstory(prev => ({ ...prev, [slotId]: false }));
    }
  };

  // Generate backstory using AI
  const generateBackstory = async (slotId) => {
    const slot = characterSlots.find(s => s.slot_id === slotId);
    if (!slot || !slot.description) return;

    setGeneratingBackstory(prev => ({ ...prev, [slotId]: true }));

    try {
      // TODO: Implement character backstory generation endpoint in backend
      // For now, just show a placeholder message
      setTimeout(() => {
        updateCharacterSlot(slotId, 'backstory',
          `[Backstory generation is not yet implemented. Please write your own backstory for now.]`
        );
        setGeneratingBackstory(prev => ({ ...prev, [slotId]: false }));
      }, 1000);
    } catch (error) {
      console.error('Error generating backstory:', error);
      setGeneratingBackstory(prev => ({ ...prev, [slotId]: false }));
    }
  };

  // Save character slot
  const _saveCharacterSlot = async (slotId) => {
    const slot = characterSlots.find(s => s.slot_id === slotId);
    if (!slot) return;

    try {
      const data = await apiService.assignCharacterToSlot(campaignId, slot);
      if (data.updated) {
        console.log('Character slot saved');
      }
    } catch (error) {
      console.error('Error saving character slot:', error);
    }
  };

  // Finalize campaign setup using backend initialization
  const finalizeSetup = async () => {
    setLoading(true);
    // Clear any previous errors
    setError('');

    // Use centralized validation
    const validation = getIncompleteSlotsValidation(characterSlots);

    if (!validation.isValid) {
      const errorMessage = `Cannot start campaign. Please complete the following characters:\n${
        validation.incompleteSlots.map(slot =>
          `${slot.name} (missing: ${slot.missingFields.join(', ')})`
        ).join('\n')
      }`;
      console.error(errorMessage);
      setError(errorMessage);
      setLoading(false);
      return;
    }

    try {
      const defaultVisualValues = {
        gender: 'non-binary',
        facial_expression: 'determined',
        build: 'average'
      };

      // Build character slots array with per-slot configuration
      // Only include slots that have names defined
      const character_slots = characterSlots.map(slot => {
        const isFilled = slot.name && slot.name.trim() !== '';
        const usePregen = slot.was_pregenerated && !slot.is_modified;
        console.log(`Slot ${slot.slot_id}: was_pregenerated=${slot.was_pregenerated}, is_modified=${slot.is_modified}, use_pregenerated=${usePregen}`);
        const normalizedGender = slot.gender || defaultVisualValues.gender;
        const normalizedExpression = slot.facial_expression || defaultVisualValues.facial_expression;
        const normalizedBuild = slot.build || defaultVisualValues.build;
        return {
          slot_id: slot.slot_id,
          seat_id: slot.seat_id,
          // A character uses pre-generated data only if:
          // 1. It was originally pre-generated (was_pregenerated flag)
          // 2. It hasn't been modified by the user (no is_modified flag)
          use_pregenerated: usePregen,
          // Send character data if it's filled (has a name), regardless of source
          character_data: isFilled ? {
            name: slot.name,
            character_class: slot.character_class,
            race: slot.race,
            level: slot.level,
            description: slot.description,
            backstory: slot.backstory,
            voice_id: slot.voice_id,
            // Visual metadata for portrait generation
            gender: normalizedGender,
            age_category: slot.age_category,
            build: normalizedBuild,
            height_description: slot.height_description,
            facial_expression: normalizedExpression,
            facial_features: slot.facial_features,
            attire: slot.attire,
            primary_weapon: slot.primary_weapon,
            distinguishing_feature: slot.distinguishing_feature,
            background_setting: slot.background_setting,
            pose: slot.pose,
            // Portrait data (required)
            portrait_url: slot.portrait_url || null,
            portrait_path: slot.portrait_path || null,
            portrait_prompt: slot.portrait_prompt || null
          } : null
        };
      });

      console.log(`Campaign: was_pregenerated=${campaignWasPregenerated}`);

      // Call the backend to initialize the campaign with all context
      const result = await apiService.initializeCampaign({
        campaign_id: campaignId,
        campaign_info: campaignInfo,
        use_pregenerated_campaign: campaignWasPregenerated,  // True only if auto-generated and not edited
        character_slots
      });

      if (result.success) {
        console.log('✅ Campaign initialized in setup state. Use Room Management to start when ready.');
        if (onComplete) {
          onComplete(campaignId);
        }
      } else {
        throw new Error('Failed to initialize campaign');
      }
    } catch (error) {
      console.error('Error finalizing setup:', error);
      setError('Error finalizing setup: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Render campaign info step
  const renderCampaignInfo = () => (
    <div className="campaign-setup-step">
      <div className="step-header">
        <h2>Create New Campaign</h2>
        <div className="step-header-buttons">
          <Button
            onClick={autoFillCampaign}
            className="auto-fill-button"
            disabled={loading}
          >
            🎲 Auto-Generate Campaign
          </Button>
          {onCreateBlank && (
            <Button
              onClick={() => {
                onCreateBlank();
                onCancel();
              }}
              className="blank-campaign-button"
              variant="secondary"
              disabled={loading}
            >
              📋 Blank Campaign
            </Button>
          )}
        </div>
      </div>

      <div className="form-group">
        <label>Campaign Title</label>
        <Input
          type="text"
          value={campaignInfo.title}
          onChange={(e) => {
            setCampaignInfo({ ...campaignInfo, title: e.target.value });
            // Clear pre-generated flag if user modifies
            if (campaignWasPregenerated) {
              setCampaignWasPregenerated(false);
            }
          }}
          placeholder="Enter campaign title..."
          className="campaign-input"
        />
      </div>

      <div className="form-group">
        <label>Description</label>
        <Textarea
          value={campaignInfo.description}
          onChange={(e) => {
            setCampaignInfo({ ...campaignInfo, description: e.target.value });
            // Clear pre-generated flag if user modifies
            if (campaignWasPregenerated) {
              setCampaignWasPregenerated(false);
            }
          }}
          placeholder="Describe your campaign..."
          className="campaign-textarea"
          rows={4}
        />
      </div>

      <div className="form-group">
        <label>Game Style</label>
        <Select
          value={campaignInfo.game_style}
          onChange={(value) => setCampaignInfo({ ...campaignInfo, game_style: value })}
          className="campaign-select"
          options={[
            { value: 'balanced', label: 'Balanced' },
            { value: 'combat_heavy', label: 'Combat Heavy' },
            { value: 'roleplay_heavy', label: 'Roleplay Heavy' },
            { value: 'exploration', label: 'Exploration' }
          ]}
        />
      </div>

      <div className="button-group">
        <Button onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button
          onClick={() => setStep(2)}
          disabled={!campaignInfo.title.trim()}
          variant="primary"
        >
          Next: Player Setup
        </Button>
      </div>
    </div>
  );

  // Render player count step
  const renderPlayerCount = () => (
    <div className="campaign-setup-step">
      <h2>Player Setup</h2>

      <div className="form-group">
        <label>Number of Players</label>
        <div className="player-count-selector">
          {[1, 2, 3, 4, 5, 6, 7, 8].map(count => (
            <Button
              key={count}
              className={`player-count-button ${playerCount === count ? 'selected' : ''}`}
              onClick={() => {
                setPlayerCount(count);
                createCampaign(count);
              }}
              variant={playerCount === count ? 'primary' : 'secondary'}
            >
              {count}
            </Button>
          ))}
        </div>
        <p className="help-text">Select how many player characters will be in your campaign</p>
      </div>

      <div className="button-group">
        <Button onClick={() => setStep(1)} variant="secondary">
          Back
        </Button>
        <Button
          onClick={() => createCampaign()}
          disabled={loading}
          variant="primary"
          loading={loading}
        >
          {loading ? 'Creating...' : 'Create Campaign & Setup Characters'}
        </Button>
      </div>

      {error && <div className="error-message">{error}</div>}
    </div>
  );

  // Render character creation step
  const renderCharacterCreation = () => {
    const validation = getIncompleteSlotsValidation(characterSlots);
    const buttonText = validation.allSlotsEmpty
      ? '⏭️ Skip & Start Campaign'
      : '🎮 Start Campaign';

    return (
      <div className="campaign-setup-step character-creation">
        <div className="step-header">
          <div>
            <h2>Create Characters (Optional)</h2>
            <p className="help-text">
              Pre-create characters now, or leave empty and let players create their own when they join.
            </p>
          </div>
          <div className="header-buttons">
            <Button
              onClick={autoFillAllCharacters}
              className="auto-fill-button"
              disabled={loading}
            >
              🎭 Auto-fill All Characters
            </Button>
            <Button
              onClick={finalizeSetup}
              disabled={loading || !validation.isValid}
              variant="primary"
              className="start-campaign-top"
              loading={loading}
            >
              {loading ? 'Creating Campaign...' : buttonText}
            </Button>
          </div>
        </div>

        <div className="character-slots">
          {characterSlots.map((slot, index) => {
            const headerControls = (
              <>
                <Select
                  value={selectedCharacters[slot.slot_id] || ''}
                  onChange={(value) => handleCharacterSelection(slot.slot_id, value)}
                  className="min-w-[180px]"
                  disabled={generatingBackstory[slot.slot_id]}
                  placeholder="Select a character..."
                  forceNative={true}
                  options={[
                    { value: '', label: 'Select a character...' },
                    ...pregeneratedCharacters.map((char) => ({
                      value: char.name,
                      label: `${char.name} (${char.race} ${char.character_class})`,
                    })),
                  ]}
                />
                <Button
                  onClick={() => autoFillCharacter(slot.slot_id)}
                  disabled={generatingBackstory[slot.slot_id]}
                  className="auto-fill-button"
                  loading={generatingBackstory[slot.slot_id]}
                >
                  {generatingBackstory[slot.slot_id] ? 'Generating...' : '🎲 Random'}
                </Button>
              </>
            );

            const handleBulkChange = (updates) => {
              Object.entries(updates).forEach(([field, value]) => {
                updateCharacterSlot(slot.slot_id, field, value);
              });
            };

            return (
              <SeatCharacterEditor
                key={slot.slot_id}
                title={`Player ${index + 1}`}
                seat={{ slot_index: index }}
                character={slot}
                campaignId={campaignId}
                availableVoices={availableVoices}
                headerContent={headerControls}
                onFieldChange={(field, value) => updateCharacterSlot(slot.slot_id, field, value)}
                onBulkChange={handleBulkChange}
                onGenerateBackstory={slot.description ? () => generateBackstory(slot.slot_id) : null}
                generatingBackstory={Boolean(generatingBackstory[slot.slot_id])}
              />
            );
          })}
        </div>

        <div className="button-group">
          <Button onClick={onCancel} variant="secondary">
            Cancel
          </Button>
          <Button
            onClick={finalizeSetup}
            disabled={loading || !validation.isValid}
            variant="primary"
            loading={loading}
          >
            {loading ? 'Creating Characters...' : buttonText}
          </Button>
        </div>

        {error && <div className="error-message">{error}</div>}
      </div>
    );
  };

  return (
    <Modal
      open={isOpen}
      onClose={onCancel}
      title="Campaign Setup"
      width="max-w-6xl"
      className="h-[85vh]"
    >
      <div className="campaign-setup-container">
        <div className="campaign-setup-progress">
          <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>
            <span className="step-number">1</span>
            <span className="step-label">Campaign Info</span>
          </div>
          <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>
            <span className="step-number">2</span>
            <span className="step-label">Player Count</span>
          </div>
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>
            <span className="step-number">3</span>
            <span className="step-label">Create Characters</span>
          </div>
        </div>

        <div className="campaign-setup-content">
          {step === 1 && renderCampaignInfo()}
          {step === 2 && renderPlayerCount()}
          {step === 3 && renderCharacterCreation()}
        </div>
      </div>
    </Modal>
  );
};

export default CampaignSetup;
