"""Unit test for double attack scenario in combat."""

import asyncio
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gaia_private.agents.combat.action_selector import CombatActionSelectionAgent
from gaia_private.agents.combat.models import CombatActionIntent, CombatActionSelectionOutput
from gaia_private.models.combat.agent_io.fight.combat_action_request import CombatActionRequest
from gaia_private.models.combat.agent_io.fight.combatant_view import CombatantView
from gaia_private.models.combat.agent_io.fight.current_turn_info import CurrentTurnInfo as CurrentTurn
from gaia_private.models.combat.agent_io.initiation.battlefield_config import BattlefieldConfig as Battlefield


class TestDoubleAttack:
    """Test cases for double attack functionality."""

    @pytest.mark.asyncio
    async def test_double_attack_generates_two_actions(self):
        """Test that 'I attack twice' generates two separate attack actions."""

        # Create mock combatants
        thorin = CombatantView(
            name="Thorin",
            type="player",
            hp_current=44,
            hp_max=44,
            armor_class=18,
            action_points_current=4,
            action_points_max=4,
            is_active=True,
            is_conscious=True
        )

        goblin = CombatantView(
            name="Goblin Scout",
            type="npc",
            hp_current=10,
            hp_max=10,
            armor_class=15,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        )

        # Create combat request
        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_session",
            combat_session_id="test_session",
            player_action="I attack twice with my sword!",
            combatants=[thorin, goblin],
            current_turn=CurrentTurn(
                round_number=1,
                turn_number=1,
                active_combatant="Thorin"
            ),
            battlefield=Battlefield(
                size="medium",
                terrain="forest"
            ),
            combat_narrative=None  # Optional field
        )

        # Create action selector
        selector = CombatActionSelectionAgent()

        # Mock the AgentRunner to return a double attack response
        mock_result = Mock()
        mock_result.final_output = CombatActionSelectionOutput(
            actions=[
                CombatActionIntent(
                    actor="Thorin",
                    action_type="basic_attack",
                    target="Goblin Scout",
                    intent_description="first strike with sword"
                ),
                CombatActionIntent(
                    actor="Thorin",
                    action_type="basic_attack",
                    target="Goblin Scout",
                    intent_description="second strike with sword"
                )
            ],
            tactical_reasoning="Two attacks to maximize damage output",
            expected_ap_usage=4
        )

        with patch('gaia_private.agents.combat.action_selector.AgentRunner.run',
                   return_value=mock_result):
            # Run action selection
            result = await selector.select_actions(request)

        # Verify we got two attack actions
        assert len(result.actions) == 2, "Should generate two attack actions"

        # Verify both are basic attacks
        for action in result.actions:
            assert action.action_type == "basic_attack", "Each action should be basic_attack"
            assert action.actor == "Thorin", "Actor should be Thorin"
            assert action.target == "Goblin Scout", "Target should be Goblin Scout"

        # Verify AP usage
        assert result.expected_ap_usage == 4, "Two attacks should use 4 AP"

    @pytest.mark.asyncio
    async def test_single_attack_generates_one_action(self):
        """Test that 'I attack' generates only one attack action."""

        # Create mock combatants
        thorin = CombatantView(
            name="Thorin",
            type="player",
            hp_current=44,
            hp_max=44,
            armor_class=18,
            action_points_current=4,
            action_points_max=4,
            is_active=True,
            is_conscious=True
        )

        goblin = CombatantView(
            name="Goblin Scout",
            type="npc",
            hp_current=10,
            hp_max=10,
            armor_class=15,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        )

        # Create combat request
        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_session",
            combat_session_id="test_session",
            player_action="I attack the goblin",
            combatants=[thorin, goblin],
            current_turn=CurrentTurn(
                round_number=1,
                turn_number=1,
                active_combatant="Thorin"
            ),
            battlefield=Battlefield(
                size="medium",
                terrain="forest"
            ),
            combat_narrative=None  # Optional field
        )

        # Create action selector
        selector = CombatActionSelectionAgent()

        # Mock the AgentRunner to return a single attack response
        mock_result = Mock()
        mock_result.final_output = CombatActionSelectionOutput(
            actions=[
                CombatActionIntent(
                    actor="Thorin",
                    action_type="basic_attack",
                    target="Goblin Scout",
                    intent_description="strikes with sword"
                )
            ],
            tactical_reasoning="Single focused attack",
            expected_ap_usage=2
        )

        with patch('gaia_private.agents.combat.action_selector.AgentRunner.run',
                   return_value=mock_result):
            # Run action selection
            result = await selector.select_actions(request)

        # Verify we got only one attack action
        assert len(result.actions) == 1, "Should generate only one attack action"

        # Verify it's a basic attack
        assert result.actions[0].action_type == "basic_attack", "Action should be basic_attack"

        # Verify AP usage
        assert result.expected_ap_usage == 2, "Single attack should use 2 AP"

    @pytest.mark.asyncio
    async def test_prompt_includes_double_attack_instruction(self):
        """Test that the prompt properly includes double attack instructions."""

        selector = CombatActionSelectionAgent()
        prompt = await selector._get_system_prompt()

        # Verify the prompt includes multiple attack handling
        assert "Multiple Attack Handling" in prompt, "Prompt should include Multiple Attack Handling section"
        assert "attack twice" in prompt.lower(), "Prompt should mention 'attack twice'"
        assert "TWO separate" in prompt or "two separate" in prompt.lower(), "Prompt should mention generating two separate actions"
        assert "SEPARATE action" in prompt or "separate action" in prompt.lower(), "Prompt should emphasize separate actions"


if __name__ == "__main__":
    # Run the tests
    asyncio.run(test_double_attack_generates_two_actions())
    asyncio.run(test_single_attack_generates_one_action())
    asyncio.run(test_prompt_includes_double_attack_instruction())
    print("✅ All double attack tests passed!")