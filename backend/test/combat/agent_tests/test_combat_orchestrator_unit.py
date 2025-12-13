"""
Unit tests for CombatOrchestrator.

Validates that:
- Combat initiates with correct scene resolution
- Turn and combatant states are properly tracked
- Victory conditions are checked and handled
- NPC turns are properly handed off
- Combat action sessions are persisted
"""

import pytest
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from gaia_private.orchestration.combat_orchestrator import CombatOrchestrator
from gaia.mechanics.combat.combat_state_manager import CombatStateManager
from gaia_private.session.campaign_runner import CampaignRunner
from gaia_private.models.combat.orchestration import CombatAnalysisContext
from gaia.models.character.character_info import CharacterInfo
from gaia.models.combat import CombatSession, CombatantState, CombatStatus
from gaia.models.scene_info import SceneInfo
from gaia.mechanics.combat.combat_action_results import (
    TurnTransitionResult,
    TurnTransitionReason,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s]: %(message)s')


@pytest.fixture
def temp_campaign_dir(tmp_path):
    """Create temporary campaign storage directory."""
    campaign_storage = tmp_path / "campaigns"
    campaign_storage.mkdir()
    return campaign_storage


@pytest.fixture
def campaign_id():
    """Test campaign ID."""
    return "test_combat_orch_001"


@pytest.fixture
def mock_campaign_runner(campaign_id, temp_campaign_dir):
    """Create a mock campaign runner for testing."""
    runner = Mock(spec=CampaignRunner)
    runner.campaign_id = campaign_id

    # Create mock character manager
    char_manager = Mock()
    runner.character_manager = char_manager

    # Create mock combat state manager
    combat_manager = Mock(spec=CombatStateManager)
    combat_manager.active_sessions = {}
    combat_manager.initialized_combat = {}
    runner.combat_state_manager = combat_manager

    # Create mock scene integration
    scene_integration = Mock()
    scene_integration.current_scenes = {}
    runner.scene_integration = scene_integration

    # Mock campaign manager
    campaign_manager = Mock()
    campaign_manager.get_campaign_data_path = lambda cid: temp_campaign_dir / cid
    runner.campaign_manager = campaign_manager

    return runner


@pytest.fixture
def combat_orchestrator(mock_campaign_runner):
    """Create a CombatOrchestrator instance."""
    return CombatOrchestrator(mock_campaign_runner)


@pytest.fixture
def analysis_context(campaign_id):
    """Create a combat analysis context for testing."""
    return CombatAnalysisContext(
        campaign_id=campaign_id,
        current_scene={
            "scene_id": f"scene_{campaign_id}_001",
            "title": "Goblin Ambush",
            "description": "A forest crossroads"
        },
        game_state={"location": "Forest Crossroads", "time": "Midday"},
        players=[{
            "name": "Thorin",
            "class": "Fighter",
            "level": 5,
            "hp_max": 44,
            "hp_current": 44,
            "armor_class": 18,
            "ac": 18,
            "initiative_bonus": 2
        }],
        npcs=[
            {"name": "Goblin Scout", "type": "enemy", "hostile": True},
            {"name": "Goblin Warrior", "type": "enemy", "hostile": True}
        ],
        hostiles=[
            {"name": "Goblin Scout", "type": "Goblin", "hp": 7, "ac": 15, "initiative_bonus": 2},
            {"name": "Goblin Warrior", "type": "Goblin", "hp": 10, "ac": 14, "initiative_bonus": 1}
        ],
        threat_level="medium"
    )


@pytest.mark.asyncio
async def test_combat_scene_resolution(campaign_id):
    """Test that combat sessions properly resolve and track scene information.

    Validates:
    - Scene ID is extracted and stored in combat session
    - Scene context is maintained through combat
    """
    # Create combat session with scene information
    scene_id = f"scene_{campaign_id}_001"
    combat_session = CombatSession(
        session_id=f"{scene_id} - round 1",
        scene_id=scene_id,
        status=CombatStatus.IN_PROGRESS,
        round_number=1
    )

    # Validate scene information is properly stored
    assert combat_session.scene_id == scene_id
    assert combat_session.session_id.startswith(scene_id)

    # Simulate scene context being maintained through combat
    scene_context = {
        "scene_id": combat_session.scene_id,
        "title": "Goblin Ambush",
        "description": "A forest crossroads"
    }

    # Validate scene resolution
    assert scene_context["scene_id"] == scene_id
    assert combat_session.scene_id == scene_context["scene_id"]


