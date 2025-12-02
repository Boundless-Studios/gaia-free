# Character Management System - Current State & Roadmap

## 2025-10-24 Update
- Character resolution is now handled by a dedicated `CharacterExtractorAgent` that runs after each Dungeon Master turn.
- Tool requests emitted by the extractor (e.g., `character_updater`) are executed automatically, so character creation/updating is deterministic.
- Downstream systems consume the structured `character_resolution` block rather than parsing narrative strings.
- The Dungeon Master prompt no longer generates player option lists or mutates roster state directly; those responsibilities are now post-processing steps.

## Current State (Implemented)

### Data Model Architecture

#### 1. Core Character Models
- **CharacterInfo** (`src/core/character/models/character_info.py`)
  - Complete D&D 5e character representation
  - Fields: HP (current/max), AC, abilities, inventory, status effects, location
  - Tracks: backstory, personality traits, bonds, flaws, dialog history
  - Uses readable IDs based on names (e.g., `zephyr_nightwhisper`)

- **CharacterProfile** (`src/core/character/models/character_profile.py`)
  - Lightweight cross-campaign character reference
  - Stores: voice assignment, visual description, portrait paths
  - Maps campaign IDs to character IDs (not full data)
  - Profile IDs follow pattern: `prof_character_name`

- **CharacterStatus** (Enum)
  - HEALTHY, INJURED, AFFECTED, UNCONSCIOUS, DEAD
  - Properly tracked but not yet enforced in gameplay

#### 2. Storage System
- **Dual Storage Approach**:
  1. **Global Storage** (`campaign-storage/characters/`)
     - Persistent character records across campaigns
     - Character files named by character ID (e.g., `zephyr_nightwhisper.json`)
  
  2. **Campaign-Specific Storage** (`campaign-storage/campaigns/{campaign_id}/characters/`)
     - Campaign-specific character state
     - Allows character evolution within campaigns
     - Includes `character_summary.json` for quick reference

- **CharacterStorage** (`src/core/character/character_storage.py`)
  - Handles file I/O operations
  - Generates consistent IDs from character names
  - Links characters to campaigns

- **ProfileStorage** (`src/core/character/profile_storage.py`)
  - Manages cross-campaign profiles
  - Handles voice assignments
  - Prevents data duplication

#### 3. Character Management
- **CharacterManager** (`src/core/character/character_manager.py`)
  - Per-campaign character management
  - Creates characters from simple input data
  - Persists to both global and campaign storage
  - Methods for updating character state (partially implemented)

- **CharacterTranslator** (`src/core/character/character_translator.py`)
  - Converts simple character data to full CharacterInfo
  - Calculates D&D stats (HP, AC) based on class/level
  - Generates starting inventory and abilities

#### 4. Voice System
- **VoicePool** (`src/core/character/voice_pool.py`)
  - Assigns voices based on character archetypes
  - Limited to available voices in VoiceRegistry
  - Prevents voice duplication within campaigns

### Current Game Flow

1. **Campaign Initialization**
   - User creates campaign with character slots
   - Characters can be pre-generated or custom
   - CharacterManager creates CharacterInfo objects
   - Characters saved to both storage locations
   - Voice assignments made automatically

2. **Character Context for DM**
   - CharacterManager provides `get_character_context_for_dm()`
   - Returns party summary with HP, AC, status, key items
   - DM agents receive character context in prompts

3. **Basic State Updates**
   - `update_character_from_dm()` method exists
   - Can update HP, status, inventory, location
   - Updates are persisted to storage
   - **NOT YET**: Real-time enforcement or validation

## Critical Gaps & Next Steps

### 1. Dynamic Character State Management
**Problem**: Characters don't update during gameplay

**Needed Implementation**:
```python
class CharacterStateManager:
    """Real-time character state tracking during gameplay"""
    
    def apply_damage(self, character_id: str, damage: int, damage_type: str):
        """Apply damage with type resistance/vulnerability checks"""
        
    def apply_healing(self, character_id: str, healing: int):
        """Apply healing up to max HP"""
        
    def add_status_effect(self, character_id: str, effect: StatusEffect):
        """Add conditions like poisoned, stunned, etc."""
        
    def consume_resource(self, character_id: str, resource: str, amount: int):
        """Track spell slots, abilities, items"""
        
    def validate_action(self, character_id: str, action: str) -> bool:
        """Check if character can perform action based on status"""
```

**Integration Points**:
- Hook into DM response parsing
- Extract damage/healing from narrative
- Update before next turn
- Persist after each round

### 2. Turn Order & Combat Management
**Problem**: No enforcement of initiative or turn structure

