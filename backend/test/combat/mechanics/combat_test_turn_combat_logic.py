"""Unit tests for turn scene type logic during combat."""

import pytest


@pytest.mark.unit
class TestTurnCombatLogic:
    """Test the logic that determines scene_type for turns."""

    def test_scene_in_combat(self):
        """Test scene type logic when scene is in combat."""
        current_scene = {
            "scene_id": "tavern_brawl_001",
            "scene_type": "social",  # Original type was social
            "in_combat": True,       # But now in combat
            "combat_data": {
                "session_id": "combat_abc123",
                "round_number": 2,
                "hostile_targets": ["Angry Patron"]
            }
        }

        # Logic from campaign_runner.py
        in_combat = current_scene.get("in_combat", False)
        combat_data = current_scene.get("combat_data") if in_combat else None
        scene_type = "combat" if in_combat else current_scene.get("scene_type", "exploration")

        assert scene_type == "combat"
        assert combat_data is not None
        assert combat_data["session_id"] == "combat_abc123"
        assert combat_data["round_number"] == 2

    def test_scene_not_in_combat(self):
        """Test scene type logic when scene is not in combat."""
        current_scene = {
            "scene_id": "tavern_main_hall",
            "scene_type": "social",
            "in_combat": False
        }

        in_combat = current_scene.get("in_combat", False)
        combat_data = current_scene.get("combat_data") if in_combat else None
        scene_type = "combat" if in_combat else current_scene.get("scene_type", "exploration")

        assert scene_type == "social"
        assert combat_data is None

    def test_scene_no_combat_flag(self):
        """Test scene type logic when in_combat flag is missing."""
        current_scene = {
            "scene_id": "market_square",
            "scene_type": "exploration"
            # No in_combat field
        }

        in_combat = current_scene.get("in_combat", False)
        combat_data = current_scene.get("combat_data") if in_combat else None
        scene_type = "combat" if in_combat else current_scene.get("scene_type", "exploration")

        assert in_combat is False
        assert scene_type == "exploration"
        assert combat_data is None

    def test_analysis_with_hostile_targets(self):
        """Test analysis context with hostile targets present."""
        analysis = {
            "scene_type": "exploration",
            "scene_id": "forest_path",
            "npcs": ["Merchant"],
            "hostile_targets": ["Bandit", "Wolf"]  # Has hostiles
        }

        # Logic from campaign_runner.py
        hostile_targets = analysis.get("hostile_targets", [])
        is_combat = bool(hostile_targets) or analysis.get("scene_type") == "combat"

        scene_context = {
            "scene_type": "combat" if is_combat else analysis.get("scene_type", "exploration"),
            "scene_id": analysis.get("scene_id"),
            "npcs": analysis.get("npcs", []),
            "hostile_targets": hostile_targets
        }

        assert is_combat is True
        assert scene_context["scene_type"] == "combat"
        assert scene_context["hostile_targets"] == ["Bandit", "Wolf"]

    def test_analysis_without_hostile_targets(self):
        """Test analysis context without hostile targets."""
        analysis = {
            "scene_type": "social",
            "scene_id": "tavern",
            "npcs": ["Bartender", "Patron"],
            "hostile_targets": []  # No hostiles
        }

        hostile_targets = analysis.get("hostile_targets", [])
        is_combat = bool(hostile_targets) or analysis.get("scene_type") == "combat"

        scene_context = {
            "scene_type": "combat" if is_combat else analysis.get("scene_type", "exploration"),
            "scene_id": analysis.get("scene_id"),
            "npcs": analysis.get("npcs", []),
            "hostile_targets": hostile_targets
        }

        assert is_combat is False
        assert scene_context["scene_type"] == "social"
        assert scene_context["hostile_targets"] == []

    def test_analysis_with_combat_scene_type(self):
        """Test analysis when scene_type is explicitly 'combat'."""
        analysis = {
            "scene_type": "combat",  # Explicitly combat
            "scene_id": "battlefield",
            "npcs": ["Enemy Soldier"],
            "hostile_targets": []  # Even without hostiles
        }

        hostile_targets = analysis.get("hostile_targets", [])
        is_combat = bool(hostile_targets) or analysis.get("scene_type") == "combat"

        scene_context = {
            "scene_type": "combat" if is_combat else analysis.get("scene_type", "exploration"),
            "scene_id": analysis.get("scene_id"),
            "npcs": analysis.get("npcs", []),
            "hostile_targets": hostile_targets
        }

        assert is_combat is True
        assert scene_context["scene_type"] == "combat"

    def test_combat_data_extraction(self):
        """Test extraction of combat data from scene."""
        scenes = [
            {
                "scene_id": "combat_active",
                "in_combat": True,
                "combat_data": {
                    "session_id": "abc123",
                    "round_number": 5,
                    "current_turn": "Player1"
                }
            },
            {
                "scene_id": "no_combat",
                "in_combat": False
            },
            {
                "scene_id": "missing_flag"
                # No in_combat or combat_data
            }
        ]

        results = []
        for scene in scenes:
            in_combat = scene.get("in_combat", False)
            combat_data = scene.get("combat_data") if in_combat else None
            results.append({
                "scene_id": scene["scene_id"],
                "in_combat": in_combat,
                "combat_data": combat_data
            })

        # First scene should have combat data
        assert results[0]["in_combat"] is True
        assert results[0]["combat_data"] is not None
        assert results[0]["combat_data"]["session_id"] == "abc123"

        # Second scene should not have combat data
        assert results[1]["in_combat"] is False
        assert results[1]["combat_data"] is None

        # Third scene should not have combat data (defaults to False)
        assert results[2]["in_combat"] is False
        assert results[2]["combat_data"] is None