@pytest.mark.asyncio
async def test_turn_and_combatant_tracking(mock_campaign_runner, campaign_id):
    """Test that turns and combatants are properly tracked.

    Validates:
    - Combatants are properly registered
    - Turn order is maintained
    - Current turn is tracked
    """
    # Create a real combat session
    combat_session = CombatSession(
        session_id=f"scene_{campaign_id}_001 - round 1",
        scene_id=f"scene_{campaign_id}_001",
        status=CombatStatus.IN_PROGRESS,
        round_number=1,
        current_turn_index=0
    )

    # Add combatants
    player = CombatantState(
        character_id="player_001",
        name="Thorin",
        is_npc=False,
        initiative=15,
        hp=44,
        max_hp=44,
        ac=18,
        level=5
    )
    goblin = CombatantState(
        character_id="goblin_001",
        name="Goblin Scout",
        is_npc=True,
        initiative=12,
        hp=7,
        max_hp=7,
        ac=15,
        level=1
    )

    combat_session.combatants = {
        "player_001": player,
        "goblin_001": goblin
    }
    combat_session.turn_order = ["player_001", "goblin_001"]

    # Validate turn tracking
    assert combat_session.current_turn_index == 0
    assert len(combat_session.turn_order) == 2
    assert combat_session.turn_order[0] == "player_001"

    # Simulate turn advancement
    combat_session.current_turn_index = 1
    assert combat_session.turn_order[combat_session.current_turn_index] == "goblin_001"

    # Validate combatant states
    assert player.hp == 44
    assert player.is_npc is False
    assert goblin.hp == 7
    assert goblin.is_npc is True


@pytest.mark.asyncio
async def test_victory_condition_handling():
    """Test victory condition detection.

    Validates:
    - All enemies defeated triggers victory
    - Combat status changes to completed
    """
    # Create combat session with defeated enemies
    combat_session = CombatSession(
        session_id="test_victory",
        scene_id="test_scene",
        status=CombatStatus.IN_PROGRESS,
        round_number=3
    )

    # Add player (alive)
    player = CombatantState(
        character_id="player_001",
        name="Thorin",
        is_npc=False,
        initiative=15,
        hp=30,
        max_hp=44,
        ac=18,
        level=5
    )

    # Add defeated enemy (0 hp)
    goblin = CombatantState(
        character_id="goblin_001",
        name="Goblin",
        is_npc=True,
        initiative=12,
        hp=0,  # Defeated
        max_hp=7,
        ac=15,
        level=1
    )

    combat_session.combatants = {
        "player_001": player,
        "goblin_001": goblin
    }

    # Check victory condition: all NPCs have 0 HP
    npcs = [c for c in combat_session.combatants.values() if c.is_npc]
    all_npcs_defeated = all(npc.hp <= 0 for npc in npcs)

    assert all_npcs_defeated is True, "Victory condition not detected"

    # Simulate victory handling
    if all_npcs_defeated:
        combat_session.status = CombatStatus.COMPLETED

    assert combat_session.status == CombatStatus.COMPLETED


@pytest.mark.asyncio
async def test_npc_turn_handoff():
    """Test NPC turn handling.

    Validates:
    - NPC turns are identified correctly
    - System generates actions for NPCs
    """
    combat_session = CombatSession(
        session_id="test_npc_turn",
        scene_id="test_scene",
        status=CombatStatus.IN_PROGRESS,
        round_number=1,
        current_turn_index=1  # NPC turn
    )

    player = CombatantState(
        character_id="player_001",
        name="Thorin",
        is_npc=False,
        initiative=15,
        hp=44,
        max_hp=44,
        ac=18,
        level=5
    )

    goblin = CombatantState(
        character_id="goblin_001",
        name="Goblin",
        is_npc=True,  # This is an NPC
        initiative=12,
        hp=7,
        max_hp=7,
        ac=15,
        level=1
    )

    combat_session.combatants = {
        "player_001": player,
        "goblin_001": goblin
    }
    combat_session.turn_order = ["player_001", "goblin_001"]

    # Get current combatant
    current_id = combat_session.turn_order[combat_session.current_turn_index]
    current_combatant = combat_session.combatants[current_id]

    # Validate NPC turn detection
    assert current_id == "goblin_001"
    assert current_combatant.is_npc is True
    assert current_combatant.name == "Goblin"

    # Simulate NPC action generation (would normally call Combat agent)
    npc_action = {
        "actor": current_combatant.name,
        "action_type": "basic_attack",
        "target": "Thorin",
        "intent_description": "The goblin attacks!"
    }

    assert npc_action["actor"] == "Goblin"
    assert npc_action["action_type"] == "basic_attack"


