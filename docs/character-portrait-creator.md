# Character Portrait Creator Feature Specification

## Overview
A comprehensive character portrait generation system that allows players to customize and generate AI-powered portrait images during character creation. The system integrates visual customization with character metadata, providing persistence across campaigns and visibility in both DM and player views.

**Key Design Decision**: This feature leverages the existing [ImageGeneratorAgent.run_without_tools()](/mnt/c/Users/haroon/Gaia-new/backend/src/game/dnd_agents/image_generator.py:485-512) pattern and [enhance_prompt()](/mnt/c/Users/haroon/Gaia-new/backend/src/game/dnd_agents/image_generator.py:331-413) method, which already has portrait-specific enhancement logic. We simply:
1. Build a raw prompt from character metadata fields
2. Call `ImageGeneratorAgent.generate()` with `image_type="portrait"`
3. The existing system handles prompt enhancement and image generation

This ensures consistent quality and minimal new code.

## Feature Description

### User Experience Flow
1. **Character Creation Screen**: User creates a character with basic and advanced visual customization options
2. **Portrait Generation**: User requests AI-generated portrait based on their specifications
3. **Iterative Refinement**: User can edit visual features and regenerate until satisfied
4. **Persistence**: Portrait and metadata are saved with character data
5. **Display**: Portrait visible in character sheets (player view) and DM interface

## Visual Customization Schema

### Basic Attributes (Always Visible)
These fields are fundamental to character identity and always displayed:

- **Name** (string): Character's full name
- **Race** (enum): Character species/lineage
  - Options: Human, Orc, Dark Elf, Wood Elf, High Elf, Dragonborn, Tiefling, Rock Gnome, Forest Gnome, Halfling, Dwarf, Half-Elf, Half-Orc
- **Gender** (enum): Character gender presentation
  - Options: Male, Female, Non-binary
  - **Default**: "non-binary" (applied automatically if not specified)
- **Class** (enum): Character's primary profession/archetype
  - Options: Barbarian, Rogue, Wizard, Cleric, Monk, Warlock, Ranger, Fighter, Bard, Paladin, Druid, Sorcerer, Artificer

### Advanced Attributes (Expandable Section)
These fields provide detailed visual customization, accessible via dropdown/accordion:

#### Physical Characteristics
- **Age Category** (enum): Visual age representation
  - Options: Young (18-25), Adult (26-40), Middle-aged (41-60), Elderly (60+)
- **Build** (enum): Body type/physique
  - Options: Slender, Athletic, Muscular, Stocky, Heavyset
  - **Default**: "average" (applied automatically if not specified)
- **Height** (string): Character height description
  - Examples: "tall", "average height", "short", "towering", "diminutive"

#### Facial Features
- **Facial Expression** (enum): Default emotional state/demeanor
  - Options: Confident, Serene, Determined, Friendly, Stern, Mysterious, Joyful, Brooding, Wise, Fierce
  - **Default**: "determined" (applied automatically if not specified)
- **Distinguishing Facial Features** (text): Unique facial characteristics
  - Examples: "thick black beard", "piercing blue eyes", "facial scar across left cheek", "angular cheekbones", "network of tattoos"

#### Appearance & Attire
- **Attire/Clothing** (text): Description of outfit and armor
  - Examples: "fur-lined leather armor", "dark robes with silver trim", "gleaming plate armor", "simple traveler's cloak"
- **Primary Weapon/Item** (text): Main equipment held or visible
  - Examples: "greatsword", "ornate staff with crystal", "twin daggers", "longbow"
- **Distinguishing Feature** (text): Single most unique visual element
  - Examples: "glowing arcane tattoos on arms", "spectral wolf companion", "mechanical arm prosthetic", "crown of thorns"

#### Environmental Context
- **Background/Setting** (text): Environment for the portrait
  - Examples: "misty forest", "grand library", "mountain peak", "tavern interior"
- **Pose/Action** (enum): Character pose in portrait
  - Options: Standing Confident, Arms Crossed, Weapon Ready, Casting Spell, Seated Thoughtful, Looking Over Shoulder

## Data Architecture

### Design Principle: Separation of Concerns

This feature implements a clear separation between **character identity** (global, immutable) and **campaign state** (local, mutable):

**CharacterProfile** (Global Registry)
- Single source of truth for character identity and appearance
- Stored in `{CAMPAIGN_STORAGE_PATH}/character_profiles/{character_id}.json`
- Shared across all campaigns the character participates in
- Contains: visual metadata, voice settings, portraits, backstory, base stats

**CharacterInfo** (Campaign State)
- Campaign-specific character state: HP, inventory, location, quest progress
- References a CharacterProfile via `profile_id`
- Contains only mutable state that changes during gameplay
- Does NOT duplicate appearance or identity data

