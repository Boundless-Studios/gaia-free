# Test Coverage for Scene Roster Consistency Implementation

## Overview

This document catalogs the test coverage for the scene roster consistency refactoring work, which aims to establish canonical participant rosters and ensure consistent character role tracking across scene, combat, and turn systems.

## Test Files Created

### 1. `test/core/session/scene/test_scene_participant.py`
**Purpose**: Unit tests for the SceneParticipant data model

**Coverage**:
- ✅ Creating participants with different roles (PLAYER, NPC_COMBATANT, NPC_SUPPORT)
- ✅ Participant capability flags (COMBAT, NARRATIVE, INVENTORY, SKILLS)
- ✅ Join/leave timestamp tracking
- ✅ Serialization/deserialization (to_dict/from_dict)
- ✅ Capability validation
- ✅ Participants without character IDs (lightweight NPCs)
- ✅ Multiple capabilities per participant
- ✅ Round-trip serialization integrity

**Key Validations**:
- CharacterRole enum usage
- CharacterCapability bitflags
- Temporal tracking (joined_at, left_at)
- Backward compatibility with legacy systems

---

### 2. `test/core/session/scene/test_scene_roster_manager.py`
**Purpose**: Unit tests for SceneRosterManager functionality

**Coverage**:
- ✅ Adding participants by CharacterInfo object
- ✅ Adding participants by character ID (with CharacterManager lookup)
- ✅ Removing participants (marking as not present)
- ✅ Filtering present vs absent participants
- ✅ Getting participants by role (PLAYER, NPC_COMBATANT, etc.)
- ✅ Getting combat-capable participants only
- ✅ Role lookup for specific characters
- ✅ Capability checking (has_capability)
- ✅ Bootstrapping roster from SceneInfo
- ✅ Syncing roster from turn data
- ✅ Tracking participant deltas (added/removed)
- ✅ Scene isolation (different scenes have separate rosters)
- ✅ Participant persistence across calls
- ✅ Duplicate prevention
- ✅ Combat readiness validation

**Key Validations**:
- Roster manager as single source of truth
- CharacterManager integration
- Scene-scoped participant tracking
- Capability-based filtering
- Delta tracking for join/leave events

---

### 3. `test/core/session/test_participant_role_consistency.py`
**Purpose**: Integration tests for consistent role tracking across systems

**Coverage**:
- ✅ Player role consistency from scene to turn
- ✅ NPC combatant role consistency
- ✅ NPC support exclusion from combat roster
- ✅ Mixed participant scenes (players + combatants + support NPCs)
- ✅ Combat initiation respects roster roles
- ✅ Turn type inference from roster role
- ✅ Participant join/leave delta tracking
- ✅ Capability validation before actions
- ✅ Roster snapshot for SceneInfo persistence
- ✅ DM narrative turn type
- ✅ Character ID prefix fallback (when roster unavailable)
- ✅ Roster persistence in SceneInfo

**Key Validations**:
- **Scene → Turn consistency**: Roles set in scene roster match turn types
- **Scene → Combat consistency**: Combat participants derived from roster
- **Cross-system consistency**: Same character has same role everywhere
- **Backward compatibility**: Legacy pcs_present/npcs_present still work

---

### 4. `test/core/character/test_npc_character_tracking.py`
**Purpose**: Tests for NPC lifecycle and character tracking improvements

**Coverage**:
- ✅ NPC first appearance tracking
- ✅ Combatant vs support NPC distinction
- ✅ NPC role upgrades (support → combatant)
- ✅ Interaction count tracking
- ✅ NPCs without full CharacterInfo (lightweight profiles)
- ✅ NPC ID generation from names
- ✅ Hostile vs friendly NPC tracking
- ✅ Multiple NPCs with same name (different IDs)
- ✅ Visual appearance tracking (for consistency)
- ✅ Voice assignment for TTS
- ✅ NPC persistence across multiple scenes

**Key Validations**:
- NPC lifecycle management (first appearance → recurring)
- Role flexibility (support NPCs can become combatants)
- Metadata tracking (hostile flag, appearance, voice)
- Scene-to-scene NPC persistence
- Unique identification (multiple "Guard" NPCs)

---

### 5. `test/core/session/test_turn_type_inference_enhanced.py`
**Purpose**: Tests for enhanced turn type inference using roster data

**Coverage**:
- ✅ Inferring PLAYER turn type from roster
- ✅ Inferring NPC turn type from roster
- ✅ DM always gets NARRATIVE type
- ✅ Fallback to character_id prefix (roster unavailable)
- ✅ Explicit turn type override
- ✅ NPC support characters get NPC turn type
- ✅ Characters not in roster (fallback behavior)
- ✅ Turn type consistency across multiple turns
- ✅ Mixed scene turn types (players + NPCs)
- ✅ Turn type after role change
- ✅ Empty character_id defaults
- ✅ Case-insensitive DM detection
- ✅ NPC prefix variations

**Key Validations**:
- **Priority**: Explicit override > Roster role > Character ID prefix
- **Consistency**: Same character always gets same turn type
- **Fallback safety**: System works even without roster
- **DM special case**: Always NARRATIVE regardless of ID

---

## Gap Analysis: What Was Missing Before

### Previously Tested ✓
- Basic scene CRUD (create, retrieve, update)
- Scene transition detection
- Character-campaign integration basics
- Turn model serialization
- Basic turn type enum usage