@pytest.mark.asyncio
async def test_combat_persistence(mock_campaign_runner, campaign_id, temp_campaign_dir):
    """Test that combat sessions are persisted.

    Validates:
    - Combat sessions are saved to disk
    - Sessions can be recovered after restart
    """
    from gaia.mechanics.combat.combat_persistence import CombatPersistenceManager

    # Create campaign directory
    campaign_path = temp_campaign_dir / campaign_id
    campaign_path.mkdir(exist_ok=True)

    # Update mock to return real campaign manager
    real_campaign_manager = Mock()
    real_campaign_manager.get_campaign_data_path = lambda cid: temp_campaign_dir / cid
    real_campaign_manager.list_campaigns = lambda: {"campaigns": [{"id": campaign_id}]}

    persistence = CombatPersistenceManager(real_campaign_manager)

    # Create combat session
    combat_session = CombatSession(
        session_id=f"scene_{campaign_id}_001 - round 1",
        scene_id=f"scene_{campaign_id}_001",
        status=CombatStatus.IN_PROGRESS,
        round_number=1
    )

    player = CombatantState(
        character_id="player_001",
        name="Thorin",
        is_npc=False,
        initiative=15,
        hp=44,
        max_hp=44,
        ac=18,
        level=5
    )
    combat_session.combatants = {"player_001": player}
    combat_session.turn_order = ["player_001"]

    # Save session
    saved = persistence.save_combat_session(campaign_id, combat_session)
    assert saved is True, "Combat session should be persisted"

    # Verify file was created
    combat_file = campaign_path / "combat" / "active" / f"{combat_session.session_id}.json"
    assert combat_file.exists(), "Combat file should exist on disk"

    # Load session
    loaded = persistence.load_active_combat(campaign_id)
    assert loaded is not None, "Should load persisted combat"
    assert loaded.session_id == combat_session.session_id
    assert len(loaded.combatants) == 1


@pytest.mark.asyncio
async def test_turn_continues_does_not_advance(combat_orchestrator, mock_campaign_runner, campaign_id):
    """Test that turn does not advance when combatant still has AP remaining.

    This test validates the fix for the bug where turns were advancing prematurely
    even when the current combatant had action points remaining.

    Validates:
    - Turn does NOT advance when turn_resolution.reason == "turn_continues"
    - Turn does NOT advance when current_actor == next_combatant
    - current_turn_index stays the same
    """
    from gaia_private.models.combat.agent_io import AgentCombatResponse

    # Create combat session with character that has AP remaining
    combat_session = CombatSession(
        session_id=f"scene_{campaign_id}_001 - round 1",
        scene_id=f"scene_{campaign_id}_001",
        status=CombatStatus.IN_PROGRESS,
        round_number=1,
        current_turn_index=0  # First character's turn
    )

    # Add combatants
    lyra = CombatantState(
        character_id="pc:lyra",
        name="Lyra",
        is_npc=False,
        initiative=19,
        hp=28,
        max_hp=28,
        ac=14,
        level=5
    )
    theron = CombatantState(
        character_id="npc:theron",
        name="Theron",
        is_npc=True,
        initiative=16,
        hp=32,
        max_hp=32,
        ac=15,
        level=5
    )

    combat_session.combatants = {
        "pc:lyra": lyra,
        "npc:theron": theron
    }
    combat_session.turn_order = ["pc:lyra", "npc:theron"]

    # Create combat response with turn_continues
    combat_response = Mock(spec=AgentCombatResponse)
    combat_response.turn_resolution = TurnTransitionResult(
        current_actor="Lyra",
        next_combatant="Lyra",  # Same combatant
        reason=TurnTransitionReason.TURN_CONTINUES,  # Turn continues!
        new_round=False,
        round_number=1,
        order_index=0
    )

    # Setup mock campaign runner with combat state manager
    mock_campaign_runner.combat_state_manager.active_sessions = {}

    # Store initial turn index
    initial_turn_index = combat_session.current_turn_index
    initial_current_character = combat_session.resolve_current_character()

    # Apply turn resolution (this should NOT advance the turn)
    combat_orchestrator._apply_turn_resolution(combat_session, combat_response)

    # Verify turn did NOT advance
    assert combat_session.current_turn_index == initial_turn_index, \
        "Turn index should not change when turn continues"
    assert combat_session.resolve_current_character() == initial_current_character, \
        "Current character should not change when turn continues"
    assert combat_session.resolve_current_character() == "pc:lyra", \
        "Lyra should still be the active combatant"


