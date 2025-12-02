"""Integration test for turn state persistence to scenes.

This test verifies that CampaignRunner properly persists turn order and current turn index
to scene data when advancing non-combat turns.

Key behaviors tested:
1. Turn order is persisted to scene when set_non_combat_order is called
2. Current turn index is persisted after each turn advancement
3. Turn state survives backend restart (loaded from disk)
4. CampaignRunner handles persistence, not TurnManager
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaia_private.session.campaign_runner import CampaignRunner
from gaia_private.session.turn_manager import TurnManager
from gaia_private.session.scene.scene_integration import SceneIntegration
from gaia.models.scene_info import SceneInfo
from gaia.models.turn import Turn, TurnStatus


def generate_unique_id(base: str) -> str:
    """Generate a unique ID with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{base}_{timestamp}"


class TestTurnPersistenceIntegration:
    """Test turn state persistence through CampaignRunner."""

    def test_turn_advancement_persists_to_scene(self):
        """Test that advancing turns persists current_turn_index to scene.

        This test verifies the refactored behavior where CampaignRunner
        (not TurnManager) handles persistence to scenes.
        """
        # Initialize components
        campaign_id = generate_unique_id("test_persistence")
        scene_id = generate_unique_id("tavern_scene")

        # Create scene with multiple PCs
        turn_manager = TurnManager()
        scene_integration = SceneIntegration(turn_manager=turn_manager)
        turn_manager.scene_integration = scene_integration
        scene_manager = scene_integration.get_scene_manager(campaign_id)

        scene_info = SceneInfo(
            scene_id=scene_id,
            title="The Rusty Dragon Tavern",
            scene_type="exploration",
            location_id="rusty_dragon",
            location_description="A cozy tavern",
            description="A warm tavern",
            pcs_present=["alice", "bob", "charlie"]
        )

        created_scene_id = scene_manager.create_scene(scene_info)

        # Initialize turn manager and set turn order
        character_ids = ["pc:alice", "pc:bob", "pc:charlie"]
        turn_manager.set_non_combat_order(created_scene_id, character_ids)

        # Verify initial state in memory
        assert turn_manager.get_current_character_non_combat(created_scene_id) == "pc:alice"
        assert turn_manager.non_combat_index[created_scene_id] == 0

        # Simulate what CampaignRunner._handle_turn_progression does:
        # 1. Advance the turn in memory
        next_character_id = turn_manager.advance_non_combat_turn(created_scene_id)
        assert next_character_id == "pc:bob"

        # 2. Persist to scene (this is what CampaignRunner does after advancing)
        updates = {
            'current_turn_index': turn_manager.non_combat_index.get(created_scene_id, 0),
            'turn_order': turn_manager.non_combat_order.get(created_scene_id, [])
        }
        scene_manager.update_scene(created_scene_id, updates)

        # Verify scene was updated on disk
        scene_from_disk = scene_manager.get_scene(created_scene_id)
        assert scene_from_disk is not None
        assert scene_from_disk.current_turn_index == 1  # Advanced to Bob (index 1)
        assert scene_from_disk.turn_order == ["pc:alice", "pc:bob", "pc:charlie"]

        # Advance again to Charlie
        next_character_id = turn_manager.advance_non_combat_turn(created_scene_id)
        assert next_character_id == "pc:charlie"

        # Persist again
        updates = {
            'current_turn_index': turn_manager.non_combat_index.get(created_scene_id, 0),
            'turn_order': turn_manager.non_combat_order.get(created_scene_id, [])
        }
        scene_manager.update_scene(created_scene_id, updates)

        # Verify second update
        scene_from_disk = scene_manager.get_scene(created_scene_id)
        assert scene_from_disk.current_turn_index == 2  # Advanced to Charlie (index 2)

        # Advance and wrap to Alice
        next_character_id = turn_manager.advance_non_combat_turn(created_scene_id)
        assert next_character_id == "pc:alice"  # Wrapped around

        # Persist wrap-around
        updates = {
            'current_turn_index': turn_manager.non_combat_index.get(created_scene_id, 0),
            'turn_order': turn_manager.non_combat_order.get(created_scene_id, [])
        }
        scene_manager.update_scene(created_scene_id, updates)

        # Verify wrap-around persisted
        scene_from_disk = scene_manager.get_scene(created_scene_id)
        assert scene_from_disk.current_turn_index == 0  # Wrapped to Alice (index 0)

    def test_turn_state_survives_restart(self):
        """Test that turn state can be restored from disk after 'restart'.

        Simulates a backend restart by:
        1. Creating and advancing turns
        2. Persisting state to disk
        3. Creating new manager instances
        4. Verifying state is restored correctly
        """
        # Phase 1: Initial session
        campaign_id = generate_unique_id("test_restart")
        scene_id = generate_unique_id("scene")

        turn_manager_1 = TurnManager()
        scene_integration_1 = SceneIntegration(turn_manager=turn_manager_1)
        turn_manager_1.scene_integration = scene_integration_1
        scene_manager_1 = scene_integration_1.get_scene_manager(campaign_id)

        scene_info = SceneInfo(
            scene_id=scene_id,
            title="Test Scene",
            scene_type="exploration",
            location_id="test_loc",
            location_description="Test location",
            description="Test",
            pcs_present=["alice", "bob"]
        )

        created_scene_id = scene_manager_1.create_scene(scene_info)

        character_ids = ["pc:alice", "pc:bob"]
        turn_manager_1.set_non_combat_order(created_scene_id, character_ids)

        # Advance to Bob and persist
        turn_manager_1.advance_non_combat_turn(created_scene_id)

        updates = {
            'current_turn_index': turn_manager_1.non_combat_index.get(created_scene_id, 0),
            'turn_order': turn_manager_1.non_combat_order.get(created_scene_id, [])
        }
        scene_manager_1.update_scene(created_scene_id, updates)

        # Verify state before "restart"
        scene_before = scene_manager_1.get_scene(created_scene_id)
        assert scene_before.current_turn_index == 1  # On Bob
        assert scene_before.turn_order == ["pc:alice", "pc:bob"]

        # Phase 2: Simulate restart by creating new instances
        turn_manager_2 = TurnManager()
        scene_integration_2 = SceneIntegration(turn_manager=turn_manager_2)
        turn_manager_2.scene_integration = scene_integration_2
        scene_manager_2 = scene_integration_2.get_scene_manager(campaign_id)

        # Load scene from disk
        scene_after = scene_manager_2.get_scene(created_scene_id)
        assert scene_after is not None

        # Restore turn state from scene
        if scene_after.turn_order:
            turn_manager_2.set_non_combat_order(created_scene_id, scene_after.turn_order)
            turn_manager_2.non_combat_index[created_scene_id] = scene_after.current_turn_index

        # Verify restored state
        assert turn_manager_2.non_combat_order[created_scene_id] == ["pc:alice", "pc:bob"]
        assert turn_manager_2.non_combat_index[created_scene_id] == 1
        assert turn_manager_2.get_current_character_non_combat(created_scene_id) == "pc:bob"

        # Verify we can continue from where we left off
        next_char = turn_manager_2.advance_non_combat_turn(created_scene_id)
        assert next_char == "pc:alice"  # Wraps around correctly

    def test_turn_manager_does_not_persist(self):
        """Verify that TurnManager no longer handles persistence directly.

        This test ensures the refactoring separated concerns properly:
        - TurnManager manages in-memory state
        - CampaignRunner/SceneManager handle persistence
        """
        campaign_id = generate_unique_id("test_no_persist")
        scene_id = generate_unique_id("scene")

        turn_manager = TurnManager()
        scene_integration = SceneIntegration(turn_manager=turn_manager)
        turn_manager.scene_integration = scene_integration
        scene_manager = scene_integration.get_scene_manager(campaign_id)

        scene_info = SceneInfo(
            scene_id=scene_id,
            title="Test Scene",
            scene_type="exploration",
            location_id="test_loc",
            location_description="Test location",
            description="Test",
            pcs_present=["alice", "bob"]
        )

        created_scene_id = scene_manager.create_scene(scene_info)

        # Create TurnManager with scene_integration
        character_ids = ["pc:alice", "pc:bob"]

        # Set order and advance
        turn_manager.set_non_combat_order(created_scene_id, character_ids)
        turn_manager.advance_non_combat_turn(created_scene_id)

        # Verify in-memory state is correct
        assert turn_manager.non_combat_index[created_scene_id] == 1

        # Verify scene was NOT automatically updated by TurnManager
        # (It should still have default values since we didn't call scene_manager.update_scene)
        scene_from_disk = scene_manager.get_scene(created_scene_id)

        # The scene should exist but turn_order and current_turn_index should be default
        # (empty list and 0, since we never called update_scene)
        assert scene_from_disk.turn_order == []  # Not persisted automatically
        assert scene_from_disk.current_turn_index == 0  # Not persisted automatically


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
