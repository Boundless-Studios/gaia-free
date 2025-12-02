"""Unit tests for combat narrative agent turn announcement and player options."""

import pytest
import unittest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from gaia_private.agents.combat.narrator import CombatNarrativeAgent
from gaia_private.models.combat.agent_io.fight import (
    CombatActionRequest,
    CurrentTurnInfo,
    CombatantView
)
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig
from gaia.mechanics.combat.combat_action_results import (
    TurnTransitionResult,
    TurnTransitionReason,
)
from gaia.models.combat.mechanics.combat_action import CombatAction


class TestCombatNarrativeAgentTurnLogic(unittest.IsolatedAsyncioTestCase):
    """Test the combat narrative agent's turn announcement and player options logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.agent = CombatNarrativeAgent()

        # Create common test combatants
        self.player_alice = CombatantView(
            name="Alice",
            type="player",
            hp_current=30,
            hp_max=30,
            armor_class=18,
            action_points_current=4,
            action_points_max=4,
            is_active=True
        )

        self.player_bob = CombatantView(
            name="Bob",
            type="player",
            hp_current=20,
            hp_max=20,
            armor_class=14,
            action_points_current=4,
            action_points_max=4,
            is_active=True
        )

        self.npc_goblin = CombatantView(
            name="Goblin Scout",
            type="enemy",
            hp_current=15,
            hp_max=15,
            armor_class=13,
            action_points_current=4,
            action_points_max=4,
            is_active=True
        )

        # Create common test request
        self.request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="I attack with my sword",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1
            ),
            combatants=[self.player_alice, self.player_bob, self.npc_goblin],
            battlefield=BattlefieldConfig(terrain="forest clearing")
        )

    def test_is_next_turn_player_when_transitioning_to_player(self):
        """Test _is_next_turn_player returns True when transitioning to a player's turn."""
        turn_resolution = TurnTransitionResult(
            current_actor="Goblin Scout",
            next_combatant="Alice",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=0
        )

        result = self.agent._is_next_turn_player(turn_resolution, self.request)
        self.assertTrue(result)

    def test_is_next_turn_player_when_transitioning_to_npc(self):
        """Test _is_next_turn_player returns False when transitioning to an NPC's turn."""
        turn_resolution = TurnTransitionResult(
            current_actor="Alice",
            next_combatant="Goblin Scout",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=2
        )

        result = self.agent._is_next_turn_player(turn_resolution, self.request)
        self.assertFalse(result)

    def test_is_next_turn_player_when_turn_continues(self):
        """Test _is_next_turn_player returns False when turn continues for same combatant."""
        turn_resolution = TurnTransitionResult(
            current_actor="Alice",
            next_combatant="Alice",
            reason=TurnTransitionReason.TURN_CONTINUES,
            new_round=False,
            round_number=1,
            order_index=0
        )

        result = self.agent._is_next_turn_player(turn_resolution, self.request)
        self.assertFalse(result)

    def test_is_next_turn_player_with_no_turn_resolution(self):
        """Test _is_next_turn_player returns False when turn_resolution is None."""
        result = self.agent._is_next_turn_player(None, self.request)
        self.assertFalse(result)

    def test_generate_next_turn_prompt_turn_continues(self):
        """Test _generate_next_turn_prompt when turn continues."""
        turn_resolution = TurnTransitionResult(
            current_actor="Alice",
            next_combatant="Alice",
            reason=TurnTransitionReason.TURN_CONTINUES,
            new_round=False,
            round_number=1,
            order_index=0
        )

        prompt = self.agent._generate_next_turn_prompt(turn_resolution, self.request)
        self.assertEqual(prompt, "You still have actions remaining. What would you like to do?")

    def test_generate_next_turn_prompt_transition_to_player(self):
        """Test _generate_next_turn_prompt when transitioning to a player."""
        turn_resolution = TurnTransitionResult(
            current_actor="Goblin Scout",
            next_combatant="Alice",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=0
        )

        prompt = self.agent._generate_next_turn_prompt(turn_resolution, self.request)
        self.assertEqual(prompt, "It's now Alice's turn. What would you like to do?")

    def test_generate_next_turn_prompt_transition_to_npc(self):
        """Test _generate_next_turn_prompt when transitioning to an NPC."""
        turn_resolution = TurnTransitionResult(
            current_actor="Alice",
            next_combatant="Goblin Scout",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=2
        )

        prompt = self.agent._generate_next_turn_prompt(turn_resolution, self.request)
        self.assertEqual(prompt, "It's Goblin Scout's turn. Are you ready?")

    def test_generate_next_turn_prompt_no_resolution(self):
        """Test _generate_next_turn_prompt with no turn_resolution."""
        prompt = self.agent._generate_next_turn_prompt(None, self.request)
        self.assertEqual(prompt, "What would you like to do?")

    def test_get_player_options_instruction_for_player_turn(self):
        """Test _get_player_options_instruction generates instructions for player turns."""
        turn_resolution = TurnTransitionResult(
            current_actor="Goblin Scout",
            next_combatant="Alice",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=0
        )

        instruction = self.agent._get_player_options_instruction(
            is_next_turn_player=True,
            turn_resolution=turn_resolution,
            request=self.request
        )

        # Should contain player-specific instructions
        self.assertIn("GENERATE PLAYER OPTIONS", instruction)
        self.assertIn("Alice", instruction)
        self.assertIn("4/4", instruction)  # AP
        self.assertIn("Goblin Scout", instruction)  # Enemy
        self.assertIn("forest clearing", instruction)  # Terrain

    def test_get_player_options_instruction_for_npc_turn(self):
        """Test _get_player_options_instruction returns empty instruction for NPC turns."""
        instruction = self.agent._get_player_options_instruction(
            is_next_turn_player=False,
            turn_resolution=None,
            request=self.request
        )

        self.assertEqual(instruction, "Do NOT generate player_options - leave the array empty.")

    def test_get_player_options_instruction_for_continuing_turn(self):
        """Test _get_player_options_instruction returns empty instruction for continuing turns."""
        instruction = self.agent._get_player_options_instruction(
            is_next_turn_player=False,
            turn_resolution=None,
            request=self.request
        )

        self.assertEqual(instruction, "Do NOT generate player_options - leave the array empty.")

    def test_get_player_options_instruction_no_turn_resolution(self):
        """Test _get_player_options_instruction handles None turn_resolution gracefully."""
        instruction = self.agent._get_player_options_instruction(
            is_next_turn_player=True,
            turn_resolution=None,
            request=self.request
        )

        self.assertEqual(instruction, "Do NOT generate player_options - leave the array empty.")

    @pytest.mark.asyncio
    @patch('gaia.infra.llm.agent_runner.AgentRunner.run')
    async def test_generate_narrative_includes_deterministic_turn_prompt(self, mock_run):
        """Test that generate_narrative adds deterministic next_turn_prompt."""
        # Mock LLM response
        mock_output = MagicMock()
        mock_output.model_dump.return_value = {
            "scene_description": "The goblin falls to the ground.",
            "narrative": "Your blade strikes true!",
            "narrative_effects": [],
            "combat_state": "ongoing",
            "player_options": []
        }
        mock_run.return_value = MagicMock(final_output=mock_output)

        turn_resolution = TurnTransitionResult(
            current_actor="Alice",
            next_combatant="Bob",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=1
        )

        resolved_actions = [
            CombatAction(
                timestamp=datetime.now(),
                round_number=1,
                actor_id="pc:alice",
                action_type="basic_attack",
                target_id="npc:goblin_scout",
                ap_cost=2,
                success=True,
                damage_dealt=8
            )
        ]

        result = await self.agent.generate_narrative(
            request=self.request,
            resolved_actions=resolved_actions,
            combatant_updates={},
            turn_resolution=turn_resolution
        )

        # Verify deterministic turn prompt was added
        self.assertIn("next_turn_prompt", result)
        self.assertEqual(result["next_turn_prompt"], "It's now Bob's turn. What would you like to do?")

    @pytest.mark.asyncio
    @patch('gaia.infra.llm.agent_runner.AgentRunner.run')
    async def test_generate_narrative_player_options_for_player_turn(self, mock_run):
        """Test that generate_narrative receives player options from LLM for player turns."""
        # Mock LLM response with player options
        mock_output = MagicMock()
        mock_output.model_dump.return_value = {
            "scene_description": "The goblin staggers back.",
            "narrative": "Your strike lands solidly!",
            "narrative_effects": [],
            "combat_state": "ongoing",
            "player_options": [
                "Strike the goblin again",
                "Feint and then attack",
                "Charge into the goblin",
                "Retreat to cover"
            ]
        }
        mock_run.return_value = MagicMock(final_output=mock_output)

        turn_resolution = TurnTransitionResult(
            current_actor="Goblin Scout",
            next_combatant="Alice",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=0
        )

        resolved_actions = [
            CombatAction(
                timestamp=datetime.now(),
                round_number=1,
                actor_id="npc:goblin_scout",
                action_type="basic_attack",
                target_id="pc:alice",
                ap_cost=2,
                success=False,
                damage_dealt=0
            )
        ]

        result = await self.agent.generate_narrative(
            request=self.request,
            resolved_actions=resolved_actions,
            combatant_updates={},
            turn_resolution=turn_resolution
        )

        # Verify player_options are present
        self.assertIn("player_options", result)
        self.assertEqual(len(result["player_options"]), 4)
        self.assertIn("Strike the goblin again", result["player_options"])

    @pytest.mark.asyncio
    @patch('gaia.infra.llm.agent_runner.AgentRunner.run')
    async def test_generate_narrative_empty_player_options_for_npc_turn(self, mock_run):
        """Test that generate_narrative has empty player_options for NPC turns."""
        # Mock LLM response without player options
        mock_output = MagicMock()
        mock_output.model_dump.return_value = {
            "scene_description": "Alice dodges the goblin's attack.",
            "narrative": "The goblin's blade misses!",
            "narrative_effects": [],
            "combat_state": "ongoing",
            "player_options": []
        }
        mock_run.return_value = MagicMock(final_output=mock_output)

        turn_resolution = TurnTransitionResult(
            current_actor="Alice",
            next_combatant="Goblin Scout",
            reason=TurnTransitionReason.AP_EXHAUSTED,
            new_round=False,
            round_number=1,
            order_index=2
        )

        resolved_actions = [
            CombatAction(
                timestamp=datetime.now(),
                round_number=1,
                actor_id="pc:alice",
                action_type="basic_attack",
                target_id="npc:goblin_scout",
                ap_cost=2,
                success=True,
                damage_dealt=12
            )
        ]

        result = await self.agent.generate_narrative(
            request=self.request,
            resolved_actions=resolved_actions,
            combatant_updates={},
            turn_resolution=turn_resolution
        )

        # Verify player_options is empty
        self.assertIn("player_options", result)
        self.assertEqual(result["player_options"], [])


if __name__ == '__main__':
    unittest.main()