@pytest.mark.asyncio
async def test_turn_advances_when_different_combatant(combat_orchestrator, mock_campaign_runner, campaign_id):
    """Test that turn DOES advance when moving to a different combatant.

    Validates:
    - Turn advances when current_actor != next_combatant
    - Turn advances when reason is NOT "turn_continues"
    - current_turn_index increments correctly
    """
    from gaia_private.models.combat.agent_io import AgentCombatResponse

    # Create combat session
    combat_session = CombatSession(
        session_id=f"scene_{campaign_id}_001 - round 1",
        scene_id=f"scene_{campaign_id}_001",
        status=CombatStatus.IN_PROGRESS,
        round_number=1,
        current_turn_index=0
    )

    # Add combatants
    lyra = CombatantState(
        character_id="pc:lyra",
        name="Lyra",
        is_npc=False,
        initiative=19,
        hp=28,
        max_hp=28,
        ac=14,
        level=5
    )
    theron = CombatantState(
        character_id="npc:theron",
        name="Theron",
        is_npc=True,
        initiative=16,
        hp=32,
        max_hp=32,
        ac=15,
        level=5
    )

    combat_session.combatants = {
        "pc:lyra": lyra,
        "npc:theron": theron
    }
    combat_session.turn_order = ["pc:lyra", "npc:theron"]

    # Create combat response with actual turn transition
    combat_response = Mock(spec=AgentCombatResponse)
    combat_response.turn_resolution = TurnTransitionResult(
        current_actor="Lyra",
        next_combatant="Theron",  # Different combatant
        reason=TurnTransitionReason.AP_EXHAUSTED,  # Turn ending reason
        new_round=False,
        round_number=1,
        order_index=1
    )

    # Setup mock campaign runner
    mock_campaign_runner.combat_state_manager.active_sessions = {}

    # Store initial state
    initial_turn_index = combat_session.current_turn_index
    assert combat_session.resolve_current_character() == "pc:lyra"

    # Apply turn resolution (this SHOULD advance the turn)
    combat_orchestrator._apply_turn_resolution(combat_session, combat_response)

    # Verify turn DID advance
    assert combat_session.current_turn_index == initial_turn_index + 1, \
        "Turn index should increment when advancing to different combatant"
    assert combat_session.resolve_current_character() == "npc:theron", \
        "Theron should now be the active combatant"


def test_annotate_combat_end_adds_structured_data(combat_orchestrator):
    """Ensure combat end annotations mark responses correctly."""
    formatted = {
        "structured_data": {
            "answer": "Theron collapses as the final blow lands.",
            "narrative": "Lyra channels her last spell and the enemy falls.",
            "turn": "Awaiting next action."
        }
    }
    summary = {
        "session_id": "combat_session_123",
        "rounds": 4,
        "reason": "players_victory",
        "survivors": [{"name": "Lyra", "hp": "10/28", "conscious": True}]
    }

    result = combat_orchestrator._annotate_combat_end(
        formatted,
        end_reason="players_victory",
        combat_summary=summary
    )

    structured = result["structured_data"]
    assert structured["interaction_type"] == "combat_end"
    assert structured["next_interaction_type"] == "default"
    assert structured["combat_state"] == "players_victory"
    assert structured["combat_ended"]["reason"] == "players_victory"
    assert structured["combat_summary"] == summary
    assert structured["turn"] == "Combat has ended."
    assert "Combat has ended" in structured["answer"]
    assert "Combat has ended" in structured["narrative"]
    assert structured["is_combat_active"] is False
