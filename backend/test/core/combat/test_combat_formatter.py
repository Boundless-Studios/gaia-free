"""Unit tests for CombatFormatter.format_combat_response()."""

import pytest
from datetime import datetime
from gaia.mechanics.combat.combat_formatter import CombatFormatter
from gaia_private.models.combat.agent_io.fight import (
    AgentCombatResponse,
    AgentCharacterStatus,
    CombatActionRequest,
    CombatantView,
    CurrentTurnInfo
)
from gaia_private.models.combat.agent_io.initiation import (
    BattlefieldConfig,
    CombatInitiation,
    CombatNarrative,
    InitiativeEntry,
)
from gaia.mechanics.combat.combat_action_results import (
    TurnTransitionResult,
    TurnTransitionReason
)


@pytest.fixture
def player_alice():
    """Create test player combatant."""
    return CombatantView(
        name="Alice",
        type="player",
        hp_current=30,
        hp_max=30,
        armor_class=18,
        action_points_current=4,
        action_points_max=4,
        is_active=True,
        is_conscious=True
    )


@pytest.fixture
def enemy_goblin():
    """Create test enemy combatant."""
    return CombatantView(
        name="Goblin Scout",
        type="enemy",
        hp_current=15,
        hp_max=15,
        armor_class=13,
        action_points_current=4,
        action_points_max=4,
        is_active=True,
        is_conscious=True
    )


