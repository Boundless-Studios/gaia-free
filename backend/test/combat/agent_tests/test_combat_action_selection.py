"""Test combat action selection and AP mechanics."""

import asyncio
import logging
import pytest
from unittest.mock import Mock, AsyncMock, patch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_combat_action_selection():
    """Test that action selection properly returns actions with AP costs."""
    print("\n" + "="*60)
    print("Testing Combat Action Selection Agent")
    print("="*60)

    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

    from gaia_private.agents.combat.action_selector import CombatActionSelectionAgent
    from gaia_private.agents.combat.models import CombatActionSelectionOutput
    from gaia_private.models.combat.agent_io.fight import (
        CombatActionRequest,
        CombatantView,
        CurrentTurnInfo
    )

    agent = CombatActionSelectionAgent()

    # Mock the LLM response
    mock_response = CombatActionSelectionOutput(
        actions=[{
            "actor": "Fighter",
            "action_type": "basic_attack",
            "target": "Goblin",
            "intent_description": "attack the goblin with sword"
        }],
        tactical_reasoning="Attack the nearest enemy",
        expected_ap_usage=2
    )

    # Create a test request
    request = CombatActionRequest(
        campaign_id="test",
        combat_id="test_001",
        player_action="I attack the goblin with my sword",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Fighter",
            available_actions=["basic_attack", "defend", "move", "end_turn"]
        ),
        combatants=[
            CombatantView(
                name="Fighter",
                type="player",
                hp_current=20,
                hp_max=20,
                action_points_current=3,
                action_points_max=3,
                armor_class=16,
                is_active=True,
                is_conscious=True
            ),
            CombatantView(
                name="Goblin",
                type="enemy",
                hp_current=10,
                hp_max=10,
                action_points_current=3,
                action_points_max=3,
                armor_class=12,
                is_active=True,
                is_conscious=True
            )
        ],
        battlefield={"size": "medium", "terrain": "forest"},
        initiative_order=["Fighter", "Goblin"]
    )

    # Test action selection with mock
    print("\n1. Testing action selection for player attack...")
    # Mock AgentRunner.run to return a mock result with final_output
    from gaia.infra.llm.agent_runner import AgentRunner
    mock_result = Mock()
    mock_result.final_output = mock_response

    with patch.object(AgentRunner, 'run', new_callable=AsyncMock, return_value=mock_result):
        result = await agent.select_actions(request)

    print(f"   Result type: {type(result)}")
    print(f"   Actions: {result.actions if hasattr(result, 'actions') else 'No actions'}")
    print(f"   Expected AP usage: {result.expected_ap_usage if hasattr(result, 'expected_ap_usage') else 'Unknown'}")

    # Verify we got a proper response
    assert result is not None, "No result from action selector"
    assert hasattr(result, 'actions'), "Result missing 'actions' attribute"
    assert len(result.actions) > 0, "No actions selected"

    # Check the action has required fields
    first_action = result.actions[0]
    assert hasattr(first_action, 'actor'), "Action missing 'actor'"
    assert hasattr(first_action, 'action_type'), "Action missing 'action_type'"
    assert first_action.actor == "Fighter", f"Wrong actor: {first_action.actor}"

    print("   ✅ Action selection returned valid structure")

    # Test NPC action selection
    print("\n2. Testing NPC action selection...")
    npc_request = CombatActionRequest(
        campaign_id="test",
        combat_id="test_001",
        player_action="",  # Empty for NPC
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=2,
            active_combatant="Goblin",
            available_actions=["basic_attack", "defend", "move", "end_turn"]
        ),
        combatants=request.combatants,
        battlefield={"size": "medium", "terrain": "forest"},
        initiative_order=["Fighter", "Goblin"]
    )

    # Use the same mocking for NPC turn
    with patch.object(AgentRunner, 'run', new_callable=AsyncMock, return_value=mock_result):
        npc_result = await agent.select_actions(npc_request)

    print(f"   NPC Result type: {type(npc_result)}")
    print(f"   NPC Actions: {npc_result.actions if hasattr(npc_result, 'actions') else 'No actions'}")
    print(f"   NPC Expected AP: {npc_result.expected_ap_usage if hasattr(npc_result, 'expected_ap_usage') else 'Unknown'}")

    assert npc_result is not None, "No result for NPC"
    assert hasattr(npc_result, 'actions'), "NPC result missing 'actions'"
    assert len(npc_result.actions) > 0, "No NPC actions selected"

    print("   ✅ NPC action selection returned valid structure")

    return True