**EnrichedCharacter** (API View)
- Merged view of CharacterProfile + CharacterInfo for API responses
- Frontend receives complete character data in one call
- Backend resolves references and merges data on demand

**Campaign** (References Only)
- Stores list of `character_ids` participating in the campaign
- Does NOT store character data directly
- Loads character data via references when needed

### Data Flow Diagram

```
┌─────────────────────────────────────┐
│     CharacterProfile (Global)       │
│  - character_id, name, race, class  │
│  - Visual metadata (gender, build)  │
│  - Portrait (url, path, prompt)     │
│  - Voice settings                   │
│  - Backstory, descriptions          │
└──────────────┬──────────────────────┘
               │ Referenced by
               │ profile_id
               ▼
┌─────────────────────────────────────┐
│    CharacterInfo (Campaign State)   │
│  - character_id, profile_id         │
│  - HP, AC, status, inventory        │
│  - Location, quests                 │
│  - Level override (optional)        │
└──────────────┬──────────────────────┘
               │ Merged for API
               ▼
┌─────────────────────────────────────┐
│      EnrichedCharacter (API)        │
│  - Complete character view          │
│  - Identity + State combined        │
│  - Frontend-ready format            │
└─────────────────────────────────────┘
```

### Benefits
1. **No Duplication**: Same character in multiple campaigns shares one profile
2. **Single Source of Truth**: All appearance data lives in CharacterProfile
3. **Clear Boundaries**: Identity vs. state separation
4. **Performance**: Profile caching reduces I/O
5. **Maintainability**: Changes to appearance update all campaigns automatically

## Data Schema Extensions

### CharacterProfile Model Extensions
Enhance [character_profile.py](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/models/character_profile.py) to be the single source of truth:

```python
@dataclass
class CharacterProfile:
    character_id: str
    name: str
    character_type: CharacterType = CharacterType.NPC

    # Core identity (NEW - moved from CharacterInfo)
    race: str = "human"
    character_class: str = "adventurer"
    base_level: int = 1  # Default level, campaigns can override

    # Voice assignment (EXISTING)
    voice_id: Optional[str] = None
    voice_settings: Dict[str, Any] = field(default_factory=dict)
    voice_archetype: Optional[VoiceArchetype] = None

    # Visual representation (ENHANCED)
    portrait_url: Optional[str] = None  # NEW - add URL support
    portrait_path: Optional[str] = None
    portrait_prompt: Optional[str] = None
    additional_images: List[str] = field(default_factory=list)

    # Visual metadata (NEW - moved from CharacterInfo)
    gender: Optional[str] = None  # Male, Female, Non-binary
    age_category: Optional[str] = None  # Young, Adult, Middle-aged, Elderly
    build: Optional[str] = None  # Slender, Athletic, Muscular, etc.
    height_description: Optional[str] = None  # tall, average, short, etc.
    facial_expression: Optional[str] = None  # Confident, Serene, Determined, etc.
    facial_features: Optional[str] = None  # Distinguishing facial characteristics
    attire: Optional[str] = None  # Clothing and armor description
    primary_weapon: Optional[str] = None  # Main weapon/item
    distinguishing_feature: Optional[str] = None  # Most unique visual element
    background_setting: Optional[str] = None  # Environmental context
    pose: Optional[str] = None  # Character pose/action

    # Descriptions (NEW - moved from CharacterInfo)
    backstory: str = ""
    description: str = ""  # Physical and personality description
    appearance: str = ""  # Visual appearance for consistency
    visual_description: str = ""  # Detailed appearance for image generation

    # Metadata (EXISTING)
    first_created: datetime = field(default_factory=datetime.now)
    total_interactions: int = 0
```

### CharacterInfo Model Refactoring
Refactor [character_info.py](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/models/character_info.py) to focus on campaign state:

```python
@dataclass
class CharacterInfo:
    character_id: str
    profile_id: str  # NEW - explicit link to CharacterProfile

    # Campaign-specific overrides (optional)
    level: Optional[int] = None  # If None, use profile.base_level

    # Campaign state (KEEP ALL EXISTING FIELDS)
    hit_points_current: int = 10
    hit_points_max: int = 10
    armor_class: int = 10
    status: CharacterStatus = CharacterStatus.HEALTHY
    inventory: Dict[str, Item] = field(default_factory=dict)
    location: Optional[str] = None
    # ... all existing combat/state fields

    # REMOVE: All visual metadata fields (moved to CharacterProfile)
    # portrait_url, portrait_path, portrait_prompt
    # gender, age_category, build, height_description
    # facial_expression, facial_features, attire, primary_weapon
    # distinguishing_feature, background_setting, pose
```

