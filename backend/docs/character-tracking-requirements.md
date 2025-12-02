# Character Tracking System Requirements

## Executive Summary

The Character Tracking System extends Gaia's D&D campaign management with persistent character identity management. It tracks player characters and NPCs across sessions, maintains voice assignments from ElevenLabs, stores visual descriptions, and integrates seamlessly with the existing campaign persistence system.

## Functional Requirements

### 1. Campaign Start Modes

#### 1.1 New Campaign
- **Player Count Selection**: Users specify the number of players (1-8)
- **Character Creation Flow**:
  - For each player slot, collect:
    - Character name (required)
    - Description/background (optional, free text)
    - Option to generate LLM backstory based on description
  - Character creation is deterministic (user-driven, not LLM-driven)
  - All character data persisted immediately to campaign structure

#### 1.2 Blank Campaign
- **Character Extraction**: LLM analyzes campaign context to identify potential characters
- **Character Assignment UI**: 
  - Display extracted characters with suggested names
  - Allow users to:
    - Edit character names
    - Modify descriptions/backstories
    - Remove unwanted characters
    - Add missing characters

#### 1.3 Load Existing Campaign
- **Character Data Loading**: Load structured character data from `campaign_data.json`
- **Character State Restoration**: 
  - Restore all character attributes
  - Maintain voice assignments
  - Load visual descriptions

### 2. Character Data Structure

#### 2.1 Core Character Attributes
```json
{
  "character_id": "unique_id",
  "name": "Character Name",
  "character_type": "player|npc|creature",
  "description": "Physical and personality description",
  "backstory": "Character background story",
  "visual_description": "Detailed appearance for image generation",
  "voice_id": "elevenlabs_voice_id",
  "voice_settings": {
    "speed": 1.0,
    "pitch": 0,
    "emphasis": "normal"
  },
  "campaign_associations": {
    "campaign_id": {
      "version": "v1",
      "attributes": "CharacterInfo object",
      "first_appearance": "timestamp",
      "last_interaction": "timestamp"
    }
  }
}
```

#### 2.2 Character Versioning
- Characters stored in: `characters/{name}/version_{timestamp}`
- Support multiple versions per character (different campaigns/states)
- Version contains campaign-specific attributes (level, HP, equipment)

### 3. Character Persistence

#### 3.1 Storage Structure
```
data/
├── campaigns/
│   └── {campaign_id}/
│       └── campaign_data.json (includes characters field)
└── characters/
    └── {character_name}/
        ├── metadata.json
        ├── version_001/
        │   ├── attributes.json
        │   └── campaign_associations.json
        └── version_002/
            └── ...
```

#### 3.2 Campaign Integration
- Characters field in `campaign_data.json` contains full CharacterInfo
- Character registry maintains cross-campaign character data
- Synchronization between campaign-specific and global character data

### 4. Voice Management

#### 4.1 Voice Assignment
- Available ElevenLabs voices: priyanka, caleb, cornelius, alice, jon, lea, gary, mike, laura, jenna
- Automatic assignment based on character type/role
- Manual override through UI
- No duplicate voices for major characters in same campaign

#### 4.2 Voice Persistence
- Voice assignments stored with character profile
- Voice settings (speed, pitch) customizable per character
- Fallback to narrator voice if character voice unavailable

### 5. API Requirements

#### 5.1 Character Management Endpoints
```
POST   /api/campaigns/{campaign_id}/characters/setup
       Body: { player_count: number }
       Response: { setup_id, character_slots: [...] }

POST   /api/campaigns/{campaign_id}/characters
       Body: { name, description, character_type, generate_backstory }
       Response: { character_id, character_data }

GET    /api/campaigns/{campaign_id}/characters
       Response: { characters: [...] }

PUT    /api/campaigns/{campaign_id}/characters/{character_id}
       Body: { updates to character }
       Response: { updated character }

POST   /api/campaigns/{campaign_id}/characters/{character_id}/voice
       Body: { voice_id, voice_settings }
       Response: { success, voice_data }

POST   /api/characters/extract
       Body: { campaign_text }
       Response: { extracted_characters: [...] }

GET    /api/characters/{character_name}/versions
       Response: { versions: [...] }
```

### 6. Frontend Requirements

#### 6.1 Character Setup Page
- **Route**: `/campaigns/{campaign_id}/characters/setup`
- **Features**:
  - Player count selector (1-8)
  - Character creation forms
  - Backstory generation button
  - Voice preview/selection
  - Save and continue workflow

#### 6.2 Character Management Page
- **Route**: `/campaigns/{campaign_id}/characters`
- **Features**:
  - Character gallery with cards
  - Voice assignment interface
  - Character detail editing
  - Version history viewer
  - Quick character reference panel

#### 6.3 Campaign Creation Flow
```
1. New Campaign → Set player count → Character creation → Campaign ready
2. Blank Campaign → LLM extraction → Character review/edit → Campaign ready
3. Load Campaign → Character data loaded → Campaign ready
```

### 7. Integration Requirements

#### 7.1 Campaign System Integration
- Character data automatically included in campaign saves
- Character updates trigger campaign auto-save
- Character data included in campaign compaction

#### 7.2 DM Agent Integration
- DM receives character information at campaign start
- Character context included in agent prompts
- New character detection during gameplay

#### 7.3 TTS Integration
- Auto-TTS uses character-assigned voices
- Dialog attribution determines voice selection
- Narrator voice for non-character content

### 8. Non-Functional Requirements

#### 8.1 Performance
- Character lookup: < 50ms
- Voice assignment: < 100ms
- Character list loading: < 200ms for 100 characters

#### 8.2 Scalability
- Support 100+ characters per campaign
- Handle 50+ campaigns with shared characters
- Efficient character version management

#### 8.3 Data Integrity
- Atomic character updates
- Consistent state between campaign and character stores
- Backup before character modifications

## Technical Implementation Plan

### Phase 1: Data Models & Core Systems (Priority: High)
1. Extend CharacterInfo in campaign_data_models.py
2. Create character-specific models (CharacterProfile, CharacterVersion)
3. Implement CharacterRegistry
4. Create character persistence manager

### Phase 2: Campaign Integration (Priority: High)
1. Modify campaign creation flow
2. Add character setup to campaign initialization
3. Integrate character extraction for blank campaigns
4. Update campaign persistence to include characters

### Phase 3: API Development (Priority: Medium)
1. Create character management endpoints
2. Implement character extraction endpoint
3. Add voice assignment endpoints
4. Create character version management

### Phase 4: Frontend Implementation (Priority: Medium)
1. Create character setup component
2. Build character management page
3. Integrate with campaign creation flow
4. Add voice selection UI

### Phase 5: Voice & TTS Integration (Priority: Medium)
1. Extend auto-TTS for character voices
2. Implement voice pool management
3. Add voice preview functionality
4. Create voice archetype system

## Success Criteria

1. **Character Creation**: Users can create and customize characters during campaign setup
2. **Persistence**: Character data persists across sessions and campaigns
3. **Voice Assignment**: Each character has a unique, persistent voice
4. **Extraction**: Blank campaigns successfully extract and present characters for user confirmation
5. **Integration**: Character system seamlessly integrates with existing campaign flow
6. **Performance**: All operations complete within specified time limits
7. **User Experience**: Intuitive character management interface

## Future Enhancements

1. **Character Portraits**: AI-generated character images
2. **Voice Cloning**: Custom voices using ElevenLabs voice cloning
3. **Character Relationships**: Track inter-character relationships
4. **Character Templates**: Pre-built character archetypes
5. **Bulk Import/Export**: Character data migration tools