def test_combat_mechanical_resolution():
    """Test that action intents are properly post-processed with mechanics resolution.

    Validates that:
    - Action intents are converted to CombatAction objects
    - AP costs are correctly assigned based on action type
    - Combat engine processes actions correctly
    - Context tracks action resolutions
    """
    from gaia_private.agents.combat.combat import Combat
    from gaia_private.models.combat.agent_io.fight import (
        CombatActionRequest,
        CombatantView,
        CurrentTurnInfo
    )
    from gaia.models.combat import CombatSession, CombatantState, CombatStatus
    from gaia.models.combat.mechanics.action_points import ActionPointState
    from gaia.mechanics.combat.combat_engine import CombatEngine
    from unittest.mock import Mock, patch

    # Create a mock combat session with proper combatants
    combat_session = CombatSession(
        session_id="test_combat",
        scene_id="test_scene",
        status=CombatStatus.IN_PROGRESS,
        round_number=1
    )

    # Add combatants to session
    fighter = CombatantState(
        character_id="fighter_001",
        name="Fighter",
        is_npc=False,
        initiative=15,
        hp=20,
        max_hp=20,
        ac=16,
        level=3
    )
    fighter.action_points = ActionPointState(max_ap=3, current_ap=3)
    goblin = CombatantState(
        character_id="goblin_001",
        name="Goblin",
        is_npc=True,
        initiative=12,
        hp=10,
        max_hp=10,
        ac=12,
        level=1
    )
    combat_session.combatants = {
        "fighter_001": fighter,
        "goblin_001": goblin
    }
    combat_session.turn_order = ["fighter_001", "goblin_001"]

    # Create combat agent and context
    combat = Combat()

    # Create test request with name-to-ID mapping
    request = CombatActionRequest(
        campaign_id="test",
        combat_id="test_001",
        player_action="attack",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Fighter",
            available_actions=["basic_attack", "end_turn"]
        ),
        combatants=[
            CombatantView(
                name="Fighter",
                type="player",
                hp_current=20,
                hp_max=20,
                action_points_current=3,
                action_points_max=3,
                armor_class=16,
                is_active=True,
                is_conscious=True
            ),
            CombatantView(
                name="Goblin",
                type="enemy",
                hp_current=10,
                hp_max=10,
                action_points_current=3,
                action_points_max=3,
                armor_class=12,
                is_active=True,
                is_conscious=True
            )
        ],
        battlefield={"size": "medium", "terrain": "plains"},
        initiative_order=["Fighter", "Goblin"]
    )
    # Add name-to-ID mapping
    request.name_to_combatant_id = {
        "Fighter": "fighter_001",
        "Goblin": "goblin_001"
    }

    # Test 1: basic_attack resolution
    action_intents = {
        "actions": [{
            "actor": "Fighter",
            "action_type": "basic_attack",
            "target": "Goblin",
            "intent_description": "attacks goblin"
        }]
    }

    initial_snapshot = combat._capture_initial_state(request)
    run_result = combat._resolve_combat_actions(
        action_intents=action_intents,
        request=request,
        combat_session=combat_session,
        initial_snapshot=initial_snapshot
    )

    assert len(run_result.action_resolutions) > 0, "No actions resolved"
    first_action = run_result.action_resolutions[0]

    # Validate CombatAction structure
    assert hasattr(first_action, 'action_type'), "Missing action_type"
    assert hasattr(first_action, 'ap_cost'), "Missing ap_cost"
    assert hasattr(first_action, 'actor_id'), "Missing actor_id"
    assert hasattr(first_action, 'target_id'), "Missing target_id"

    # Validate mechanics were applied
    assert first_action.ap_cost == 2, f"Wrong AP cost for basic_attack: {first_action.ap_cost}"
    assert first_action.actor_id == "fighter_001", "Wrong actor_id"
    assert first_action.target_id == "goblin_001", "Wrong target_id"

    # Validate result bookkeeping
    updates = run_result.to_combatant_updates()
    assert "goblin_001" in updates or "Goblin" in updates

    # Reset session state for next test path
    combat_session.combatants["goblin_001"].hp = 10
    fighter_ap = combat_session.combatants["fighter_001"].action_points
    if fighter_ap:
        fighter_ap.current_ap = fighter_ap.max_ap

    # Test 2: end_turn action (0 AP cost)
    end_turn_intents = {
        "actions": [{
            "actor": "Fighter",
            "action_type": "end_turn",
            "target": None,
            "intent_description": "ends turn"
        }]
    }

    initial_snapshot = combat._capture_initial_state(request)
    result_end = combat._resolve_combat_actions(
        action_intents=end_turn_intents,
        request=request,
        combat_session=combat_session,
        initial_snapshot=initial_snapshot
    )

    assert len(result_end.action_resolutions) > 0, "No end_turn resolved"
    end_action = result_end.action_resolutions[0]

    # end_turn should cost 0 AP
    assert end_action.ap_cost == 0, f"Wrong AP cost for end_turn: {end_action.ap_cost}"
    assert end_action.action_type == "end_turn"