**Needed Implementation**:
```python
class CombatManager:
    """Manages combat rounds and turn order"""
    
    def __init__(self):
        self.initiative_order: List[str] = []  # Character IDs in order
        self.current_turn_index: int = 0
        self.round_number: int = 1
        self.combat_active: bool = False
        
    def roll_initiative(self, participants: List[CharacterInfo]):
        """Roll initiative for all participants"""
        # d20 + dexterity modifier
        
    def get_current_actor(self) -> str:
        """Return character ID whose turn it is"""
        
    def advance_turn(self):
        """Move to next character, handle round advancement"""
        
    def validate_action_timing(self, character_id: str, action_type: str) -> bool:
        """Ensure character acts only on their turn"""
```

**Required DM Agent Updates**:
- EncounterRunner needs to track initiative
- TurnRunner needs to enforce turn order
- DM must announce whose turn it is
- Block out-of-turn actions

### 3. Character Sheet UI
**Problem**: No frontend display of character information

**Needed Components**:
```jsx
// CharacterCard.jsx
- Display: Name, Class, Race, Level
- Stats: HP bar, AC shield, Status icons
- Resources: Spell slots, abilities
- Quick actions based on class

// PartyPanel.jsx  
- Grid/list of CharacterCards
- Initiative tracker during combat
- Highlight current turn
- Status effect timers

// CharacterDetailModal.jsx
- Full character sheet
- Inventory management
- Ability descriptions
- Character backstory/notes
```

### 4. State Synchronization
**Problem**: Frontend doesn't receive character updates

**Needed Implementation**:
1. **WebSocket Updates**
   ```python
   async def broadcast_character_update(character_id: str, update_type: str):
       """Send character state changes to frontend"""
   ```

2. **Structured Data Enhancement**
   ```python
   structured_data = {
       "narrative": "...",
       "character_updates": {
           "gharek": {"hp_change": -8, "status": "injured"},
           "elara": {"spell_slots": {"level_1": 2}}
       },
       "turn_order": ["elara", "gharek", "goblin_1"],
       "current_turn": "elara"
   }
   ```

### 5. Rules Enforcement
**Problem**: No validation of character actions

**Needed Systems**:
- **Action Validation**: Check class abilities, spell slots, item availability
- **Movement Tracking**: Enforce movement speed limits
- **Resource Management**: Track ammunition, spell components
- **Condition Effects**: Apply disadvantage, advantage, immunity
- **Death Saves**: Track and enforce death saving throws

## Implementation Priority

### Phase 1: Core State Management (Immediate)
1. Implement CharacterStateManager
2. Hook into DM response processing
3. Parse damage/healing from narratives
4. Test with simple combat scenarios

### Phase 2: Turn Order (Next Sprint)
1. Implement CombatManager
2. Update EncounterRunner agent
3. Add initiative rolling
4. Enforce turn-based actions

### Phase 3: Frontend Display (Following Sprint)
1. Create CharacterCard components
2. Add PartyPanel to game view
3. Implement real-time updates via WebSocket
4. Add health bars and status indicators

### Phase 4: Advanced Features (Future)
1. Full character sheet UI
2. Inventory management
3. Spell/ability tracking
4. Character progression/leveling

## Technical Integration Points

### Backend Flow
```
User Input → ScenarioAnalyzer → DM (with character context) 
    → Response with character updates → CharacterStateManager 
    → Update storage → Broadcast to frontend
```

### Frontend Flow
```
WebSocket receives update → Update Redux/State 
    → Re-render CharacterCards → Highlight changes 
    → Update turn indicator
```

### Data Flow Example
```python
# DM generates response
dm_response = {
    "narrative": "The orc's axe strikes Gharek for 8 damage!",
    "character_updates": {
        "gharek": {
            "hit_points_current": 22,  # was 30
            "status": "injured"
        }
    }
}

# CharacterManager processes
character_manager.update_character_from_dm(dm_response)

# Frontend receives via WebSocket
{
    "type": "character_update",
    "character_id": "gharek",
    "changes": {
        "hp": {"current": 22, "max": 30},
        "status": "injured"
    }
}
```

## Success Metrics
- Characters persist across sessions ✅
- HP/status updates reflected immediately ⏳
- Turn order enforced in combat ❌
- Frontend displays current character state ❌
- Death/unconscious states handled properly ❌
- Resources tracked accurately ❌

## Next Immediate Steps
1. Complete `update_character_from_dm()` implementation
2. Add character update parsing to DM response handler
3. Create WebSocket endpoint for character updates
4. Build minimal CharacterCard component
5. Test with a simple combat encounter
