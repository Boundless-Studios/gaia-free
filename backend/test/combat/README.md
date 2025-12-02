# Combat System Tests

Tests are organized into focused subdirectories by purpose.

## Directory Structure

```
test/combat/
├── agents/          # Combat agent behavior and orchestration
├── flow/            # Combat flow sequences (initiation, turns)
├── data/            # Data models and structures
├── mechanics/       # Game mechanics (AP, turns, scenes)
└── integration/     # End-to-end integration tests
```

### `agents/` - Combat Agent Tests (8 files)
Tests for agent behavior, action selection, and orchestration.

- `test_combat_action_selection.py` - Action selection logic and AP mechanics
- `test_combat_agent_integration.py` - Combat initiator agent integration
- `test_combat_agent_updated.py` - Split combat agent architecture (integration style)
- `test_split_combat_agents.py` - Split combat agent architecture (unit tests with mocks)
- `test_combat_narrative_handoff.py` - Narrative handoff between orchestrator and combat
- `test_combat_orchestrator_unit.py` - Combat orchestrator (integration style with real components)
- `test_npc_agent_isolated.py` - Isolated NPC agent behavior
- `test_npc_with_logging.py` - NPC agent with logging validation

**Also see:** `test/orchestrator/test_combat_orchestrator.py` (pytest-style unit tests with mocks)

### `flow/` - Combat Flow Tests (5 files)
Tests for combat sequencing, initiation, and turn management.

- `test_combat_initiation_flow.py` - Complete combat initiation flow validation
- `test_combat_init_simple.py` - Simple combat initiation formatting test
- `test_combat_turn_order.py` - Turn order and round advancement
- `test_combat_initiative_alignment.py` - Initiative order alignment with combat session
- `test_combat_initiator_guardrails.py` - Guardrail behavior validation

### `data/` - Data Model Tests (4 files)
Tests for combat data structures and validation.

- `test_combat_models.py` - Combat system data model validation
- `test_combat_request_building.py` - Combat request construction
- `test_combat_initiation_models.py` - Combat initiation data model tests
- `test_combat_engine_structs.py` - Structured results vs tuples validation

### `mechanics/` - Combat Mechanics Tests (7 files)
Tests for game mechanics: AP, turns, scenes, and specific scenarios.

- `test_action_points.py` - Action point configuration and calculations
- `test_action_points_overdraw.py` - AP overdraw mechanics and penalties
- `combat_test_turn_simple.py` - Turn management at model level
- `combat_test_turn_combat_scene.py` - Turn management in combat scenes
- `combat_test_turn_combat_logic.py` - Scene type logic for turns
- `combat_test_combat_scene_association.py` - Combat/scene association tests
- `test_combat_double_attack.py` - Double attack scenario mechanics

### `integration/` - Integration Tests (2 files)
End-to-end tests requiring full system components.

- `test_combat_full_integration.py` ⭐ **MOST COMPREHENSIVE** - Complete combat flow from scene setup through multiple rounds
- `test_combat_persistence.py` - Combat state persistence across session restarts

### Core Engine Tests (outside test/combat/)
- `test/core/session/combat/test_combat_engine.py` - Core combat engine mechanics (AP, damage, attacks, **NEW: target validation**)

## Running Tests

### Run all combat tests:
```bash
python3 gaia_launcher.py test test/combat/
```

### Run by category:
```bash
# Agent tests
python3 gaia_launcher.py test test/combat/agents/

# Flow tests
python3 gaia_launcher.py test test/combat/flow/

# Data model tests
python3 gaia_launcher.py test test/combat/data/

# Mechanics tests
python3 gaia_launcher.py test test/combat/mechanics/

# Integration tests (requires full system)
python3 gaia_launcher.py test test/combat/integration/
```

### Run specific test:
```bash
python3 gaia_launcher.py test test/combat/integration/test_combat_full_integration.py
```

### Run core engine tests:
```bash
python3 gaia_launcher.py test test/core/session/combat/
```

## Test Classification

### ✅ Unit Tests (can run in isolation with mocks)
- Most tests in `agents/` (except integration-style ones)
- All tests in `data/`
- All tests in `mechanics/`
- Some tests in `flow/`

### 🔧 Integration Tests (require Docker/LLM/full system)
- `agents/test_combat_agent_integration.py`
- `agents/test_combat_agent_updated.py`
- `agents/test_combat_orchestrator_unit.py`
- `flow/test_combat_initiation_flow.py`
- All tests in `integration/`

### 📝 Component Tests (test specific components)
- Most tests in `flow/` and `mechanics/`

## Redundancy Analysis

**No truly redundant tests found.** Tests that appear similar actually test different aspects:

- **Combat Orchestrator** (2 tests):
  - `agents/test_combat_orchestrator_unit.py` - Integration-style with real components
  - `test/orchestrator/test_combat_orchestrator.py` - Pytest unit tests with mocks
  - **Both valuable** - different testing approaches

- **Split Combat Agents** (2 tests):
  - `agents/test_combat_agent_updated.py` - Integration test of complete 4-step flow
  - `agents/test_split_combat_agents.py` - Pytest unit tests for individual agent components
  - **Both valuable** - integration vs unit testing

- **Turn Tests** (4 tests):
  - `mechanics/combat_test_turn_simple.py` - Model-level turn logic
  - `mechanics/combat_test_turn_combat_scene.py` - Turn manager integration with scenes
  - `mechanics/combat_test_turn_combat_logic.py` - Scene type determination logic
  - `mechanics/combat_test_combat_scene_association.py` - Combat/scene associations
  - **All distinct** - test different layers/concerns

## Recently Updated

- **2025-09-30**: Organized tests into subdirectories
- **2025-09-30**: Removed `test_debug_combat_init_simple.py` (debug script)
- **2025-09-30**: Added target validation to combat engine

## Notes

- Tests requiring Docker/LLM should be marked with `@pytest.mark.integration`
- Unit tests use mocking for external dependencies
- All new combat features should have corresponding tests
- When adding tests, place them in the appropriate subdirectory