### Previously UNTESTED ✗ (Now Covered)
1. **SceneParticipant model** - New data structure, no tests existed
2. **SceneRosterManager** - New component, no tests existed
3. **Participant role tracking** - Scene/combat/turn consistency not validated
4. **NPC lifecycle management** - First appearance → recurring not tested
5. **Role-based turn type inference** - Only tested ID-based heuristics
6. **Capability validation** - No tests for combat-capable filtering
7. **Participant join/leave deltas** - Not tested in existing suite
8. **NPC role upgrades** - Support → combatant transitions not tested
9. **Cross-system integration** - No tests verifying scene/combat/turn alignment
10. **Roster bootstrapping** - Converting SceneInfo to roster not tested

---

## Test Execution

### Running Individual Test Files

```bash
# SceneParticipant model tests
python3 gaia_launcher.py test backend/test/core/session/scene/test_scene_participant.py

# SceneRosterManager tests
python3 gaia_launcher.py test backend/test/core/session/scene/test_scene_roster_manager.py

# Role consistency integration tests
python3 gaia_launcher.py test backend/test/core/session/test_participant_role_consistency.py

# NPC tracking tests
python3 gaia_launcher.py test backend/test/core/character/test_npc_character_tracking.py

# Enhanced turn type inference tests
python3 gaia_launcher.py test backend/test/core/session/test_turn_type_inference_enhanced.py
```

### Running All Roster Consistency Tests

```bash
# Run all new tests in one command
python3 gaia_launcher.py test \
  backend/test/core/session/scene/test_scene_participant.py \
  backend/test/core/session/scene/test_scene_roster_manager.py \
  backend/test/core/session/test_participant_role_consistency.py \
  backend/test/core/character/test_npc_character_tracking.py \
  backend/test/core/session/test_turn_type_inference_enhanced.py
```

---

## Success Criteria Validation

These tests validate the success criteria from `m-refactor-scene-roster-consistency.md`:

| Criteria | Test Coverage |
|----------|---------------|
| ✅ Core models implemented (CharacterRole, CharacterCapability, SceneParticipant) | `test_scene_participant.py` |
| ✅ SceneRosterManager created and integrated | `test_scene_roster_manager.py` |
| ✅ NPC lifecycle management | `test_npc_character_tracking.py` |
| ✅ Combat/turn systems use roster data for is_player/is_npc | `test_participant_role_consistency.py` |
| ✅ Turn type inference enhanced with roster | `test_turn_type_inference_enhanced.py` |
| ✅ Consistent participant roles across scene/combat/turn | `test_participant_role_consistency.py` |

---

## Implementation Dependencies

These tests will **PASS** once the following are implemented:

### Required Models
- `SceneParticipant` dataclass in `backend/src/core/session/scene/models.py`
- Already exists: `CharacterRole` and `CharacterCapability` enums

### Required Managers
- `SceneRosterManager` in `backend/src/core/session/scene/scene_roster_manager.py`
- Integration with `SceneIntegration`
- Integration with `TurnManager._infer_turn_type()`

### Required Methods
- `SceneRosterManager.add_participant(scene_id, character)`
- `SceneRosterManager.remove_participant(scene_id, character_id)`
- `SceneRosterManager.get_participants(scene_id, include_absent=False)`
- `SceneRosterManager.get_participants_by_role(scene_id, role)`
- `SceneRosterManager.get_combat_participants(scene_id)`
- `SceneRosterManager.lookup_role(scene_id, character_id)`
- `SceneRosterManager.has_capability(scene_id, character_id, capability)`
- `SceneRosterManager.bootstrap_scene(scene_info, previous_scene=None)`
- `SceneRosterManager.sync_from_turn(scene_id, turn_data)`
- `SceneRosterManager.get_participant_deltas(scene_id, previous_participants)`

---

## Notes for Codex

When implementing the roster consistency work:

1. **Run tests incrementally** - Implement one component at a time and run its tests
2. **Use TDD approach** - Tests are written, so implement until they pass
3. **Mock wisely** - Tests use mocks for CharacterManager; ensure real implementation matches
4. **Preserve backward compatibility** - Tests verify legacy fields (pcs_present, npcs_present) still work
5. **Handle edge cases** - Tests cover None values, empty rosters, duplicate additions, etc.

---

## Expected Test Results

**Before Implementation**: All tests should FAIL (components don't exist yet)

**After Implementation**: All tests should PASS, validating:
- SceneParticipant model works correctly
- SceneRosterManager maintains accurate rosters
- Scene/Combat/Turn systems use consistent roles
- NPC tracking lifecycle works end-to-end
- Turn type inference uses roster data appropriately

---

## Future Test Additions

Consider adding these tests after initial implementation:

1. **Migration tests** - Validate converting old scenes to new participant model
2. **Performance tests** - Ensure roster lookups scale with large participant counts
3. **Concurrency tests** - Validate thread-safety if multiple systems access roster
4. **Serialization tests** - Full round-trip through JSON persistence
5. **Combat integration tests** - End-to-end combat with roster-driven setup

---

## Summary

**Total Test Files**: 5
**Total Test Cases**: ~60+
**Systems Covered**: Scene Management, Character Tracking, Turn Management, Combat Integration
**New Components Validated**: SceneParticipant, SceneRosterManager, Enhanced Turn Type Inference

These tests provide comprehensive coverage for the scene roster consistency refactoring and will ensure the implementation maintains data integrity across all game systems.
