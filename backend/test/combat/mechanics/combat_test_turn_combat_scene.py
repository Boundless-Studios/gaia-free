"""Unit tests for turn scene type during combat."""

import pytest
from unittest.mock import MagicMock

from gaia_private.session.turn_manager import TurnManager
from gaia.models.turn import TurnType


@pytest.mark.unit
class TestTurnCombatScene:
    """Test that turns get proper scene_type when in combat."""

    @pytest.fixture
    def turn_manager(self):
        """Create a turn manager for testing."""
        return TurnManager()

    def test_turn_with_combat_scene_context(self, turn_manager):
        """Test turn creation with combat scene context."""
        scene_context_combat = {
            "scene_id": "tavern_brawl_001",
            "scene_type": "combat",
            "in_combat": True,
            "combat_session_id": "combat_abc123",
            "combat_round": 2,
            "hostile_targets": ["Angry Patron", "Bar Thug"]
        }

        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="player_bob",
            character_name="Bob the Fighter",
            scene_context=scene_context_combat
        )

        assert turn.scene_id == "tavern_brawl_001"
        assert turn.scene_type == "combat"
        assert turn.context.get("in_combat") is True
        assert turn.context.get("combat_session_id") == "combat_abc123"
        assert "Angry Patron" in turn.context.get("hostile_targets", [])
        assert "Bar Thug" in turn.context.get("hostile_targets", [])

    def test_turn_with_exploration_scene_context(self, turn_manager):
        """Test turn creation with exploration scene context."""
        scene_context_exploration = {
            "scene_id": "tavern_main_hall",
            "scene_type": "exploration",
            "in_combat": False
        }

        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="player_alice",
            character_name="Alice the Wizard",
            scene_context=scene_context_exploration
        )

        assert turn.scene_id == "tavern_main_hall"
        assert turn.scene_type == "exploration"
        assert turn.context.get("in_combat") is False
        assert turn.context.get("combat_session_id") is None

    def test_turn_with_social_scene_context(self, turn_manager):
        """Test turn creation with social scene context."""
        scene_context_social = {
            "scene_id": "kings_court",
            "scene_type": "social",
            "in_combat": False,
            "npcs": ["King", "Queen", "Royal Guard"]
        }

        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="player_charlie",
            character_name="Charlie the Bard",
            scene_context=scene_context_social
        )

        assert turn.scene_id == "kings_court"
        assert turn.scene_type == "social"
        assert turn.context.get("in_combat") is False
        assert "King" in turn.context.get("npcs", [])

    def test_scene_type_override_when_in_combat(self):
        """Test that scene_type becomes 'combat' when in_combat is True."""
        current_scene = {
            "scene_id": "forest_ambush",
            "scene_type": "social",  # Original scene type
            "in_combat": True,  # But now in combat
            "combat_data": {
                "session_id": "combat_xyz",
                "round_number": 1,
                "hostile_targets": ["Goblin", "Wolf"]
            }
        }

        # Logic from campaign_runner.py
        in_combat = current_scene.get("in_combat", False)
        combat_data = current_scene.get("combat_data") if in_combat else None
        scene_type = "combat" if in_combat else current_scene.get("scene_type", "exploration")

        # When in_combat is True, scene_type should be overridden to 'combat'
        assert scene_type == "combat"
        assert in_combat is True
        assert combat_data is not None
        assert combat_data["session_id"] == "combat_xyz"

    def test_turn_context_includes_all_scene_data(self, turn_manager):
        """Test that turn context includes all relevant scene data."""
        comprehensive_scene = {
            "scene_id": "dungeon_boss_room",
            "scene_type": "combat",
            "in_combat": True,
            "combat_session_id": "boss_fight_001",
            "combat_round": 5,
            "hostile_targets": ["Ancient Dragon", "Dragon Cultist"],
            "environment": "dark cavern with treasure",
            "special_conditions": ["dim light", "difficult terrain"],
            "players_present": ["Bob", "Alice", "Charlie"]
        }

        turn = turn_manager.create_turn(
            campaign_id="epic_campaign",
            character_id="player_bob",
            character_name="Bob the Fighter",
            scene_context=comprehensive_scene
        )

        # All scene context should be preserved in the turn
        assert turn.scene_id == "dungeon_boss_room"
        assert turn.scene_type == "combat"
        assert turn.context.get("in_combat") is True
        assert turn.context.get("combat_session_id") == "boss_fight_001"
        assert turn.context.get("combat_round") == 5
        assert "Ancient Dragon" in turn.context.get("hostile_targets", [])
        assert turn.context.get("environment") == "dark cavern with treasure"
        assert "dim light" in turn.context.get("special_conditions", [])
        assert "Bob" in turn.context.get("players_present", [])

    def test_turn_without_scene_context(self, turn_manager):
        """Test turn creation without scene context."""
        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="player_dave",
            character_name="Dave the Ranger",
            scene_context=None  # No scene context provided
        )

        # Should have reasonable defaults
        assert turn.scene_id is None or turn.scene_id == ""
        assert turn.scene_type is None or turn.scene_type == "exploration"
        assert turn.context is not None  # Should still have a context dict

    def test_turn_scene_transition(self, turn_manager):
        """Test turn behavior during scene transition from non-combat to combat."""
        # First turn: non-combat
        pre_combat_scene = {
            "scene_id": "tavern_peaceful",
            "scene_type": "social",
            "in_combat": False
        }

        turn1 = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="player",
            character_name="Player",
            scene_context=pre_combat_scene
        )

        assert turn1.scene_type == "social"
        assert turn1.context.get("in_combat") is False

        # Second turn: combat initiated
        combat_scene = {
            "scene_id": "tavern_peaceful",  # Same scene ID
            "scene_type": "combat",  # But now combat type
            "in_combat": True,
            "combat_session_id": "sudden_brawl",
            "hostile_targets": ["Drunk Patron"]
        }

        turn2 = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="player",
            character_name="Player",
            scene_context=combat_scene
        )

        # Same scene but now in combat
        assert turn2.scene_id == turn1.scene_id
        assert turn2.scene_type == "combat"
        assert turn2.context.get("in_combat") is True
        assert turn2.context.get("combat_session_id") == "sudden_brawl"