**Note**: Visual metadata is removed from CharacterInfo during Phase 2 of the refactoring (after migration script runs).

### EnrichedCharacter Model (NEW)
Create [enriched_character.py](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/models/enriched_character.py):

```python
@dataclass
class EnrichedCharacter:
    """Merged view of CharacterInfo + CharacterProfile for API responses.

    This provides a complete character view to frontend without requiring
    separate calls. All identity data comes from CharacterProfile, all
    campaign state comes from CharacterInfo.
    """

    # From CharacterProfile (identity)
    character_id: str
    profile_id: str
    name: str
    race: str
    character_class: str
    gender: Optional[str]
    age_category: Optional[str]
    build: Optional[str]
    height_description: Optional[str]
    facial_expression: Optional[str]
    facial_features: Optional[str]
    attire: Optional[str]
    primary_weapon: Optional[str]
    distinguishing_feature: Optional[str]
    background_setting: Optional[str]
    pose: Optional[str]
    portrait_url: Optional[str]
    portrait_path: Optional[str]
    portrait_prompt: Optional[str]
    voice_id: Optional[str]
    backstory: str

    # From CharacterInfo (campaign state)
    level: int  # Resolved from profile.base_level or campaign override
    hit_points_current: int
    hit_points_max: int
    armor_class: int
    status: CharacterStatus
    inventory: Dict[str, Item]
    location: Optional[str]
    # ... all campaign state fields

    @classmethod
    def from_character_and_profile(
        cls,
        character_info: CharacterInfo,
        profile: CharacterProfile
    ) -> 'EnrichedCharacter':
        """Merge CharacterInfo and CharacterProfile into enriched view."""
        level = character_info.level if character_info.level else profile.base_level

        return cls(
            # Identity from profile
            character_id=profile.character_id,
            profile_id=profile.character_id,
            name=profile.name,
            race=profile.race,
            character_class=profile.character_class,
            gender=profile.gender,
            age_category=profile.age_category,
            # ... all profile fields

            # State from campaign
            level=level,
            hit_points_current=character_info.hit_points_current,
            # ... all campaign state fields
        )
```

### Pregenerated Character Extensions
Update [characters.json](/mnt/c/Users/haroon/Gaia-new/campaign_storage/pregenerated/characters.json) with portrait metadata:

For each character entry, add:
```json
{
  "name": "Character Name",
  "race": "Human",
  "gender": "Male",
  "character_class": "Fighter",
  "age_category": "Adult",
  "build": "Muscular",
  "height_description": "tall",
  "facial_expression": "Determined",
  "facial_features": "broken nose, hazel eyes, short chestnut hair",
  "attire": "steel breastplate over red tabard",
  "primary_weapon": "longsword",
  "distinguishing_feature": "battle scars on arms",
  "background_setting": "training grounds",
  "pose": "Standing Confident"
}
```

## Backend Implementation

### Architecture Overview

The portrait generation system leverages the existing [ImageGeneratorAgent](/mnt/c/Users/haroon/Gaia-new/backend/src/game/dnd_agents/image_generator.py) infrastructure:

**Execution Flow**:
1. **CharacterPortraitGenerator** builds raw prompt from character metadata
2. Calls **ImageGeneratorAgent.generate()** with `image_type="portrait"`
3. **generate()** routes portraits to **run_without_tools()** (line 530-532)
4. **run_without_tools()** uses **enhance_prompt()** to refine the raw prompt using AI (line 502)
5. **enhance_prompt()** uses portrait-specific enhancement logic (lines 362-378)
6. **generate_image_tool()** creates the final image with the enhanced prompt (lines 505-510)

This pattern ensures:
- ✅ Consistent image quality using proven enhancement logic
- ✅ Single-turn generation (faster, more predictable than multi-turn)
- ✅ Portrait-specific prompt optimization already implemented
- ✅ Minimal new code - reuses existing infrastructure

**Visual Flow Diagram**:
```
Character Metadata (name, race, gender, class, facial_expression, etc.)
    ↓
CharacterPortraitGenerator._build_portrait_prompt()
    ↓ (raw prompt: "Garrick, determined, male, Human, adult, Fighter, ...")
ImageGeneratorAgent.generate(prompt, image_type="portrait")
    ↓ (routes portraits to run_without_tools)
ImageGeneratorAgent.run_without_tools()
    ↓
ImageGeneratorAgent.enhance_prompt(raw_prompt, "portrait")
    ↓ (AI enhances: "Garrick, determined male Human adult Fighter with...")
    ↓ (uses portrait enhancement logic lines 362-378)
generate_image_tool(enhanced_prompt, image_type="portrait")
    ↓ (applies portrait style template line 28)
    ↓ ("D&D Photorealistic face closeup, cinematic portrait...")
ImageServiceManager.generate_image()
    ↓
Portrait Image (saved to campaign media directory)
```

