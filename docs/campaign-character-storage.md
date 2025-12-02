# Character Persistence Architecture - Complete Explanation

**Last Updated**: October 13, 2025
**Author**: System Documentation
**Status**: Current Implementation

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Model Breakdown](#data-model-breakdown)
3. [Scenario Walkthrough](#scenario-walkthrough)
4. [Key Questions Answered](#key-questions-answered)
5. [Complete On-Disk Data Model](#complete-on-disk-data-model)
6. [Data Flow During Gameplay](#data-flow-during-gameplay)
7. [Memory Management](#memory-management)
8. [Summary](#summary)

---

## Architecture Overview

### Two-Layer Storage Model

Gaia uses a **dual-layer persistence model** that separates **global identity** from **campaign-specific state**.

```
┌─────────────────────────────────────────────────────────────┐
│                    GLOBAL LAYER                             │
│  Character Identity (Shared Across Campaigns)               │
│                                                             │
│  📁 character_profiles/                                     │
│     ├─ pc:kara_stormwind.json ← CharacterProfile          │
│     ├─ pc:theron_gearwright.json                           │
│     └─ pc:aria_silverleaf.json                             │
│                                                             │
│  Contains: Voice, portraits, visual metadata, backstory    │
└─────────────────────────────────────────────────────────────┘
                            ↕
                     (references)
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                   CAMPAIGN LAYER                            │
│  Character State (Campaign-Specific)                        │
│                                                             │
│  📁 campaign_12345/                                         │
│     ├─ campaign_data.json ← CampaignData                   │
│     │    character_ids: ["pc:kara_stormwind", ...]         │
│     │                                                       │
│     └─ characters/                                          │
│        ├─ pc:kara_stormwind.json ← CharacterInfo          │
│        └─ pc:theron_gearwright.json                        │
│                                                             │
│  Contains: HP, inventory, abilities, location, XP, status   │
└─────────────────────────────────────────────────────────────┘
```

### Why Two Layers?

**Problem Solved**: How do you let players reuse characters across multiple campaigns while maintaining separate game state?

**Solution**:
- **Global Layer**: Character identity that doesn't change (appearance, voice, backstory)
- **Campaign Layer**: Character state that changes during play (HP, inventory, location)

**Benefits**:
- Reuse characters across campaigns without duplicating portraits/voices
- Same character can be level 3 in one campaign, level 10 in another
- Portrait generation happens once, shared everywhere
- Consistent character identity across all campaigns

---

## Data Model Breakdown

### 1. CharacterProfile (Global Identity)

**Location**: `{CAMPAIGN_STORAGE_PATH}/character_profiles/{character_id}.json`

**Purpose**: Immutable character identity shared across all campaigns

**Schema**:
```python
@dataclass
class CharacterProfile:
    character_id: str
    name: str
    character_type: CharacterType  # PLAYER, NPC

    # Core identity
    race: str = "human"
    character_class: str = "adventurer"
    base_level: int = 1  # Default starting level

    # Voice assignment (persists across campaigns)
    voice_id: Optional[str] = None
    voice_settings: Dict[str, Any] = field(default_factory=dict)
    voice_archetype: Optional[VoiceArchetype] = None

    # Visual representation
    portrait_url: Optional[str] = None
    portrait_path: Optional[str] = None
    portrait_prompt: Optional[str] = None
    additional_images: List[str] = field(default_factory=list)

    # Visual metadata for portrait generation
    gender: Optional[str] = None
    age_category: Optional[str] = None
    build: Optional[str] = None
    height_description: Optional[str] = None
    facial_expression: Optional[str] = None
    facial_features: Optional[str] = None
    attire: Optional[str] = None
    primary_weapon: Optional[str] = None
    distinguishing_feature: Optional[str] = None
    background_setting: Optional[str] = None
    pose: Optional[str] = None

    # Descriptions
    backstory: str = ""
    description: str = ""
    appearance: str = ""
    visual_description: str = ""

    # Metadata
    first_created: datetime = field(default_factory=datetime.now)
    total_interactions: int = 0  # Across ALL campaigns
```

**Example JSON**:
```json
{
  "character_id": "pc:kara_stormwind",
  "name": "Kara Stormwind",
  "character_type": "player",

  "race": "Human",
  "character_class": "Fighter",
  "base_level": 3,

  "voice_id": "caleb",
  "voice_archetype": "hero",
  "voice_settings": {},

  "gender": "Female",
  "age_category": "Adult",
  "build": "Athletic",
  "facial_expression": "Confident",
  "facial_features": "scar across left eyebrow",
  "attire": "battle-worn plate armor",
  "primary_weapon": "longsword",
  "distinguishing_feature": "family crest tattoo on right shoulder",

  "portrait_url": "/api/images/runware_image_123.png",
  "portrait_path": "/home/gaia/images/runware_image_123.png",
  "portrait_prompt": "D&D character portrait: Female human fighter...",

  "backstory": "Former soldier seeking redemption after failing to protect her unit...",
  "description": "Tall, muscular human fighter with battle scars...",

  "first_created": "2025-10-01T12:00:00",
  "total_interactions": 15
}
```

**Key Point**: This is the "character sheet template" - their identity, appearance, and voice that doesn't change between campaigns.

---

### 2. CharacterInfo (Campaign State)

**Location**: `{CAMPAIGN_STORAGE_PATH}/{campaign_id}/characters/{character_id}.json`

**Purpose**: Mutable campaign-specific state (what changes during gameplay)

**Schema**:
```python
@dataclass
class CharacterInfo:
    character_id: str
    name: str
    character_class: str
    level: int
    race: str
    alignment: str = "neutral good"

    # Profile reference (links to global identity)
    profile_id: Optional[str] = None

    # Combat stats (change during gameplay)
    hit_points_current: int = 10
    hit_points_max: int = 10
    armor_class: int = 10
    status: CharacterStatus = CharacterStatus.HEALTHY
    status_effects: List[str] = field(default_factory=list)

    # Ability scores (can change via items/magic)
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    # Campaign-specific collections
    inventory: Dict[str, ItemInfo] = field(default_factory=dict)
    abilities: Dict[str, AbilityInfo] = field(default_factory=dict)
    dialog_history: List[str] = field(default_factory=list)
    quests: List[str] = field(default_factory=list)

    # Campaign progress
    location: Optional[str] = None
    personality_traits: List[str] = field(default_factory=list)
    bonds: List[str] = field(default_factory=list)
    flaws: List[str] = field(default_factory=list)

    # Visual data (copied from profile for convenience)
    gender: Optional[str] = None
    age_category: Optional[str] = None
    build: Optional[str] = None
    facial_expression: Optional[str] = None
    # ... other visual fields

    # Copied from profile
    backstory: str = ""
    description: str = ""
    appearance: str = ""
    visual_description: str = ""
    voice_id: Optional[str] = None
    voice_settings: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    character_type: str = "player"
    first_appearance: datetime = field(default_factory=datetime.now)
    last_interaction: datetime = field(default_factory=datetime.now)
    interaction_count: int = 0  # In THIS campaign only
```

**Example JSON**:
```json
{
  "character_id": "pc:kara_stormwind",
  "profile_id": "pc:kara_stormwind",
  "name": "Kara Stormwind",

  "race": "Human",
  "character_class": "Fighter",
  "level": 5,
  "alignment": "lawful good",

  "hit_points_current": 42,
  "hit_points_max": 52,
  "armor_class": 18,
  "status": "injured",
  "status_effects": ["blessed", "shield of faith"],

  "strength": 16,
  "dexterity": 12,
  "constitution": 14,
  "intelligence": 10,
  "wisdom": 13,
  "charisma": 8,

  "inventory": {
    "longsword": {
      "name": "Longsword +1",
      "item_type": "weapon",
      "description": "A finely crafted longsword..."
    },
    "health_potion": {
      "name": "Potion of Healing",
      "quantity": 3
    }
  },

  "abilities": {
    "second_wind": {
      "name": "Second Wind",
      "description": "Regain hit points...",
      "uses_left": 1,
      "uses_max": 1
    }
  },

  "location": "Tavern of the Drunken Dragon",
  "quests": ["find_the_lost_sword", "rescue_the_merchant"],
  "dialog_history": ["I accept your quest!", "Where is the merchant?"],

  "backstory": "Former soldier seeking redemption...",
  "voice_id": "caleb",

  "character_type": "player",
  "interaction_count": 8,
  "last_interaction": "2025-10-13T10:30:00"
}
```

**Key Point**: This is the "save game state" - HP, inventory, location, what happened in THIS campaign. Level can differ from `base_level` in profile!

---

### 3. CampaignData (Campaign Root)

**Location**: `{CAMPAIGN_STORAGE_PATH}/{campaign_id}/campaign_data.json`

**Purpose**: Campaign metadata and references to characters

**Schema**:
```python
@dataclass
class CampaignData:
    campaign_id: str
    title: str = "Untitled Campaign"
    description: str = ""
    game_style: GameStyle = GameStyle.BALANCED
    game_theme: Optional[GameTheme] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_played: datetime = field(default_factory=datetime.now)

    # CHARACTER REFERENCES (not full data!)
    character_ids: List[str] = field(default_factory=list)

    # Campaign content
    npcs: Dict[str, NPCInfo] = field(default_factory=dict)
    environments: Dict[str, EnvironmentInfo] = field(default_factory=dict)
    scenes: Dict[str, SceneInfo] = field(default_factory=dict)
    scene_order: List[str] = field(default_factory=list)
    narratives: List[NarrativeInfo] = field(default_factory=list)
    quests: Dict[str, QuestInfo] = field(default_factory=dict)

    # Current state
    current_scene_id: Optional[str] = None
    current_location_id: Optional[str] = None
    active_quest_ids: List[str] = field(default_factory=list)

    # Session tracking
    total_sessions: int = 0
    total_playtime_hours: float = 0.0

    # Additional metadata
    tags: Dict[str, str] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
```

**Example JSON**:
```json
{
  "campaign_id": "campaign_12345",
  "title": "The Lost Kingdom",
  "description": "A quest to find the ancient sword of kings...",
  "game_style": "balanced",
  "game_theme": "high_fantasy",

  "character_ids": [
    "pc:kara_stormwind",
    "pc:theron_gearwright",
    "pc:aria_silverleaf"
  ],

  "npcs": {
    "merchant_bob": {
      "npc_id": "merchant_bob",
      "name": "Bob the Merchant",
      "role": "merchant",
      "description": "A jolly merchant with a wide smile..."
    }
  },

  "environments": {
    "tavern": {
      "location_id": "tavern",
      "name": "The Drunken Dragon",
      "description": "A cozy tavern filled with adventurers..."
    }
  },

  "quests": {
    "find_sword": {
      "quest_id": "find_sword",
      "title": "The Lost Sword",
      "status": "active",
      "description": "Find the legendary sword..."
    }
  },

  "current_scene_id": "scene_003",
  "current_location_id": "tavern",
  "active_quest_ids": ["find_sword"],

  "total_sessions": 5,
  "total_playtime_hours": 12.5,
  "created_at": "2025-10-01T12:00:00",
  "last_played": "2025-10-13T10:30:00"
}
```

**Key Point**: Campaign data only stores **references** to characters (IDs), not the full character data. This keeps campaigns lightweight.

---

## Scenario Walkthrough

### Complete Flow: Load Preset → Edit → Start Campaign

#### **Step 1: User Creates Campaign**

**Frontend Request**:
```http
POST /api/campaigns/new
Content-Type: application/json

{
  "title": "The Lost Kingdom",
  "description": "Epic quest to find the ancient sword...",
  "character_slots": []
}
```

**What Happens**:
1. `CampaignService.create_campaign()` called
2. `CampaignData` object created with unique ID: `"campaign_12345"`
3. Campaign directory created: `campaign_12345/`
4. Empty campaign saved: `campaign_12345/campaign_data.json`

**On Disk**:
```
campaign_12345/
  ├─ campaign_data.json
  │    {
  │      "campaign_id": "campaign_12345",
  │      "title": "The Lost Kingdom",
  │      "character_ids": []  ← Empty!
  │    }
  └─ characters/ (empty directory)
```

**In Memory**: Campaign state initialized, no characters yet.

---

#### **Step 2: User Loads Preset Character**

**Frontend Request**:
```http
GET /api/characters/pregenerated
```

**Response**:
```json
[
  {
    "name": "Kara Stormwind",
    "character_class": "Fighter",
    "race": "Human",
    "level": 3,
    "gender": "Female",
    "facial_expression": "Confident",
    "build": "Athletic",
    "backstory": "Former soldier seeking redemption..."
  },
  {
    "name": "Theron Gearwright",
    "character_class": "Artificer",
    "race": "Rock Gnome",
    "level": 3,
    "gender": "Male",
    "facial_expression": "Joyful",
    "backstory": "Brilliant inventor with a mechanical squirrel..."
  }
]
```

**What Happens**:
1. Backend loads `backend/pregenerated/characters.json`
2. Returns array of preset character data
3. Frontend displays in dropdown: "Kara Stormwind (Human Fighter)"

**Important**:
- **NO SAVE YET** - just JSON in memory on frontend
- User sees character in dropdown selector
- Presets remain unchanged on disk

**On Disk**: No changes yet.

---

#### **Step 3: User Edits Character**

**User Actions**:
1. Selects "Kara Stormwind" from dropdown
2. **Edits**:
   - Name: "Kara Stormwind" → "Kara Smith"
   - Facial Expression: "Confident" → "Determined"
   - Attire: (adds custom) "Silver-trimmed plate armor"
   - Build: "Athletic" → "Muscular"
3. Clicks "🎨 Generate Portrait" (optional)

**Frontend State**:
```javascript
characterSlots[0] = {
  name: "Kara Smith",  // Edited!
  character_class: "Fighter",
  race: "Human",
  level: 3,
  gender: "Female",
  facial_expression: "Determined",  // Edited!
  build: "Muscular",  // Edited!
  attire: "Silver-trimmed plate armor",  // Added!
  backstory: "Former soldier seeking redemption...",
  portrait_url: null  // Not generated yet
}
```

**If Portrait Generated**:
```http
POST /api/characters/temp_slot_0/portrait/generate
Content-Type: application/json

{
  "character_id": "temp_slot_0",
  "campaign_id": "campaign_12345",
  "character_data": { /* character slot data */ }
}
```

**What Happens**:
1. Portrait generator creates image using visual metadata
2. Image saved: `images/runware_image_456.png`
3. Returns portrait URL
4. Frontend updates: `characterSlots[0].portrait_url = "/api/images/runware_image_456.png"`

**On Disk** (if portrait generated):
```
images/
  └─ runware_image_456.png  ← Portrait saved!

campaign_12345/
  └─ (no character data saved yet)
```

**Key Point**: Character edits only in frontend memory. Portrait image saved, but no profile created yet.

---

#### **Step 4: User Clicks "Start Campaign"**

**Frontend Request**:
```http
POST /api/campaigns/12345/start
Content-Type: application/json

{
  "character_slots": [
    {
      "name": "Kara Smith",
      "character_class": "Fighter",
      "race": "Human",
      "level": 3,
      "gender": "Female",
      "age_category": "Adult",
      "build": "Muscular",
      "facial_expression": "Determined",
      "attire": "Silver-trimmed plate armor",
      "backstory": "Former soldier seeking redemption...",
      "portrait_url": "/api/images/runware_image_456.png"
    }
  ]
}
```

**Backend Processing**:

```python
# 1. CharacterManager initialized for campaign
char_manager = CharacterManager(campaign_id="campaign_12345")

# 2. Create character from slot data
character_info = char_manager.create_character_from_simple(character_slots[0])

# Inside create_character_from_simple():
#   a. CharacterTranslator.simple_to_character_info()
#      → Creates CharacterInfo with ALL visual metadata
#      → Generates character_id: "pc:kara_smith"
#      → Calculates HP, AC, inventory, abilities
#
#   b. CharacterStorage.save_character()
#      → Saves CharacterInfo to characters/pc:kara_smith.json
#
#   c. CharacterManager.ensure_profile_exists()
#      → Creates/updates CharacterProfile
#      → Copies visual metadata from CharacterInfo
#      → Saves profile to character_profiles/pc:kara_smith.json
#
#   d. VoicePool.assign_voice()
#      → Auto-assigns voice based on archetype
#      → Updates profile with voice_id
```

**Critical Moment - Two Files Created**:

**File 1 - CharacterProfile (GLOBAL)**:
```json
// Location: character_profiles/pc:kara_smith.json
{
  "character_id": "pc:kara_smith",
  "name": "Kara Smith",
  "character_type": "player",

  "race": "Human",
  "character_class": "Fighter",
  "base_level": 3,

  "voice_id": "caleb",
  "voice_archetype": "hero",
  "voice_settings": {},

  "gender": "Female",
  "age_category": "Adult",
  "build": "Muscular",
  "facial_expression": "Determined",
  "attire": "Silver-trimmed plate armor",

  "portrait_url": "/api/images/runware_image_456.png",
  "portrait_path": "/home/gaia/images/runware_image_456.png",
  "portrait_prompt": "D&D character portrait: Female human fighter, determined expression...",

  "backstory": "Former soldier seeking redemption...",
  "description": "",
  "appearance": "",

  "first_created": "2025-10-13T11:00:00",
  "total_interactions": 0
}
```

**File 2 - CharacterInfo (CAMPAIGN-SPECIFIC)**:
```json
// Location: campaign_12345/characters/pc:kara_smith.json
{
  "character_id": "pc:kara_smith",
  "profile_id": "pc:kara_smith",
  "name": "Kara Smith",

  "race": "Human",
  "character_class": "Fighter",
  "level": 3,
  "alignment": "neutral good",

  "hit_points_current": 26,
  "hit_points_max": 26,
  "armor_class": 16,
  "status": "healthy",
  "status_effects": [],

  "strength": 16,
  "dexterity": 12,
  "constitution": 14,
  "intelligence": 10,
  "wisdom": 13,
  "charisma": 8,

  "inventory": {
    "longsword": {
      "name": "Longsword",
      "item_type": "weapon",
      "equipped": true
    },
    "plate_armor": {
      "name": "Plate Armor",
      "item_type": "armor",
      "equipped": true
    }
  },

  "abilities": {
    "second_wind": {
      "name": "Second Wind",
      "uses_left": 1,
      "uses_max": 1
    }
  },

  "location": null,
  "quests": [],
  "dialog_history": [],

  "backstory": "Former soldier seeking redemption...",
  "voice_id": "caleb",

  "character_type": "player",
  "first_appearance": "2025-10-13T11:00:00",
  "last_interaction": "2025-10-13T11:00:00",
  "interaction_count": 0
}
```

**File 3 - CampaignData Updated**:
```json
// Location: campaign_12345/campaign_data.json
{
  "campaign_id": "campaign_12345",
  "title": "The Lost Kingdom",
  "description": "Epic quest...",

  "character_ids": [
    "pc:kara_smith"  ← Character linked!
  ],

  "npcs": {},
  "environments": {},
  "quests": {},

  "created_at": "2025-10-13T10:00:00",
  "last_played": "2025-10-13T11:00:00"
}
```

**Final On-Disk State**:
```
{CAMPAIGN_STORAGE_PATH}/
├─ character_profiles/  (GLOBAL)
│  ├─ prof_kara_stormwind.json  ← Original preset (unchanged)
│  └─ pc:kara_smith.json  ← NEW: Edited character profile
│
├─ images/  (GLOBAL)
│  └─ runware_image_456.png  ← Portrait image
│
└─ campaign_12345/  (CAMPAIGN)
   ├─ campaign_data.json
   │    { "character_ids": ["pc:kara_smith"] }
   │
   └─ characters/
      └─ pc:kara_smith.json  ← Campaign state
```

**Key Insights**:
1. ✅ Original preset `prof_kara_stormwind.json` remains unchanged
2. ✅ New profile `pc:kara_smith.json` created (because name changed)
3. ✅ Portrait image saved globally (can be reused)
4. ✅ Campaign state separate from global identity
5. ✅ Campaign only stores character ID reference

---

## Key Questions Answered

### Q1: Is there a global version of the character saved somewhere?

**YES!** `CharacterProfile` is saved globally at:
```
{CAMPAIGN_STORAGE_PATH}/character_profiles/{character_id}.json
```

**Why Global?**
1. **Reusability**: Use same character in multiple campaigns
2. **Efficiency**: Portrait/voice generated once, shared everywhere
3. **Consistency**: Character identity (appearance, backstory) stays the same
4. **Performance**: Don't regenerate portraits for each campaign

**Example**: You can use "Kara Smith" in:
- Campaign A (level 3, 26/26 HP, in tavern)
- Campaign B (level 10, 85/85 HP, in castle)
- Same portrait, voice, backstory in both!

---

### Q2: What if I edit a preset character?

**Two scenarios**:

#### **Scenario A: You Change the Name**

Before:
```json
// Preset: prof_kara_stormwind.json
{ "name": "Kara Stormwind", "class": "Fighter" }
```

After editing to "Kara Smith":
```
character_profiles/
  ├─ prof_kara_stormwind.json  ← Unchanged (original preset)
  └─ pc:kara_smith.json  ← NEW profile (your edited version)
```

**Result**: New profile created, preset preserved.

#### **Scenario B: You Keep the Name**

Before:
```json
// Preset: prof_kara_stormwind.json
{ "name": "Kara Stormwind", "facial_expression": "Confident" }
```

After editing expression to "Determined":
```
character_profiles/
  └─ prof_kara_stormwind.json  ← UPDATED!
      { "name": "Kara Stormwind", "facial_expression": "Determined" }
```

**Result**: Existing profile updated.

⚠️ **Warning**: If you edit a preset (same name), it affects **all future uses** of that preset!

**Current Behavior**: `ensure_profile_exists()` updates existing profiles with new data from CharacterInfo.

---

### Q3: When I load a campaign, is the entire campaign reloaded?

**NO!** Gaia uses **lazy loading** and **caching**:

#### **Campaign Load Process**:

```python
# Step 1: Load campaign metadata (lightweight)
campaign_data = load_campaign_data("campaign_12345")
# Loads: campaign_12345/campaign_data.json (~5KB)
# Contains: character_ids, current_scene, quest refs

# Step 2: Load campaign characters (moderate)
char_manager = CharacterManager("campaign_12345")
char_manager._load_characters()
# Loads: campaign_12345/characters/*.json (~3KB each)
# Contains: CharacterInfo (HP, inventory, location)

# Step 3: Profiles loaded on-demand (lazy)
profile = char_manager._get_profile("pc:kara_smith")
# Loads: character_profiles/pc:kara_smith.json (~2KB)
# Cached in: char_manager._profile_cache
```

#### **Memory Structure**:

```python
class CharacterManager:
    def __init__(self, campaign_id: str):
        self.campaign_id = "campaign_12345"

        # ALWAYS LOADED (on campaign start)
        self.characters: Dict[str, CharacterInfo] = {
            "pc:kara_smith": CharacterInfo(...),
            "pc:theron_gearwright": CharacterInfo(...)
        }

        # LAZY LOADED (on first access)
        self._profile_cache: Dict[str, CharacterProfile] = {}
```

#### **Read Operations**:

```python
# Get character (from memory - fast!)
character = char_manager.get_character("pc:kara_smith")
# → Returns from self.characters (already loaded)
# → No disk I/O

# Get enriched character (lazy loads profile)
enriched = char_manager.get_enriched_character("pc:kara_smith")
# → Loads CharacterInfo from memory
# → Loads CharacterProfile from cache (or disk if not cached)
# → Merges into EnrichedCharacter for API response
```

**Performance**:
- ✅ Campaign data: ~5KB (loaded once)
- ✅ Character state: ~3KB per character (loaded once)
- ✅ Character profiles: ~2KB each (lazy-loaded, cached)
- ✅ 4-character campaign: ~20KB total in memory
- ✅ Profile cache cleared after session ends

---

### Q4: As campaign progresses, are complete character details duplicated?

**Answer**: Intentional **partial duplication** for performance and flexibility.

#### **Field-by-Field Breakdown**:

| Field | CharacterProfile | CharacterInfo | Why Both? |
|-------|------------------|---------------|-----------|
| `name` | ✅ Source | ✅ Copy | Profile is source of truth, copied for convenience |
| `race` | ✅ Source | ✅ Copy | Copied for convenience (rarely changes) |
| `character_class` | ✅ Source | ✅ Copy | Copied for convenience |
| `level` | `base_level: 3` | `level: 5` | **Can diverge!** Character levels up in campaign |
| `backstory` | ✅ Source | ✅ Copy | Copied for convenience (read-only in gameplay) |
| `portrait_url` | ✅ Source | ❌ Never | **Never duplicated** - always loaded from profile |
| `portrait_path` | ✅ Source | ❌ Never | Always from profile |
| `voice_id` | ✅ Source | ✅ Copy | Copied for convenience |
| `hit_points` | ❌ Never | ✅ Only here | Campaign state only |
| `inventory` | ❌ Never | ✅ Only here | Campaign state only |
| `location` | ❌ Never | ✅ Only here | Campaign state only |
| `status_effects` | ❌ Never | ✅ Only here | Campaign state only |
| `visual_metadata` | ✅ Source | ✅ Copy | Copied for portrait regeneration |

#### **Why Duplicate Some Fields?**

**1. Performance**:
```python
# Without duplication (slow):
if character.character_class == "Fighter":  # Need to load profile!
    profile = load_profile(character.profile_id)
    if profile.character_class == "Fighter":
        # Do something

# With duplication (fast):
if character.character_class == "Fighter":  # Already in CharacterInfo!
    # Do something
```

**2. Flexibility**:
```python
# Character can level up in campaign without affecting profile
character_info.level = 10  # In this campaign
profile.base_level = 3  # Starting level (unchanged)

# Next campaign can start at base_level again
new_campaign_character.level = 3  # Fresh start
```

**3. Simplicity**:
```python
# CharacterInfo has everything needed for gameplay
print(f"{character.name} (Level {character.level} {character.character_class})")
print(f"HP: {character.hit_points_current}/{character.hit_points_max}")
print(f"Location: {character.location}")
# No need to load profile for common operations
```

#### **Update Strategy**:

| Update Type | Updates Profile | Updates CharacterInfo | Example |
|-------------|-----------------|----------------------|---------|
| Portrait generated | ✅ | ❌ | `profile.portrait_url = "..."` |
| Visual metadata edited | ✅ | ❌ | `profile.facial_expression = "Angry"` |
| Character takes damage | ❌ | ✅ | `character.hit_points_current -= 8` |
| Character levels up | ❌ | ✅ | `character.level += 1` |
| Character gains item | ❌ | ✅ | `character.inventory["sword"] = Item(...)` |
| Voice assigned | ✅ | ✅ (copy) | Profile is source, copied to CharacterInfo |
| Name changed | ✅ | ✅ | Both updated to maintain consistency |

**Key Insight**: Portrait/voice/visual data is **never duplicated** - always loaded from profile when needed.

---

### Q5: What happens if I use the same character in multiple campaigns?

**Example**: "Kara Smith" in two campaigns

**On Disk**:
```
character_profiles/
  └─ pc:kara_smith.json  ← ONE global profile

campaign_11111/
  ├─ campaign_data.json
  │    { "character_ids": ["pc:kara_smith"] }
  └─ characters/
     └─ pc:kara_smith.json  ← Campaign A state (level 3, 15 HP)

campaign_22222/
  ├─ campaign_data.json
  │    { "character_ids": ["pc:kara_smith"] }
  └─ characters/
     └─ pc:kara_smith.json  ← Campaign B state (level 10, 85 HP)
```

**Key Points**:
1. ✅ **One profile**, shared between campaigns
2. ✅ **Two CharacterInfo files**, different campaign states
3. ✅ **Same portrait/voice** in both campaigns
4. ✅ **Different HP/inventory/location** in each campaign

**Behavior**:
```python
# Campaign A
kara_a = char_manager_a.get_enriched_character("pc:kara_smith")
# → CharacterInfo from campaign_11111/characters/
# → CharacterProfile from character_profiles/
# → level: 3, HP: 15/26, portrait_url: same

# Campaign B
kara_b = char_manager_b.get_enriched_character("pc:kara_smith")
# → CharacterInfo from campaign_22222/characters/
# → CharacterProfile from character_profiles/ (same!)
# → level: 10, HP: 85/105, portrait_url: same
```

---

### Q6: Why do I see multiple character files with similar names? What's the difference between `prof_`, `pc:`, and campaign character files?

**Answer**: The system maintains different file types for different purposes:

#### **Quick Reference**

| File Path | Prefix | Purpose | When Created | Why Different |
|-----------|--------|---------|--------------|---------------|
| `character_profiles/prof_pc:name.json` | `prof_` | **Preset Template** | When preset first loaded | Mostly nulls, preserves original |
| `character_profiles/pc:name.json` | `pc:` | **Global Identity** | After customization/portrait gen | Full details, shared across campaigns |
| `campaign_X/data/characters/pc:name.json` | `pc:` | **Campaign State** | When campaign starts | Gameplay data (HP, inventory) |
| `shared/character_profiles/pc:name.json` | `pc:` | **Legacy/Duplicate** | Auto-synced? | May be obsolete directory |

#### **Example: "Eldrin Oakwhisper"**

**File 1: `prof_pc:eldrin_oakwhisper.json`** (Original Preset)
```json
{
  "character_id": "prof_pc:eldrin_oakwhisper",
  "race": "human",              // Generic default
  "character_class": "adventurer",
  "portrait_url": null,         // NOT YET GENERATED
  "facial_expression": null,    // NOT YET CUSTOMIZED
  "voice_id": null              // NOT YET ASSIGNED
}
```
**Status**: Mostly nulls - this is the UNCUSTOMIZED template

**File 2: `pc:eldrin_oakwhisper.json`** (Customized Global Profile)
```json
{
  "character_id": "pc:eldrin_oakwhisper",
  "race": "Wood Elf",           // USER CUSTOMIZED
  "character_class": "Druid",   // USER CUSTOMIZED
  "portrait_url": "/api/images/runware_image_123.png",  // GENERATED
  "facial_expression": "Wise",  // USER SPECIFIED
  "voice_id": "caleb"          // ASSIGNED
}
```
**Status**: Fully populated - character identity ready for use

**File 3: `campaign_112/data/characters/pc:eldrin_oakwhisper.json`** (Campaign State)
```json
{
  "character_id": "pc:eldrin_oakwhisper",
  "level": 2,
  "hit_points_current": 13,     // GAMEPLAY STATE
  "hit_points_max": 13,
  "inventory": { "rations": {...} },
  "location": "Tavern",
  "portrait_url": "/api/images/runware_image_123.png"  // COPIED FROM PROFILE
}
```
**Status**: Campaign-specific gameplay data

#### **Why the Difference?**

1. **Preset (`prof_`) has nulls**: Uncustomized template, preserved for reuse
2. **Global profile (`pc:`) fully populated**: User customized + portrait generated
3. **Campaign state different focus**: Tracks gameplay (HP, inventory, location)

#### **Creation Timeline**
```
T0: User loads preset → prof_pc:eldrin_oakwhisper.json (nulls)
T1: User customizes character → (updates in memory)
T2: User generates portrait → pc:eldrin_oakwhisper.json (full data)
T3: User starts campaign → campaign_112/.../pc:eldrin_oakwhisper.json (state)
```

**See Also**: [Understanding Profile File Types and Naming](#understanding-profile-file-types-and-naming) for detailed breakdown.

---

## Complete On-Disk Data Model

### Directory Structure

```
{CAMPAIGN_STORAGE_PATH}/
│
├─ character_profiles/          # GLOBAL LAYER
│  │                            # Character identity (shared across campaigns)
│  │
│  │ ─── PRESET TEMPLATES (prof_ prefix) ───
│  ├─ prof_pc:kara_stormwind.json    # Preset original (nulls, uncustomized)
│  ├─ prof_pc:elara_moonwhisper.json # Preset original
│  ├─ prof_pc:gorak_the_brutal.json  # Preset original
│  │
│  │ ─── CUSTOMIZED CHARACTERS (pc: prefix) ───
│  ├─ pc:kara_smith.json             # User-created (customized from preset)
│  ├─ pc:theron_gearwright.json      # User-created (fully populated)
│  └─ pc:aria_silverleaf.json        # User-created (with portrait)
│
├─ images/                      # GLOBAL LAYER
│  │                            # Portrait images (referenced by profiles)
│  ├─ runware_image_456.png    # Kara's portrait (157 KB)
│  ├─ runware_image_789.png    # Theron's portrait
│  └─ flux_image_123.png       # Aria's portrait
│
├─ campaign_12345/              # CAMPAIGN LAYER (Campaign A)
│  │                            # Campaign-specific data
│  ├─ campaign_data.json       # Campaign metadata + character refs
│  │    {
│  │      "campaign_id": "campaign_12345",
│  │      "title": "The Lost Kingdom",
│  │      "character_ids": [
│  │        "pc:kara_smith",
│  │        "pc:theron_gearwright"
│  │      ]
│  │    }
│  │
│  ├─ characters/               # Character campaign state
│  │  ├─ pc:kara_smith.json
│  │  └─ pc:theron_gearwright.json
│  │
│  ├─ scenes/                   # Scene data
│  │  ├─ scene_001.json
│  │  └─ scene_002.json
│  │
│  └─ chat_history/             # Chat logs
│     └─ messages.json
│
├─ campaign_67890/              # CAMPAIGN LAYER (Campaign B)
│  │                            # Another campaign (reusing Kara!)
│  ├─ campaign_data.json
│  │    {
│  │      "campaign_id": "campaign_67890",
│  │      "title": "Dragon's Lair",
│  │      "character_ids": [
│  │        "pc:kara_smith",      ← Same character!
│  │        "pc:aria_silverleaf"
│  │      ]
│  │    }
│  │
│  └─ characters/
│     ├─ pc:kara_smith.json    ← Different state! (level 10 vs level 3)
│     └─ pc:aria_silverleaf.json
│
└─ pregenerated/                # PRESETS (read-only)
   └─ characters.json          # Preset character definitions
```

### File Size Reference

```
character_profiles/
  └─ pc:kara_smith.json         ~1-2 KB (identity)

campaign_12345/
  ├─ campaign_data.json         ~5-10 KB (metadata + refs)
  └─ characters/
     └─ pc:kara_smith.json      ~3-5 KB (campaign state)

images/
  └─ runware_image_456.png      ~150-200 KB (portrait)
```

### Cross-Campaign Sharing

**Key Insight**: Same character, different states

```
Character: "Kara Smith"
├─ ONE CharacterProfile
│  └─ character_profiles/pc:kara_smith.json
│     ├─ portrait_url: "/api/images/runware_image_456.png"
│     ├─ voice_id: "caleb"
│     └─ base_level: 3
│
├─ CharacterInfo in Campaign A
│  └─ campaign_12345/characters/pc:kara_smith.json
│     ├─ level: 3
│     ├─ hit_points: 15/26
│     └─ location: "Tavern"
│
└─ CharacterInfo in Campaign B
   └─ campaign_67890/characters/pc:kara_smith.json
      ├─ level: 10
      ├─ hit_points: 85/105
      └─ location: "Dragon's Lair"
```

---

### Understanding Profile File Types and Naming

When working with characters, you may encounter multiple profile files with similar names. Here's what each type means:

#### **File Type 1: Preset Templates (`prof_` prefix)**

**Location**: `character_profiles/prof_pc:character_name.json`
**Purpose**: Original preset template BEFORE customization
**Created**: When preset first loaded from `pregenerated/characters.json`
**Contains**: Minimal default values (often null or generic)

```json
// Example: prof_pc:eldrin_oakwhisper.json
{
  "character_id": "prof_pc:eldrin_oakwhisper",
  "name": "Eldrin Oakwhisper",
  "race": "human",              // Generic default
  "character_class": "adventurer",  // Generic default
  "base_level": 1,
  "portrait_url": null,         // Not yet generated
  "facial_expression": null,    // Not yet customized
  "gender": null,
  "voice_id": null,
  // ... most fields are null
}
```

**Why it exists**: Preserved to allow reusing the original preset in future campaigns without being affected by customizations made to other instances.

**Why mostly null**: This is the UNCUSTOMIZED template before the user adds visual details or generates portraits.

---

#### **File Type 2: Global Character Profiles (`pc:` prefix)**

**Location**: `character_profiles/pc:character_name.json`
**Purpose**: Customized global character identity (CharacterProfile)
**Created**: When user customizes preset and/or generates portrait
**Contains**: Full character identity (portrait, voice, visual metadata, backstory)

```json
// Example: pc:eldrin_oakwhisper.json
{
  "character_id": "pc:eldrin_oakwhisper",
  "name": "Eldrin Oakwhisper",
  "race": "Wood Elf",           // User customized
  "character_class": "Druid",   // User customized
  "base_level": 2,

  "voice_id": "caleb",          // Assigned voice
  "voice_archetype": "villain",

  "portrait_url": "/api/images/runware_image_123.png",  // Generated
  "portrait_path": "/home/gaia/images/runware_image_123.png",
  "portrait_prompt": "D&D character portrait: ...",

  "gender": "Male",
  "age_category": "Middle-aged",
  "facial_expression": "Wise",
  "facial_features": "weathered face with kind green eyes...",
  "attire": "robes woven from living vines...",
  "backstory": "Guardian of the Moonwell Grove...",
  // ... all fields populated
}
```

**Why it exists**: This is the CHARACTER IDENTITY shared across all campaigns. Generate portrait once, use everywhere.

**Why fully populated**: User has customized the character and generated its visual representation.

---

#### **File Type 3: Campaign Character State**

**Location**: `campaign_{id}/data/characters/pc:character_name.json`
**Purpose**: Campaign-specific gameplay state (CharacterInfo)
**Created**: When campaign starts with this character
**Contains**: Gameplay data (HP, inventory, location, abilities)

```json
// Example: campaign_112/data/characters/pc:eldrin_oakwhisper.json
{
  "character_id": "pc:eldrin_oakwhisper",
  "name": "Eldrin Oakwhisper",
  "level": 2,                   // Can differ from base_level

  "hit_points_current": 13,     // GAMEPLAY STATE
  "hit_points_max": 13,
  "armor_class": 10,
  "status": "healthy",

  "inventory": {                // Items acquired in THIS campaign
    "rations": { "quantity": 5 },
    "waterskin": { "quantity": 1 }
  },

  "abilities": {                // Abilities for THIS level
    "basic_attack": { ... }
  },

  "location": "Tavern",         // Current location in THIS campaign
  "quests": ["find_sword"],     // Active quests in THIS campaign

  // Visual data copied from profile for convenience
  "portrait_url": "/api/images/runware_image_123.png",
  "voice_id": "caleb",
  "backstory": "Guardian of the Moonwell Grove..."
}
```

**Why it exists**: Same character can have different state in different campaigns (different HP, level, inventory).

**Why different from profile**: Contains mutable campaign state, not immutable identity.

---

#### **File Type 4: Shared Profiles (Legacy)**

**Location**: `shared/character_profiles/pc:character_name.json`
**Purpose**: May be legacy sync location or backup
**Created**: Appears to be duplicated from global profiles
**Contains**: Duplicate of Type 2 (global profile)

```json
// Example: shared/character_profiles/pc:eldrin_oakwhisper.json
// Identical to character_profiles/pc:eldrin_oakwhisper.json
```

**Note**: This appears to be a legacy directory structure or sync mechanism. May warrant investigation for cleanup.

---

### Creation Timeline Example

Here's the complete lifecycle of a preset character becoming a campaign character:

```
Time: T0 (User loads preset "Eldrin Oakwhisper")
  ├─ File Created: character_profiles/prof_pc:eldrin_oakwhisper.json
  │  └─ Status: Empty template (nulls), race="human", class="adventurer"
  │  └─ Purpose: Preserve original preset

Time: T1 (User customizes character)
  └─ User changes:
     - Race: human → Wood Elf
     - Class: adventurer → Druid
     - Adds facial features, attire, backstory

Time: T2 (User generates portrait)
  ├─ File Created: character_profiles/pc:eldrin_oakwhisper.json
  │  └─ Status: Fully populated with visual metadata
  │  └─ portrait_url: "/api/images/runware_image_123.png"
  │  └─ voice_id: "caleb" (assigned)
  │
  └─ Image Created: images/runware_image_123.png

Time: T3 (User starts campaign)
  ├─ Campaign Created: campaign_112/
  │
  └─ File Created: campaign_112/data/characters/pc:eldrin_oakwhisper.json
     └─ Status: Campaign state initialized
     └─ HP: 13/13, Level: 2, Inventory: basic items
     └─ Links to global profile via portrait_url and voice_id
```

---

### File Naming Convention Summary

| Prefix | Meaning | Example | Purpose |
|--------|---------|---------|---------|
| `prof_` | **Preset Original** | `prof_pc:kara_stormwind.json` | Unmodified preset template |
| `pc:` | **Player Character** | `pc:kara_smith.json` | Customized character instance |
| None | **Campaign State** | `campaign_112/data/characters/pc:...` | Gameplay state |

**Key Rule**:
- `prof_` = Preserved preset (mostly nulls)
- `pc:` = Actual character (fully populated)
- Campaign path = Game state (HP, items, location)

---

### Why Some Files Have Null Values

**Preset files (`prof_`) have nulls because**:
1. They represent UNCUSTOMIZED templates
2. Portrait not yet generated
3. Voice not yet assigned
4. Visual metadata not yet filled in
5. Intentionally minimal to serve as clean starting point

**Global profiles (`pc:`) have full data because**:
1. User has customized the character
2. Portrait has been generated
3. Voice has been assigned
4. All visual metadata filled in during character creation
5. Ready to be used across multiple campaigns

**Campaign state files have different focus**:
1. Emphasize gameplay state (HP, inventory)
2. Copy some profile data for convenience (portrait, voice)
3. Track campaign-specific progress (location, quests)
4. Can have different level/HP than base profile

---

## Data Flow During Gameplay

### Scenario 1: Character Takes Damage

**User Action**: "I attack the goblin!"

**Flow**:
```
1. Player action received
   ↓
2. DM Agent processes: "Goblin counterattacks for 8 damage"
   ↓
3. CharacterManager.apply_damage("pc:kara_smith", 8)
   ↓
4. Update in-memory CharacterInfo:
   character.hit_points_current = 34  (was 42)
   character.last_interaction = now()
   ↓
5. Persist to disk:
   CharacterManager.persist_characters()
   ↓
6. ONLY CharacterInfo updated:
   campaign_12345/characters/pc:kara_smith.json
   { "hit_points_current": 34 }
   ↓
7. CharacterProfile NOT touched
   (damage is campaign-specific)
```

**Files Modified**:
- ✅ `campaign_12345/characters/pc:kara_smith.json` (HP updated)
- ❌ `character_profiles/pc:kara_smith.json` (unchanged)

---

### Scenario 2: User Regenerates Portrait

**User Action**: Clicks "🎨 Regenerate Portrait"

**Flow**:
```
1. Frontend: POST /api/characters/pc:kara_smith/portrait/generate
   ↓
2. CharacterManager.generate_character_portrait()
   ↓
3. Load CharacterProfile (for visual metadata)
   profile = self._get_profile("pc:kara_smith")
   ↓
4. CharacterPortraitGenerator.generate_portrait()
   - Uses profile.gender, profile.facial_expression, etc.
   - Sends to Runware/Gemini/Local SDXL
   ↓
5. Image generated:
   /home/gaia/images/runware_image_999.png (159 KB)
   ↓
6. Update profile:
   profile.portrait_url = "/api/images/runware_image_999.png"
   profile.portrait_path = "/home/gaia/images/runware_image_999.png"
   profile.portrait_prompt = "D&D character portrait: Female human..."
   ↓
7. Save profile:
   ProfileStorage.save_profile(profile)
   ↓
8. ONLY CharacterProfile updated:
   character_profiles/pc:kara_smith.json
   ↓
9. CharacterInfo NOT touched
   (portrait is global identity)
```

**Files Modified**:
- ✅ `character_profiles/pc:kara_smith.json` (portrait URLs updated)
- ✅ `images/runware_image_999.png` (new image created)
- ❌ `campaign_12345/characters/pc:kara_smith.json` (unchanged)

**Effect**: New portrait immediately available in **all campaigns** using Kara Smith!

---

### Scenario 3: Character Levels Up

**User Action**: "I gain enough XP to level up!"

**Flow**:
```
1. DM Agent: "You've reached level 4!"
   ↓
2. CharacterManager.level_up_character("pc:kara_smith")
   ↓
3. Update in-memory CharacterInfo:
   character.level = 4  (was 3)
   character.hit_points_max += 8  (HP increase)
   character.abilities["action_surge"] = Ability(...)  (new ability)
   ↓
4. Persist to disk:
   CharacterManager.persist_characters()
   ↓
5. ONLY CharacterInfo updated:
   campaign_12345/characters/pc:kara_smith.json
   { "level": 4, "hit_points_max": 34 }
   ↓
6. CharacterProfile NOT touched
   (level changes are campaign-specific)
   profile.base_level remains 3
```

**Files Modified**:
- ✅ `campaign_12345/characters/pc:kara_smith.json` (level, HP, abilities updated)
- ❌ `character_profiles/pc:kara_smith.json` (base_level unchanged)

**Key Point**: `profile.base_level` is the **starting level** for new campaigns. Campaign-specific `level` can diverge.

---

### Scenario 4: Visual Metadata Edited

**User Action**: Changes facial expression from "Confident" to "Angry"

**Flow**:
```
1. Frontend: PATCH /api/characters/pc:kara_smith
   { "facial_expression": "Angry" }
   ↓
2. CharacterManager.update_character_visuals()
   ↓
3. Load CharacterProfile:
   profile = self._get_profile("pc:kara_smith")
   ↓
4. Update visual metadata:
   profile.facial_expression = "Angry"
   ↓
5. Save profile:
   ProfileStorage.save_profile(profile)
   ↓
6. Invalidate cache:
   self._profile_cache.pop("pc:kara_smith")
   ↓
7. ONLY CharacterProfile updated:
   character_profiles/pc:kara_smith.json
   ↓
8. CharacterInfo NOT touched immediately
   (visual metadata in CharacterInfo is stale copy)
```

**Files Modified**:
- ✅ `character_profiles/pc:kara_smith.json` (facial_expression updated)
- ❌ `campaign_12345/characters/pc:kara_smith.json` (stale copy remains)

**Note**: CharacterInfo visual metadata is a **convenience copy**. Profile is the source of truth.

---

### Scenario 5: Loading Campaign on New Session

**User Action**: Clicks "Continue Campaign: The Lost Kingdom"

**Flow**:
```
1. Backend: Load campaign metadata
   campaign_data = CampaignData.from_json(
       "campaign_12345/campaign_data.json"
   )
   ↓
2. Extract character IDs:
   character_ids = ["pc:kara_smith", "pc:theron_gearwright"]
   ↓
3. Initialize CharacterManager:
   char_manager = CharacterManager("campaign_12345")
   ↓
4. Load character campaign state:
   char_manager._load_characters()
   ↓
   for char_id in character_ids:
       char_data = load_json(f"campaign_12345/characters/{char_id}.json")
       character_info = CharacterInfo.from_dict(char_data)
       char_manager.characters[char_id] = character_info
   ↓
5. Profiles NOT loaded yet (lazy loading)
   char_manager._profile_cache = {}  (empty)
   ↓
6. Campaign ready!
   - CharacterInfo in memory (HP, inventory, location)
   - CharacterProfile loaded on-demand when needed
```

**Memory After Load**:
```python
char_manager.characters = {
    "pc:kara_smith": CharacterInfo(
        level=4, hp=26/34, location="Tavern"
    ),
    "pc:theron_gearwright": CharacterInfo(
        level=3, hp=18/21, location="Tavern"
    )
}

char_manager._profile_cache = {}  # Empty - lazy loaded
```

**First Portrait Request**:
```python
# User clicks on character to view portrait
enriched = char_manager.get_enriched_character("pc:kara_smith")

# NOW profile is loaded:
profile = char_manager._get_profile("pc:kara_smith")
# → Loads from character_profiles/pc:kara_smith.json
# → Caches in _profile_cache

# Returns enriched data with portrait:
{
    "name": "Kara Smith",
    "level": 4,  # From CharacterInfo
    "hit_points_current": 26,  # From CharacterInfo
    "portrait_url": "/api/images/runware_image_456.png",  # From CharacterProfile
    "voice_id": "caleb"  # From CharacterProfile
}
```

---

## Memory Management

### What's Cached vs What's Loaded

```python
class CharacterManager:
    """Manages characters for a specific campaign."""

    def __init__(self, campaign_id: str):
        self.campaign_id = campaign_id

        # ALWAYS LOADED (eager loading on init)
        self.characters: Dict[str, CharacterInfo] = {}
        # Contains: Campaign state (HP, inventory, location)
        # Size: ~3-5 KB per character
        # Loaded from: campaign_{id}/characters/*.json

        # LAZY LOADED (on-demand, cached)
        self._profile_cache: Dict[str, CharacterProfile] = {}
        # Contains: Character identity (portrait, voice, visual metadata)
        # Size: ~1-2 KB per character
        # Loaded from: character_profiles/*.json
        # Cleared: After session ends
```

### Loading Strategy

#### **On Campaign Start**:
```python
# 1. Load campaign metadata (lightweight)
campaign_data = CampaignData.from_json("campaign_12345/campaign_data.json")
# Size: ~5-10 KB
# Contains: Character IDs, scene refs, quest refs

# 2. Initialize CharacterManager
char_manager = CharacterManager("campaign_12345")

# 3. Load all campaign characters (moderate)
char_manager._load_characters()
# Size: ~3-5 KB per character
# For 4 characters: ~20 KB total
# Contains: HP, inventory, abilities, location

# 4. Profiles NOT loaded yet (lazy)
char_manager._profile_cache = {}  # Empty
```

#### **On First Profile Access**:
```python
# User requests character portrait or voice
profile = char_manager._get_profile("pc:kara_smith")

# Flow:
if "pc:kara_smith" in self._profile_cache:
    return self._profile_cache["pc:kara_smith"]  # Cache hit
else:
    profile = self.profile_storage.load_profile("pc:kara_smith")  # Disk I/O
    self._profile_cache["pc:kara_smith"] = profile  # Cache for future
    return profile
```

#### **On Session End**:
```python
# Persist any unsaved changes
char_manager.persist_characters()

# Clear cache (profiles are reloaded next session)
char_manager._profile_cache.clear()

# CharacterInfo saved to disk:
# campaign_12345/characters/pc:kara_smith.json
```

### Memory Efficiency

**4-Character Campaign Example**:

```
Campaign Load:
├─ CampaignData: ~8 KB
├─ CharacterInfo × 4: ~20 KB
└─ CharacterProfile cache: ~0 KB (lazy)
Total: ~28 KB

After First Portrait Request:
├─ CampaignData: ~8 KB
├─ CharacterInfo × 4: ~20 KB
└─ CharacterProfile cache × 1: ~2 KB
Total: ~30 KB

After Viewing All Characters:
├─ CampaignData: ~8 KB
├─ CharacterInfo × 4: ~20 KB
└─ CharacterProfile cache × 4: ~8 KB
Total: ~36 KB
```

**Key Optimization**: Profiles only loaded when needed (portrait display, voice synthesis, visual metadata access).

---

### Read/Write Patterns

#### **High-Frequency Operations (Every Turn)**:
```python
# Get character (from memory - no disk I/O)
character = char_manager.get_character("pc:kara_smith")
# → O(1) dict lookup
# → No file reads

# Update HP (in memory)
character.hit_points_current -= 8
# → Direct memory write

# Persist (write to disk - batched)
char_manager.persist_characters()
# → Writes all CharacterInfo to campaign_id/characters/
# → Called once per turn, not per update
```

#### **Low-Frequency Operations (Portrait/Voice)**:
```python
# Get enriched character (lazy loads profile)
enriched = char_manager.get_enriched_character("pc:kara_smith")
# → CharacterInfo from memory (O(1))
# → CharacterProfile from cache or disk (O(1) or O(disk))
# → Cache hit after first load

# Generate portrait (writes to global layer)
result = char_manager.generate_character_portrait("pc:kara_smith")
# → Generates image: images/runware_image_999.png
# → Updates profile: character_profiles/pc:kara_smith.json
# → Does NOT touch CharacterInfo
```

---

## Summary

### The Two-Layer Model

| Aspect | CharacterProfile (Global) | CharacterInfo (Campaign) |
|--------|---------------------------|--------------------------|
| **File Location** | `character_profiles/{id}.json` | `{campaign}/characters/{id}.json` |
| **Purpose** | Character identity (who they are) | Campaign state (what's happening) |
| **Contains** | Portrait, voice, visual metadata, backstory | HP, inventory, location, XP, status |
| **Scope** | Shared across all campaigns | One campaign only |
| **Updated When** | Portrait generated, visual edited, voice assigned | Combat, leveling, items acquired, location changed |
| **In Memory** | Lazy-loaded, cached on-demand | Always loaded with campaign |
| **File Size** | ~1-2 KB | ~3-5 KB |
| **Persistence** | Permanent (never deleted) | Campaign lifetime |

### Data Flow Summary

```
Campaign Creation:
  User creates campaign
  → CampaignData saved
  → No characters yet

Character Setup:
  User loads preset
  → Preset template created (prof_pc:name.json, nulls)

  User edits → generates portrait
  → CharacterProfile created (pc:name.json, global, fully populated)
  → CharacterInfo created (campaign/characters/pc:name.json)
  → Portrait image saved (global)
  → Campaign links to character (ID reference)

Gameplay:
  Character takes damage
  → CharacterInfo updated (HP)
  → CharacterProfile unchanged

  Character levels up
  → CharacterInfo updated (level, abilities)
  → CharacterProfile unchanged (base_level stays same)

  Portrait regenerated
  → CharacterProfile updated (portrait URLs)
  → CharacterInfo unchanged

Campaign Load:
  Load campaign metadata
  → Load CharacterInfo (all characters)
  → CharacterProfile lazy-loaded on demand
```

### Key Takeaways

1. ✅ **Dual-layer model**: Global identity + Campaign state
2. ✅ **Three file types**: Preset templates (`prof_`), Global profiles (`pc:`), Campaign state
3. ✅ **Global identity exists**: CharacterProfile stores portrait/voice/visual data
4. ✅ **Campaign state separate**: CharacterInfo stores HP/inventory/location
5. ✅ **Preset preservation**: Original presets (`prof_`) kept unchanged with nulls
6. ✅ **Cross-campaign reuse**: Same profile, different campaign states
7. ✅ **Efficient loading**: Characters loaded eagerly, profiles lazy-loaded
8. ✅ **Minimal duplication**: Portraits never duplicated, only referenced
9. ✅ **Smart updates**: Portrait/voice update profile, damage updates campaign state
10. ✅ **Memory efficient**: ~36 KB for 4-character campaign (fully loaded)

### Practical Benefits

**For Players**:
- Use same character in multiple campaigns
- Portraits/voices persist across campaigns
- Each campaign has independent progress

**For System**:
- Portrait generated once, shared everywhere
- Campaign files stay small (just references)
- Efficient memory usage (lazy loading)
- Clear separation of concerns (identity vs state)

---

## Related Documentation

- **CharacterProfile Model**: `backend/src/core/character/models/character_profile.py`
- **CharacterInfo Model**: `backend/src/core/character/models/character_info.py`
- **CampaignData Model**: `backend/src/core/models/campaign.py`
- **CharacterManager**: `backend/src/core/character/character_manager.py`
- **ProfileStorage**: `backend/src/core/character/profile_storage.py`
- **Portrait Verification**: `docs/character-portrait-persistence-verification.md`
- **Implementation Summary**: `docs/character-portrait-implementation-summary.md`

---

**Last Updated**: October 15, 2025
**Version**: 1.1
**Status**: Current implementation - verified working
**Changelog**:
- Added comprehensive explanation of profile file types (`prof_`, `pc:`, campaign state)
- Added Q6: Understanding multiple character files with similar names
- Updated directory structure to show preset templates vs customized profiles
- Clarified why some files have null values vs full data
- Added creation timeline examples