class TestCombatFormatterResponse:
    """Test format_combat_response method."""

    def test_combat_status_structured_dict(self, player_alice, enemy_goblin):
        """Test that combat_status is sent as structured dict, not text."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="I attack the goblin",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1,
                available_actions=[]
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="forest")
        )

        combat_response = AgentCombatResponse(
            scene_description="Alice's sword strikes true.",
            narrative="The goblin staggers back.",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="3/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="8/15", ap="4/4", status=["wounded"])
            },
            combat_state="ongoing",
            next_turn_prompt="What would you like to do?"
        )

        result = formatter.format_combat_response(combat_response, request)

        # Verify combat_status is in structured_data as dict
        assert "combat_status" in result["structured_data"]
        assert isinstance(result["structured_data"]["combat_status"], dict)

        # Verify each combatant has structured status
        assert "Alice" in result["structured_data"]["combat_status"]
        assert "Goblin Scout" in result["structured_data"]["combat_status"]

        alice_status = result["structured_data"]["combat_status"]["Alice"]
        assert alice_status["hp"] == "30/30"
        assert alice_status["ap"] == "3/4"
        assert alice_status["status"] == []

        goblin_status = result["structured_data"]["combat_status"]["Goblin Scout"]
        assert goblin_status["hp"] == "8/15"
        assert goblin_status["ap"] == "4/4"
        assert goblin_status["status"] == ["wounded"]

    def test_narrative_excludes_combat_status(self, player_alice, enemy_goblin):
        """Test that narrative field does not contain combat status text."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="I attack the goblin",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1,
                available_actions=[]
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="forest")
        )

        combat_response = AgentCombatResponse(
            scene_description="The forest clearing dims.",
            narrative="The goblin staggers back, wounded.",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="3/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="8/15", ap="4/4", status=["wounded"])
            },
            combat_state="ongoing"
        )

        result = formatter.format_combat_response(combat_response, request)

        # Verify narrative exists and doesn't contain "Status:" text
        assert "narrative" in result["structured_data"]
        narrative = result["structured_data"]["narrative"]
        assert "Status:" not in narrative
        assert "HP=" not in narrative
        assert "AP=" not in narrative

        # Verify narrative contains only scene description and action narrative
        assert "The forest clearing dims." in narrative
        assert "The goblin staggers back, wounded." in narrative

    def test_available_actions_from_request(self, player_alice, enemy_goblin):
        """Test that available_actions comes from request.current_turn, not undefined variable."""
        formatter = CombatFormatter()

        # Create request with available_actions
        available_actions = ["Attack", "Dodge", "Dash"]
        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="I attack the goblin",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1,
                available_actions=available_actions
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="forest")
        )

        # Create minimal combat response
        combat_response = AgentCombatResponse(
            scene_description="Alice's sword strikes true.",
            narrative="The goblin staggers back.",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="3/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="8/15", ap="4/4", status=["wounded"])
            },
            combat_state="ongoing",
            next_turn_prompt="What would you like to do?"
        )

        # Format the response
        result = formatter.format_combat_response(combat_response, request)

        # Verify available_actions comes from request, not undefined variable
        assert "turn_info" in result["structured_data"]
        assert "available_actions" in result["structured_data"]["turn_info"]
        assert result["structured_data"]["turn_info"]["available_actions"] == available_actions

    def test_answer_structure_with_all_parts(self, player_alice, enemy_goblin):
        """Test answer includes scene_description + narrative + next_turn_prompt."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="I strike at the goblin",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="arena")
        )

        # Response with all parts
        combat_response = AgentCombatResponse(
            scene_description="Alice's blade flashes in a silver arc, steel meeting flesh with a wet thud.",
            narrative="The goblin reels backward, dark blood welling from the wound.",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="2/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="6/15", ap="4/4", status=["wounded"])
            },
            combat_state="ongoing",
            next_turn_prompt="It's now Bob's turn. What would you like to do?"
        )

        result = formatter.format_combat_response(combat_response, request)
        answer = result["structured_data"]["answer"]

        # All three parts should be present and in order
        assert "Alice's blade flashes in a silver arc" in answer  # scene_description first
        assert "The goblin reels backward" in answer  # narrative second
        assert "It's now Bob's turn" in answer  # next_turn_prompt third

        # Verify order
        scene_pos = answer.index("Alice's blade flashes")
        narrative_pos = answer.index("The goblin reels")
        prompt_pos = answer.index("It's now Bob's turn")
        assert scene_pos < narrative_pos < prompt_pos

    def test_answer_structure_with_missing_parts(self, player_alice, enemy_goblin):
        """Test answer handles missing scene_description or narrative gracefully."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="dodge",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="arena")
        )

        # Response with only scene_description (no narrative or next_turn_prompt)
        combat_response = AgentCombatResponse(
            scene_description="Alice dodges to the side.",
            narrative="",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="3/4", status=[])
            },
            combat_state="ongoing"
        )

        result = formatter.format_combat_response(combat_response, request)
        answer = result["structured_data"]["answer"]

        # Should just have the scene_description
        assert answer == "Alice dodges to the side."

    def test_answer_fallback_when_all_parts_missing(self, player_alice, enemy_goblin):
        """Test answer has fallback when all parts are empty."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="wait",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="arena")
        )

        # Response with all empty strings
        combat_response = AgentCombatResponse(
            scene_description="",
            narrative="",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="4/4", status=[])
            },
            combat_state="ongoing"
        )

        result = formatter.format_combat_response(combat_response, request)
        answer = result["structured_data"]["answer"]

        # Should have fallback
        assert answer == "Alice acts."

    def test_turn_field_uses_player_options(self, player_alice, enemy_goblin):
        """Test turn field uses player_options when available."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="attack",
            current_turn=CurrentTurnInfo(
                active_combatant="Goblin Scout",
                round_number=1,
                turn_number=1
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="forest")
        )

        # Response with player_options (for next player turn)
        player_options = [
            "Strike the goblin with your sword",
            "Feint toward the goblin then strike",
            "Charge at the goblin",
            "Retreat behind cover"
        ]
        combat_response = AgentCombatResponse(
            scene_description="The goblin's attack misses.",
            narrative="Alice dodges the wild swing.",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="4/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="15/15", ap="0/4", status=[])
            },
            combat_state="ongoing",
            player_options=player_options,
            next_turn_prompt="It's now Alice's turn. What would you like to do?"
        )

        result = formatter.format_combat_response(combat_response, request)
        turn = result["structured_data"]["turn"]

        # Turn should be the player_options array
        assert turn == player_options

    def test_turn_field_fallback_to_next_turn_prompt(self, player_alice, enemy_goblin):
        """Test turn field uses next_turn_prompt when player_options is empty."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="attack",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="forest")
        )

        # Response without player_options (NPC turn next)
        combat_response = AgentCombatResponse(
            scene_description="Alice strikes the goblin.",
            narrative="The blade finds its mark.",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="0/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="8/15", ap="4/4", status=["wounded"])
            },
            combat_state="ongoing",
            player_options=[],
            next_turn_prompt="It's Goblin Scout's turn. Are you ready?"
        )

        result = formatter.format_combat_response(combat_response, request)
        turn = result["structured_data"]["turn"]

        # Turn should be the next_turn_prompt string
        assert turn == "It's Goblin Scout's turn. Are you ready?"

    def test_turn_field_ultimate_fallback(self, player_alice, enemy_goblin):
        """Test turn field has ultimate fallback when both player_options and next_turn_prompt are missing."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="wait",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="arena")
        )

        # Response with no player_options and no next_turn_prompt
        combat_response = AgentCombatResponse(
            scene_description="Alice waits.",
            narrative="",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="4/4", status=[])
            },
            combat_state="ongoing",
            player_options=[]
        )

        result = formatter.format_combat_response(combat_response, request)
        turn = result["structured_data"]["turn"]

        # Should have ultimate fallback
        assert turn == "It is Alice's turn."

    def test_available_actions_empty_list_when_none(self, player_alice, enemy_goblin):
        """Test available_actions defaults to empty list when None in request."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="attack",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=1,
                turn_number=1,
                available_actions=None  # Explicitly None
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="forest")
        )

        combat_response = AgentCombatResponse(
            scene_description="Combat continues.",
            narrative="",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="4/4", status=[])
            },
            combat_state="ongoing"
        )

        result = formatter.format_combat_response(combat_response, request)

        # Should default to empty list
        assert result["structured_data"]["turn_info"]["available_actions"] == []

    def test_formatter_uses_run_result_when_session_missing(self, player_alice, enemy_goblin):
        """Ensure formatter derives status from run_result when session data is unavailable."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="combat-42",
            player_action="Alice attacks",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=2,
                turn_number=1,
                available_actions=[]
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="dungeon"),
            name_to_combatant_id={"Alice": "pc:alice", "Goblin Scout": "npc:goblin"}
        )

        class DummyRunResult:
            def __init__(self):
                self.hp = {
                    "pc:alice": {"current": 18, "max": 30},
                    "npc:goblin": {"current": 0, "max": 15},
                    "Alice": {"current": 18, "max": 30},
                    "Goblin Scout": {"current": 0, "max": 15}
                }
                self.ap = {
                    "pc:alice": {"current": 2, "max": 4},
                    "npc:goblin": {"current": 0, "max": 4},
                    "Alice": {"current": 2, "max": 4},
                    "Goblin Scout": {"current": 0, "max": 4}
                }
                self.status_end = {
                    "pc:alice": ["focused"],
                    "npc:goblin": ["defeated"],
                    "Alice": ["focused"],
                    "Goblin Scout": ["defeated"]
                }

            def get_authoritative_hp(self, key):
                return self.hp.get(key)

            def get_authoritative_ap(self, key):
                return self.ap.get(key)

        run_result = DummyRunResult()

        combat_response = AgentCombatResponse(
            scene_description="",
            narrative="",
            combat_state="ongoing",
            next_turn_prompt="",
            combat_status={},  # Force formatter to rely on run_result mapping
            run_result=run_result
        )

        result = formatter.format_combat_response(combat_response, request)
        status = result["structured_data"]["combat_status"]

        assert status["Alice"]["hp"] == "18/30"
        assert status["Alice"]["ap"] == "2/4"
        assert status["Alice"]["status"] == ["focused"]

        assert status["Goblin Scout"]["hp"] == "0/15"
        assert status["Goblin Scout"]["ap"] == "0/4"
        assert status["Goblin Scout"]["status"] == ["defeated"]

    def test_turn_info_includes_round_and_turn_numbers(self, player_alice, enemy_goblin):
        """Ensure turn_info and combat_state include round/turn metadata."""
        formatter = CombatFormatter()

        request = CombatActionRequest(
            campaign_id="test_campaign",
            combat_id="test_combat",
            player_action="Strike true",
            current_turn=CurrentTurnInfo(
                active_combatant="Alice",
                round_number=2,
                turn_number=3,
                available_actions=["attack", "dodge"]
            ),
            combatants=[player_alice, enemy_goblin],
            battlefield=BattlefieldConfig(terrain="crypt"),
            initiative_order=["Alice", "Goblin Scout"],
            name_to_combatant_id={"Alice": "pc:alice"}
        )

        combat_response = AgentCombatResponse(
            scene_description="",
            narrative="",
            combat_state="ongoing",
            next_turn_prompt="",
            combat_status={
                "Alice": AgentCharacterStatus(hp="30/30", ap="3/4", status=[]),
                "Goblin Scout": AgentCharacterStatus(hp="12/15", ap="4/4", status=[])
            }
        )

        result = formatter.format_combat_response(combat_response, request)
        turn_info = result["structured_data"]["turn_info"]
        combat_state = result["structured_data"]["combat_state"]

        assert turn_info["round_number"] == 2
        assert turn_info["turn_number"] == 3
        assert turn_info["initiative_order"] == ["Alice", "Goblin Scout"]
        assert turn_info["turn_id"] == "pc:alice-r2-t3"
        assert turn_info["is_combat"] is True
        assert combat_state["state"] == "ongoing"
        assert combat_state["round_number"] == 2
        assert combat_state["turn_number"] == 3
        assert combat_state["initiative_order"] == ["Alice", "Goblin Scout"]
        assert combat_state["is_active"] is True