### 1. API Endpoints

Create new endpoints in character management:

#### `/api/characters/{character_id}/portrait/generate` (POST)
Generate a portrait for a character.

**Request Body:**
```json
{
  "character_id": "char_abc123",
  "regenerate": false,  // If true, regenerate even if portrait exists
  "custom_prompt_additions": ""  // Optional user additions to prompt
}
```

**Response:**
```json
{
  "success": true,
  "portrait_url": "file:///path/to/portrait.png",
  "portrait_path": "/campaigns/campaign_123/media/portraits/char_abc123.png",
  "prompt_used": "Enhanced prompt that was sent to image generator...",
  "character_id": "char_abc123"
}
```

#### `/api/characters/{character_id}/portrait` (GET)
Retrieve existing portrait information.

**Response:**
```json
{
  "character_id": "char_abc123",
  "portrait_url": "file:///path/to/portrait.png",
  "portrait_path": "/path/to/portrait.png",
  "has_portrait": true
}
```

#### `/api/characters/{character_id}` (PATCH)
Update character visual metadata.

**Request Body:**
```json
{
  "age_category": "Adult",
  "facial_expression": "Confident",
  "attire": "Updated armor description",
  // ... any visual fields
}
```

### 2. Portrait Generation Service

Create `backend/src/core/character/portrait_generator.py`:

**Design Pattern**: This service follows the existing [ImageGeneratorAgent.run_without_tools](/mnt/c/Users/haroon/Gaia-new/backend/src/game/dnd_agents/image_generator.py:485-512) pattern:
1. Build a raw prompt from character metadata
2. Call `ImageGeneratorAgent.generate()` with `image_type="portrait"`
3. The `generate()` method automatically routes portraits to `run_without_tools()` (line 530)
4. `run_without_tools()` uses `enhance_prompt()` to refine the raw prompt (line 502)
5. Finally calls `generate_image_tool()` to create the image (lines 505-510)

This leverages the existing portrait-specific enhancement logic at lines 362-378.

```python
"""Character portrait generation service."""

from src.game.dnd_agents.image_generator import ImageGeneratorAgent
from src.core.character.models.character_info import CharacterInfo
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CharacterPortraitGenerator:
    """Generates character portraits using the existing ImageGenerator agent.

    Follows the run_without_tools pattern:
    - Build raw prompt from character metadata
    - ImageGenerator.generate() routes to run_without_tools() for portraits
    - enhance_prompt() refines the raw prompt using AI
    - generate_image_tool() creates the final image
    """

    def __init__(self):
        self.image_generator = ImageGeneratorAgent()

    async def generate_portrait(
        self,
        character_info: CharacterInfo,
        session_id: Optional[str] = None,
        custom_additions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a portrait for a character.

        This method follows the ImageGeneratorAgent.run_without_tools() pattern:
        1. Build raw prompt from character metadata
        2. Call ImageGenerator.generate() with image_type="portrait"
        3. generate() routes portraits through run_without_tools()
        4. run_without_tools() uses enhance_prompt() to refine the prompt
        5. Finally calls generate_image_tool() to create the image

        Args:
            character_info: CharacterInfo object with visual metadata
            session_id: Campaign ID for session-scoped media
            custom_additions: Optional user-provided prompt additions

        Returns:
            Dict with success status, portrait URL, path, and metadata:
            {
                "success": True,
                "image_url": "file:///path/to/portrait.png",
                "local_path": "/path/to/portrait.png",
                "prompt": "Enhanced prompt used for generation",
                "type": "portrait",
                "style": "fantasy art",
                "original_prompt": "Raw prompt before enhancement",
                "service": "provider_name"
            }
        """
        # Build raw prompt from character metadata
        raw_prompt = self._build_portrait_prompt(character_info, custom_additions)

        logger.info(f"🎨 Generating portrait for {character_info.name}")
        logger.info(f"   Raw prompt: {raw_prompt[:100]}...")

        # Use existing ImageGenerator.generate() method
        # It automatically routes "portrait" type through run_without_tools()
        # which calls enhance_prompt() and then generate_image_tool()
        result = await self.image_generator.generate(
            prompt=raw_prompt,
            image_type="portrait",  # Routes to run_without_tools automatically (line 530)
            style="fantasy art"
        )

        if result.get("success"):
            logger.info(f"✅ Portrait generated successfully for {character_info.name}")
            logger.info(f"   Path: {result.get('local_path')}")
        else:
            logger.error(f"❌ Portrait generation failed for {character_info.name}: {result.get('error')}")

        return result

    def _build_portrait_prompt(
        self,
        character_info: CharacterInfo,
        custom_additions: Optional[str] = None
    ) -> str:
        """
        Build raw prompt from character visual metadata.

        This raw prompt will be enhanced by ImageGeneratorAgent.enhance_prompt()
        which already has portrait-specific enhancement logic (lines 362-378).

        The enhance_prompt method expects a description covering:
        - Name, descriptor, gender, race, age, class
        - Facial expression, facial features
        - Armor/attire, distinguishing features
        - Head position/angle

        Returns:
            Comma-separated description string
        """
        parts = []

        # Name
        if character_info.name:
            parts.append(character_info.name)

        # Descriptor (from facial expression or personality)
        if hasattr(character_info, 'facial_expression') and character_info.facial_expression:
            parts.append(character_info.facial_expression.lower())

        # Gender
        if hasattr(character_info, 'gender') and character_info.gender:
            parts.append(character_info.gender.lower())

        # Race
        if character_info.race:
            parts.append(character_info.race)

        # Age category
        if hasattr(character_info, 'age_category') and character_info.age_category:
            parts.append(character_info.age_category.lower())

        # Class
        if character_info.character_class:
            parts.append(character_info.character_class)

        # Facial expression (repeated for emphasis if important)
        if hasattr(character_info, 'facial_expression') and character_info.facial_expression:
            parts.append(f"{character_info.facial_expression.lower()} expression")

        # Facial features
        if hasattr(character_info, 'facial_features') and character_info.facial_features:
            parts.append(character_info.facial_features)

        # Attire/Armor
        if hasattr(character_info, 'attire') and character_info.attire:
            parts.append(f"wearing {character_info.attire}")

        # Distinguishing features
        if hasattr(character_info, 'distinguishing_feature') and character_info.distinguishing_feature:
            parts.append(character_info.distinguishing_feature)

        # Head position/pose (for portraits, this is head position)
        if hasattr(character_info, 'pose') and character_info.pose:
            parts.append(character_info.pose.lower())

        # Custom user additions
        if custom_additions:
            parts.append(custom_additions)

        # Join all parts into a comma-separated description
        # enhance_prompt() will refine this into an optimized prompt
        prompt = ", ".join(parts)

        return prompt
```

