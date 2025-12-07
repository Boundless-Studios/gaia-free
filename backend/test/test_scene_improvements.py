"""Test the improved scene management system."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil
from typing import Any, Dict

from gaia.models.scene_info import SceneInfo
from gaia.infra.storage.enhanced_scene_manager import EnhancedSceneManager
from gaia_private.session.scene.scene_updater import SceneUpdater
from gaia_private.session.scene.scene_payloads import SceneAnalysisPayload, StructuredScenePayload
from gaia_private.session.scene.objectives_extractor import ObjectivesExtractor
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.utils.singleton import SingletonMeta


class TestSceneImprovements(unittest.TestCase):
    """Test the improved scene management features."""

    def setUp(self):
        """Set up test environment."""
        # Clear SimpleCampaignManager singleton before test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]

        # Create temporary directory for test campaign storage
        self.test_dir = tempfile.mkdtemp()
        os.environ['CAMPAIGN_STORAGE_PATH'] = self.test_dir
        os.environ['ENVIRONMENT_NAME'] = 'test'

        # Initialize components
        self.objectives_extractor = ObjectivesExtractor()
        self.scene_updater = SceneUpdater(objectives_extractor=self.objectives_extractor)
        self.scene_manager = EnhancedSceneManager("test_campaign")
        self.game_state_stub = None

    def _create_scene(self, analysis: Dict[str, Any], structured_data: Dict[str, Any]) -> SceneInfo:
        analysis_payload = SceneAnalysisPayload.from_raw(analysis)
        structured_payload = StructuredScenePayload.from_raw(structured_data)
        return self.scene_updater.create_from_analysis(analysis_payload, structured_payload, None, None)

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        # Clear SimpleCampaignManager singleton after test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]
    
    def test_scene_info_new_fields(self):
        """Test that SceneInfo has all the new fields."""
        scene = SceneInfo(
            scene_id="test_001",
            title="Test Scene",
            description="A test scene",
            scene_type="social",
            objectives=["Talk to the barkeep", "Gather information"],
            npcs_involved=["Barkeep", "Mysterious Stranger"],
            metadata={"location": "tavern"}
        )
        
        # Check creation fields exist
        self.assertIsNotNone(scene.metadata)
        self.assertEqual(scene.metadata.get("location"), "tavern")
        
        # Check update fields exist with defaults
        self.assertEqual(scene.npcs_added, [])
        self.assertEqual(scene.npcs_removed, [])
        self.assertEqual(scene.duration_turns, 0)
        self.assertIsNone(scene.last_updated)
    
    def test_objectives_extraction(self):
        """Test that objectives are extracted sensibly."""
        analysis = {
            "scene_type": {"primary_type": "combat"},
            "active_characters": [
                {"name": "Goblin", "is_hostile": True},
                {"name": "Orc", "is_hostile": True}
            ],
            "requirements": {
                "priority_order": ["EnvironmentHandler", "map_handler"]  # Bad objectives
            }
        }
        
        structured_data = {
            "player_action": "I want to defeat the goblins and find the treasure",
            "turn": {
                "options": [
                    "Attack the goblin leader",
                    "Search for hidden passages"
                ]
            }
        }
        
        objectives = self.objectives_extractor.extract_initial_objectives(
            analysis, structured_data, None
        )
        
        # Check that we get sensible objectives
        self.assertGreater(len(objectives), 0)
        
        # Check that agent names are filtered out
        for obj in objectives:
            self.assertNotIn("EnvironmentHandler", obj)
            self.assertNotIn("map_handler", obj)
        
        # Check that we have combat-related objectives
        combat_objectives = [obj for obj in objectives if "defeat" in obj.lower() or "survive" in obj.lower()]
        self.assertGreater(len(combat_objectives), 0)
    
    def test_scene_creation_vs_update(self):
        """Test that scene creation and updates are properly separated."""
        # Create a new scene
        scene = SceneInfo(
            scene_id="test_002",
            title="Combat Scene",
            description="A fierce battle",
            scene_type="combat",
            objectives=["Defeat the enemies"],
            npcs_involved=["Goblin Leader"],
            metadata={"location": "dungeon"}
        )
        
        # Create the scene
        scene_id = self.scene_manager.create_scene(scene)
        self.assertEqual(scene_id, "test_002")
        
        # Try to create the same scene again - should fail
        with self.assertRaises(ValueError) as context:
            self.scene_manager.create_scene(scene)
        self.assertIn("already exists", str(context.exception))
        
        # Update the scene with new outcomes
        success = self.scene_manager.update_scene(
            scene_id,
            {
                "outcomes": ["Player defeated 2 goblins"],
                "duration_turns": 5
            }
        )
        self.assertTrue(success)
        
        # Retrieve and verify updates
        updated_scene = self.scene_manager.get_scene(scene_id)
        self.assertEqual(len(updated_scene.outcomes), 1)
        self.assertEqual(updated_scene.outcomes[0], "Player defeated 2 goblins")
        self.assertEqual(updated_scene.duration_turns, 5)
        self.assertIsNotNone(updated_scene.last_updated)
        
        # Verify creation fields weren't changed
        self.assertEqual(updated_scene.title, "Combat Scene")
        self.assertEqual(updated_scene.metadata.get("location"), "dungeon")
    
    def test_scene_updater_with_extractor(self):
        """Test that scene updater uses the objectives extractor."""
        analysis = {
            "scene_type": {"primary_type": "social"},
            "game_state": {"location": "Town Square"}
        }

        structured_data = {
            "narrative": "The merchant asks you to retrieve his stolen goods from the bandits.",
            "character_resolution": {
                "npcs": [
                    {"display_name": "Merchant", "character_id": "npc:merchant"},
                    {"display_name": "Town Guard", "character_id": "npc:town_guard"}
                ],
                "monsters": [],
                "players": []
            }
        }

        scene = self._create_scene(analysis, structured_data)

        # Check scene was created with proper fields
        self.assertIsNotNone(scene.scene_id)
        self.assertEqual(scene.metadata.get("location", {}).get("id") or scene.metadata.get("location"), "Town Square")

        # Check objectives are sensible
        for obj in scene.objectives:
            self.assertNotIn("Handler", obj)
            self.assertNotIn("Runner", obj)
    
    def test_update_only_allowed_fields(self):
        """Test that only allowed fields can be updated."""
        # Create a scene
        scene = SceneInfo(
            scene_id="test_003",
            title="Original Title",
            description="Original Description",
            scene_type="social",
            metadata={"location": "original_location"}
        )
        
        scene_id = self.scene_manager.create_scene(scene)
        
        # Try to update both allowed and disallowed fields
        success = self.scene_manager.update_scene(
            scene_id,
            {
                "title": "New Title",  # Not allowed
                "outcomes": ["Something happened"],  # Allowed
                "metadata": {"location": "updated_location"},  # Allowed
            }
        )
        
        # Update should succeed but only for allowed fields
        self.assertTrue(success)
        
        # Verify only allowed fields were updated
        updated_scene = self.scene_manager.get_scene(scene_id)
        self.assertEqual(updated_scene.title, "Original Title")  # Unchanged
        self.assertEqual(updated_scene.metadata.get("location"), "updated_location")  # Updated
        self.assertEqual(len(updated_scene.outcomes), 1)  # Updated


if __name__ == '__main__':
    unittest.main()