class TestCombatFormatterSceneResponse:
    """Tests for combat initiation formatting."""

    def test_scene_initiation_includes_turn_info_and_state(self):
        """Combat initiation should expose combat status metadata."""
        formatter = CombatFormatter()

        combat_init = CombatInitiation(
            scene_id="scene_1",
            campaign_id="campaign_1",
            narrative=CombatNarrative(
                scene_description="The arena doors slam open.",
                combat_trigger="The crowd roars, demanding blood!",
                enemy_description="Two goblins sneer from the opposite gate."
            ),
            battlefield=BattlefieldConfig(terrain="arena"),
            initiative_order=[
                InitiativeEntry(name="Thorin", initiative=18, is_player=True, is_surprised=False),
                InitiativeEntry(name="Goblin Raider", initiative=12, is_player=False, is_surprised=False),
            ]
        )

        formatted = formatter.format_scene_response(
            agent_response=combat_init,
            interaction_type="combat_initiation"
        )
        structured = formatted["structured_data"]

        combat_status = structured["combat_status"]
        assert combat_status["Thorin"]["hostile"] is False
        assert combat_status["Goblin Raider"]["hostile"] is True

        turn_info = structured["turn_info"]
        assert turn_info is not None
        assert turn_info["phase"] == "combat_initiation"
        assert turn_info["turn_number"] == 1
        assert turn_info["round_number"] == 1
        assert turn_info["initiative_order"] == ["Thorin", "Goblin Raider"]
        assert turn_info["is_combat"] is True

        combat_state = structured["combat_state"]
        assert combat_state is not None
        assert combat_state["phase"] == "combat_initiation"
        assert combat_state["state"] == "ongoing"
        assert combat_state["round_number"] == 1
        assert combat_state["turn_number"] == 1
        assert combat_state["initiative_order"] == ["Thorin", "Goblin Raider"]
        assert combat_state["is_active"] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