### 3. Character Storage Updates

Update [character_storage.py](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/character_storage.py) to handle portrait data:

- Ensure portrait fields are serialized/deserialized correctly
- Store portrait images in campaign-specific media directory: `{campaign_storage}/campaigns/{campaign_id}/media/portraits/`

### 4. Character Manager Extensions

Update [character_manager.py](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/character_manager.py):

```python
async def generate_character_portrait(
    self,
    character_id: str,
    custom_additions: Optional[str] = None
) -> Dict[str, Any]:
    """Generate portrait for a character."""

    character_info = self.get_character(character_id)
    if not character_info:
        return {"success": False, "error": "Character not found"}

    portrait_gen = CharacterPortraitGenerator()
    result = await portrait_gen.generate_portrait(
        character_info=character_info,
        session_id=self.campaign_id,
        custom_additions=custom_additions
    )

    if result.get("success"):
        # Update character with portrait info
        character_info.portrait_url = result.get("image_url")
        character_info.portrait_path = result.get("local_path")
        character_info.portrait_prompt = result.get("prompt")

        # Persist updated character
        self.update_character(character_id, character_info)
        self.persist_characters()

    return result
```

## Frontend Implementation

### 1. Character Creator Component Structure

```
components/
  CharacterCreator/
    CharacterCreator.jsx          # Main component
    BasicInfoSection.jsx           # Name, race, class, gender
    AdvancedVisualSection.jsx      # Expandable visual customization
    PortraitPreview.jsx            # Portrait display and generation controls
    VisualCustomizationForm.jsx    # Form fields for visual attributes
```

### 2. Character Creator UI Layout

```jsx
<CharacterCreator>
  <Row>
    <Column width="60%">
      <BasicInfoSection />
      <AdvancedVisualSection>
        <VisualCustomizationForm />
      </AdvancedVisualSection>
      <StatsSection />
      <BackstorySection />
    </Column>

    <Column width="40%">
      <PortraitPreview>
        {portrait ? (
          <img src={portrait.url} alt={character.name} />
        ) : (
          <PlaceholderImage />
        )}
        <Button onClick={generatePortrait}>
          {portrait ? "Regenerate" : "Generate Portrait"}
        </Button>
        <LoadingSpinner visible={generating} />
      </PortraitPreview>
    </Column>
  </Row>
</CharacterCreator>
```

### 3. API Integration

Create `services/characterService.js`:

```javascript
export const characterService = {
  async generatePortrait(characterId, customAdditions = "") {
    const response = await fetch(`/api/characters/${characterId}/portrait/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        character_id: characterId,
        regenerate: true,
        custom_prompt_additions: customAdditions
      })
    });
    return response.json();
  },

  async updateCharacterVisuals(characterId, visualData) {
    const response = await fetch(`/api/characters/${characterId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(visualData)
    });
    return response.json();
  },

  async getPortrait(characterId) {
    const response = await fetch(`/api/characters/${characterId}/portrait`);
    return response.json();
  }
};
```

### 4. Character Sheet Display

Update player view character sheet to display portrait:

```jsx
<CharacterSheet>
  <CharacterPortrait>
    {character.portrait_url && (
      <img
        src={character.portrait_url}
        alt={character.name}
        className="character-portrait"
      />
    )}
  </CharacterPortrait>
  <CharacterName>{character.name}</CharacterName>
  <CharacterDetails>
    <div>Class: {character.character_class}</div>
    <div>Race: {character.race}</div>
    <div>Level: {character.level}</div>
  </CharacterDetails>
</CharacterSheet>
```

### 5. DM View Integration

Display character portraits in DM interface alongside character roster:

```jsx
<DMCharacterRoster>
  {characters.map(char => (
    <CharacterCard key={char.id}>
      <CharacterPortraitThumb src={char.portrait_url} />
      <CharacterInfo>
        <h4>{char.name}</h4>
        <p>{char.character_class} {char.level}</p>
      </CharacterInfo>
    </CharacterCard>
  ))}
</DMCharacterRoster>
```

## Implementation Plan

### Phase 0: Architecture Refactoring (CRITICAL)
**Goal**: Eliminate data duplication by establishing CharacterProfile as single source of truth

1. **Enhance CharacterProfile model** - Add visual metadata, race, class, backstory
2. **Create EnrichedCharacter model** - Merged view for API responses
3. **Update CharacterManager** - Add profile loading, caching, enrichment methods
4. **Update API endpoints** - Return EnrichedCharacter instead of CharacterInfo
5. **Create migration script** - Copy visual metadata from CharacterInfo → CharacterProfile
6. **Run migration** - Migrate all existing campaigns and characters
7. **Refactor CharacterInfo** - Remove visual metadata fields (now in profile)
8. **Update portrait generation** - Save portraits to CharacterProfile not CharacterInfo
9. **Test refactoring** - Ensure all existing functionality works with new architecture

**Why First**: This refactoring must happen before extensive use of the portrait system to avoid data migration complexity later.

### Phase 1: Backend Foundation
1. **Create CharacterPortraitGenerator service** with prompt building logic
2. **Add portrait generation API endpoints**
3. **Update CharacterManager** with portrait generation methods (using profiles)
4. **Test API endpoints** with curl commands

### Phase 2: Pregenerated Character Updates
1. **Review existing pregenerated characters** in characters.json
2. **Auto-generate visual metadata** for each character using LLM
3. **Validate and refine** generated metadata for quality
4. **Create CharacterProfiles** for all pregenerated characters
5. **Update characters.json** with profile references

### Phase 3: Frontend Character Creator
1. **Create UI components** for character creator
2. **Implement basic info section** (race, gender, class)
3. **Build advanced visual customization** expandable section
4. **Add portrait preview component** with generation button
5. **Integrate API calls** for portrait generation
6. **Add loading states** and error handling

### Phase 4: Frontend Display Integration
1. **Update player view character sheet** to show portrait
2. **Update DM view** to display character portraits in roster
3. **Add portrait thumbnails** to character lists
4. **Ensure responsive design** for various screen sizes

### Phase 5: Testing & Refinement
1. **Test character creation flow** end-to-end
2. **Test portrait generation** with various attribute combinations
3. **Validate persistence** across campaign sessions
4. **Test multi-campaign character sharing** (same profile in different campaigns)
5. **Performance testing** for image generation
6. **UI/UX refinement** based on testing feedback

## Testing Strategy

### Backend Tests

#### Unit Tests
```python
# test/core/character/test_portrait_generator.py

async def test_portrait_prompt_building():
    """Test that portrait prompts are built correctly from character data."""
    character = CharacterInfo(
        character_id="test_123",
        name="Garrick",
        race="Human",
        gender="Male",
        character_class="Fighter",
        age_category="Adult",
        facial_expression="Determined",
        attire="steel breastplate",
        primary_weapon="longsword"
    )

    generator = CharacterPortraitGenerator()
    prompt = generator._build_portrait_prompt(character)

    assert "Garrick" in prompt
    assert "Human" in prompt
    assert "Fighter" in prompt
    assert "steel breastplate" in prompt

async def test_portrait_generation():
    """Test full portrait generation pipeline."""
    # Create test character
    # Generate portrait
    # Verify image was created
    # Verify character was updated with portrait data
```

#### Integration Tests
```python
async def test_character_portrait_api():
    """Test portrait generation API endpoint."""
    # Create character
    # Call /api/characters/{id}/portrait/generate
    # Verify response has portrait URL
    # Verify file exists at path
    # Verify character record updated
```

### API Testing with curl

```bash
# Test character creation with visual metadata
curl -X POST http://localhost:8000/api/characters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Character",
    "race": "Human",
    "gender": "Male",
    "character_class": "Fighter",
    "age_category": "Adult",
    "facial_expression": "Confident",
    "attire": "plate armor",
    "campaign_id": "campaign_1"
  }'

# Test portrait generation
curl -X POST http://localhost:8000/api/characters/char_123/portrait/generate \
  -H "Content-Type: application/json" \
  -d '{
    "character_id": "char_123",
    "regenerate": false
  }'

# Test portrait retrieval
curl http://localhost:8000/api/characters/char_123/portrait

# Test visual metadata update
curl -X PATCH http://localhost:8000/api/characters/char_123 \
  -H "Content-Type: application/json" \
  -d '{
    "facial_expression": "Stern",
    "attire": "Updated armor description"
  }'
```

### Frontend Testing
User should test:
- Character creation flow from start to finish
- Portrait generation with different attribute combinations
- Portrait regeneration after editing attributes
- Portrait display in player view
- Portrait display in DM view
- Loading states during generation
- Error handling for failed generations

## Technical Considerations

### Image Storage
- **Implementation**: Uses `ImageArtifactStore` (`backend/src/core/image/image_artifact_store.py`)
- **GCS Storage**: Portraits persist to Google Cloud Storage for production durability
  - Production path: `media/images/campaign_XX/portraits/portrait.png` (no hostname prefix)
  - Development path: `media/images/{hostname}/campaign_XX/portraits/portrait.png` (hostname prefix)
- **Local Cache**: Ephemeral storage at `/tmp/gaia-images/{session_id}/{filename}`
- **URL Format**: `/api/media/images/{session_id}/{filename}`
- **Authentication**: Endpoint requires session ownership verification
- **Cleanup**: Automatic local file removal after GCS upload to save ephemeral storage

**Environment Configuration:**
Proper environment variables are critical for correct image storage:
- **Production/Staging**: Must set `ENV=prod`, `ENVIRONMENT_NAME=prod`, or `ENVIRONMENT=production`
- **Development**: Set `ENVIRONMENT=development` to enable hostname-prefixed paths
- **Configuration Files**: `config/cloudrun.prod.env`, `config/cloudrun.stg.env`

The system defaults to production behavior (no hostname prefix) if environment variables are missing or unrecognized.

**Backward Compatibility:**
The image store includes fallback logic to handle images stored with incorrect paths:
1. Primary path: `media/images/campaign_XX/portraits/image.png`
2. Legacy path: `campaign_XX/media/images/image.png`
3. Hostname-prefixed path: `media/images/localhost/campaign_XX/portraits/image.png` (migration fallback)

This ensures existing portraits remain accessible after environment detection improvements.

### Performance
- **Generation Time**: Portrait generation may take 5-30 seconds
  - Implement proper loading states in UI
  - Consider timeout handling (60 seconds max)
- **Caching**: Store generated portraits to avoid regeneration
  - Only regenerate on explicit user request or metadata change
- **Concurrent Requests**: Handle multiple portrait generations gracefully

### Prompt Engineering
- **Leverage enhance_prompt**: Use the existing [enhance_prompt](/mnt/c/Users/haroon/Gaia-new/backend/src/game/dnd_agents/image_generator.py:331) method for optimal results
- **Portrait-specific guidelines**: The enhance_prompt method already has portrait-specific logic (lines 362-378)
- **Consistent style**: Use "portrait" image_type for consistency with existing templates

### Error Handling
- **Missing Fields**: Handle gracefully when optional visual fields are empty
- **Generation Failures**: Provide user-friendly error messages
- **Network Issues**: Implement retry logic for API calls
- **Invalid Data**: Validate visual metadata before generation

## Success Criteria

### Functional Requirements
- ✅ User can specify visual attributes during character creation
- ✅ User can generate a portrait from character metadata
- ✅ User can regenerate portrait after editing attributes
- ✅ Portrait persists with character data across sessions
- ✅ Portrait displays in player view character sheet
- ✅ Portrait displays in DM view character roster
- ✅ Pregenerated characters have complete visual metadata

### Quality Requirements
- ✅ Portrait generation completes within 60 seconds
- ✅ Generated portraits match character description accurately
- ✅ UI provides clear loading/error states
- ✅ All backend tests pass
- ✅ API endpoints validated with curl
- ✅ No regressions in existing character functionality

## Future Enhancements

### Phase 2 Features (Post-MVP)
1. **Portrait Gallery**: Allow users to browse and select from previously generated portraits
2. **Style Selection**: Let users choose art style (realistic, painterly, anime, etc.)
3. **Batch Generation**: Generate portraits for all party members at once
4. **Portrait History**: Keep history of generated portraits for comparison
5. **Custom Upload**: Allow users to upload their own portrait images
6. **AI-Assisted Refinement**: Use AI to suggest improvements to descriptions
7. **Portrait Variations**: Generate multiple variations and let user choose
8. **Animation**: Add subtle animations to portraits (blinking, breathing)

### Technical Improvements
1. **Thumbnail Generation**: Auto-generate smaller thumbnails for list views
2. **Image Optimization**: Compress portraits for faster loading
3. **CDN Integration**: Serve portraits from CDN for better performance
4. **Batch Processing**: Queue system for multiple portrait requests
5. **Background Generation**: Generate portraits in background without blocking UI

## References

### Existing Code
- [ImageGeneratorAgent](/mnt/c/Users/haroon/Gaia-new/backend/src/game/dnd_agents/image_generator.py) - Image generation service
- [CharacterInfo](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/models/character_info.py) - Character data model
- [CharacterStorage](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/character_storage.py) - Character persistence
- [CharacterManager](/mnt/c/Users/haroon/Gaia-new/backend/src/core/character/character_manager.py) - Character business logic
- [Pregenerated Characters](/mnt/c/Users/haroon/Gaia-new/campaign_storage/pregenerated/characters.json) - Character templates

### Image Generation Details
- **Portrait Template** (line 28): Specialized prompt template for portraits with cinematic lighting
- **enhance_prompt Method** (line 331-413): AI-powered prompt enhancement with portrait-specific logic
- **Portrait Enhancement** (lines 362-378): Detailed focus areas for portrait generation including:
  - Name, descriptor, race, gender, age, class
  - Facial expression, facial features
  - Armor/attire, distinguishing features
  - Head position/angle

### API Patterns
- [CampaignService](/mnt/c/Users/haroon/Gaia-new/backend/src/api/campaign_service.py) - Reference for API service patterns
- Character creation pattern (lines 449-457): Shows how CharacterManager integrates with campaign flow

---

## Quick Reference: Implementation Checklist

### Phase 0: Architecture Refactoring Tasks
- [ ] Enhance CharacterProfile model with visual metadata
- [ ] Add race, class, backstory to CharacterProfile
- [ ] Create EnrichedCharacter model
- [ ] Add profile_id field to CharacterInfo
- [ ] Update CharacterManager with profile loading/caching
- [ ] Add get_enriched_character() method
- [ ] Update API endpoints to return EnrichedCharacter
- [ ] Create migration script for existing characters
- [ ] Run migration on all campaigns
- [ ] Remove visual metadata from CharacterInfo
- [ ] Test profile loading and enrichment
- [ ] Validate no data duplication

### Phase 1: Backend Foundation Tasks
- [ ] Create CharacterPortraitGenerator service
- [ ] Implement _build_portrait_prompt() using profile data
- [ ] Add portrait generation API endpoints
- [ ] Update CharacterManager portrait methods to use profiles
- [ ] Ensure portraits save to CharacterProfile
- [ ] Create portrait storage directory structure
- [ ] Write unit tests for portrait generation
- [ ] Write integration tests for API
- [ ] Test with curl commands

### Phase 2: Pregenerated Character Tasks
- [ ] Review all characters in characters.json
- [ ] Generate visual metadata for each character
- [ ] Validate metadata quality
- [ ] Create CharacterProfile for each character
- [ ] Update characters.json with profile references

### Phase 3: Frontend Character Creator Tasks
- [ ] Create CharacterCreator component structure
- [ ] Build BasicInfoSection component
- [ ] Build AdvancedVisualSection component
- [ ] Build PortraitPreview component
- [ ] Create characterService API client
- [ ] Integrate portrait generation
- [ ] Add loading/error states

### Phase 4: Frontend Display Tasks
- [ ] Update player view character sheet
- [ ] Update DM view character roster
- [ ] Add portrait thumbnails to character lists
- [ ] Ensure responsive design

### Phase 5: Testing Tasks
- [ ] Backend unit tests pass
- [ ] Backend integration tests pass
- [ ] API endpoints tested with curl
- [ ] Frontend character creation tested
- [ ] Portrait generation tested
- [ ] Portrait persistence tested (profiles not campaigns)
- [ ] Multi-campaign character sharing tested
- [ ] Portrait display tested (player & DM views)
- [ ] Error handling tested
- [ ] Performance validated
