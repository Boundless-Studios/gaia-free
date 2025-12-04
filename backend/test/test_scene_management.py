"""Tests for scene management system."""

import unittest
import tempfile
import os
import json
from typing import Any, Dict
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add backend/src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gaia.models.scene_info import SceneInfo
from gaia.infra.storage.enhanced_scene_manager import EnhancedSceneManager
from gaia_private.session.scene.scene_transition_detector import SceneTransitionDetector, TransitionIndicator
from gaia_private.session.scene.scene_updater import SceneUpdater
from gaia_private.session.scene.scene_payloads import SceneAnalysisPayload, StructuredScenePayload
from gaia_private.session.scene.scene_integration import SceneIntegration
from gaia_private.session.turn_manager import TurnManager
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.utils.singleton import SingletonMeta


class TestEnhancedSceneManager(unittest.TestCase):
    """Test EnhancedSceneManager functionality."""

    def setUp(self):
        """Set up test environment."""
        # Clear SimpleCampaignManager singleton before test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]

        # Create temp directory for campaign storage
        self.temp_dir = tempfile.mkdtemp()
        os.environ['CAMPAIGN_STORAGE_PATH'] = self.temp_dir
        os.environ['ENVIRONMENT_NAME'] = 'test'

        self.campaign_id = "test_campaign"
        self.manager = EnhancedSceneManager(self.campaign_id)

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clear SimpleCampaignManager singleton after test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]

    def test_store_and_retrieve_scene(self):
        """Test storing and retrieving a SceneInfo object."""
        # Create a test scene
        scene = SceneInfo(
            scene_id="test_scene_001",
            title="Battle at the Gate",
            description="A fierce battle erupts at the city gates",
            location_id="city_gates",
            location_description="The main gates of the city",
            scene_type="combat",
            objectives=["Defend the gates", "Defeat the invaders"],
            npcs_involved=["Guard Captain", "Orc Warlord"],
            outcomes=[],
            narrative_notes=["Epic battle scene"],
            timestamp=datetime.now()
        )
        
        # Store the scene
        scene_id = self.manager.create_scene(scene)
        self.assertEqual(scene_id, "test_scene_001")
        
        # Retrieve the scene
        retrieved = self.manager.get_scene(scene_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.scene_id, scene.scene_id)
        self.assertEqual(retrieved.title, scene.title)
        self.assertEqual(retrieved.scene_type, scene.scene_type)
        self.assertEqual(retrieved.location_id, scene.location_id)
    
    def test_get_recent_scenes(self):
        """Test retrieving recent scenes."""
        # Create multiple scenes
        for i in range(3):
            scene = SceneInfo(
                scene_id=f"scene_{i:03d}",
                title=f"Scene {i}",
                description=f"Description {i}",
                location_id=f"location_{i}",
                location_description=f"Location description {i}",
                scene_type="exploration",
                timestamp=datetime.now()
            )
            self.manager.create_scene(scene)
        
        # Get recent scenes
        recent = self.manager.get_recent_scenes(2)
        self.assertEqual(len(recent), 2)
        # Most recent should be first
        self.assertEqual(recent[0].scene_id, "scene_002")
        self.assertEqual(recent[1].scene_id, "scene_001")
    
    def test_get_scenes_by_location(self):
        """Test retrieving scenes by location."""
        # Create scenes at different locations
        locations = ["tavern", "dungeon", "tavern", "forest"]
        for i, location in enumerate(locations):
            scene = SceneInfo(
                scene_id=f"scene_{i:03d}",
                title=f"Scene {i}",
                description=f"Description {i}",
                location_id=location,
                location_description=f"A {location} location",
                scene_type="social" if location == "tavern" else "exploration",
                timestamp=datetime.now()
            )
            self.manager.create_scene(scene)
        
        # Get scenes at tavern
        tavern_scenes = self.manager.get_scenes_by_location("tavern")
        self.assertEqual(len(tavern_scenes), 2)
        for scene in tavern_scenes:
            self.assertEqual(scene.location_id, "tavern")
    
    def test_update_scene_outcomes(self):
        """Test updating scene outcomes."""
        # Create and store a scene
        scene = SceneInfo(
            scene_id="test_scene",
            title="Test Scene",
            description="A test scene",
            location_id="test_location",
            location_description="A test location",
            scene_type="combat",
            outcomes=[],
            timestamp=datetime.now()
        )
        self.manager.create_scene(scene)
        
        # Update outcomes
        new_outcomes = ["Player defeated the goblin", "Found 10 gold pieces"]
        success = self.manager.update_scene_outcomes("test_scene", new_outcomes)
        self.assertTrue(success)
        
        # Retrieve and check
        updated = self.manager.get_scene("test_scene")
        self.assertEqual(len(updated.outcomes), 2)
        self.assertIn("Player defeated the goblin", updated.outcomes)


class TestSceneTransitionDetector(unittest.TestCase):
    """Test SceneTransitionDetector functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.detector = SceneTransitionDetector()
    
    def test_detect_first_scene(self):
        """Test detection of first scene."""
        analysis = {
            "scene_type": {"primary_type": "exploration"},
            "game_state": {"location": "Tavern"}
        }
        
        detected, indicators = self.detector.detect_transition(analysis)
        self.assertTrue(detected)
        self.assertIn(TransitionIndicator.MAJOR_EVENT, indicators)
    
    def test_detect_scene_type_change(self):
        """Test detection of scene type change."""
        previous = {
            "scene_type": {"primary_type": "social"}
        }
        current = {
            "scene_type": {"primary_type": "combat"}
        }
        
        detected, indicators = self.detector.detect_transition(current, previous)
        self.assertTrue(detected)
        self.assertIn(TransitionIndicator.SCENE_TYPE_CHANGE, indicators)
    
    def test_detect_location_change(self):
        """Test detection of location change."""
        previous = {
            "game_state": {"location": "Tavern"}
        }
        current = {
            "game_state": {"location": "Dungeon"},
            "scene_type": {"primary_type": "exploration", "indicators": []}
        }
        
        detected, indicators = self.detector.detect_transition(current, previous)
        self.assertTrue(detected)
        self.assertIn(TransitionIndicator.LOCATION_CHANGE, indicators)
    
    def test_no_transition(self):
        """Test when no transition occurs."""
        previous = {
            "scene_type": {"primary_type": "social"},
            "game_state": {"location": "Tavern"}
        }
        current = {
            "scene_type": {"primary_type": "social"},
            "game_state": {"location": "Tavern"}
        }
        
        detected, indicators = self.detector.detect_transition(current, previous)
        self.assertFalse(detected)
        self.assertEqual(len(indicators), 0)


class TestSceneUpdater(unittest.TestCase):
    """Test SceneUpdater functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.updater = SceneUpdater()

    def _create_scene(self, analysis: Dict[str, Any], structured_data: Dict[str, Any]) -> SceneInfo:
        analysis_payload = SceneAnalysisPayload.from_raw(analysis)
        structured_payload = StructuredScenePayload.from_raw(structured_data)
        return self.updater.create_from_analysis(analysis_payload, structured_payload)
    
    def test_create_from_analysis(self):
        """Test creating a scene from analysis with character_resolution."""
        analysis = {
            "scene_type": {"primary_type": "combat"},
            "game_state": {"location": "Dungeon Room 5"},
            "complexity": {
                "score": 6,
                "primary_challenge": "Multiple enemies"
            },
            "requirements": {
                "priority_order": ["Defeat enemies", "Protect allies"]
            }
        }

        structured_data = {
            "narrative": "The goblins attack from the shadows!",
            "dice_rolls": [
                {"purpose": "Initiative", "result": "15"}
            ],
            "character_resolution": {
                "npcs": [
                    {"display_name": "Goblin", "character_id": "npc:goblin"},
                    {"display_name": "Orc", "character_id": "npc:orc"}
                ],
                "monsters": [],
                "players": []
            }
        }

        scene = self._create_scene(analysis, structured_data)

        self.assertIsNotNone(scene)
        self.assertEqual(scene.scene_type, "combat")
        self.assertEqual(scene.location_id, "Dungeon Room 5")
        self.assertIn("Goblin", scene.npcs_involved)
        self.assertIn("Orc", scene.npcs_involved)
        self.assertTrue(len(scene.objectives) > 0)
        self.assertIn("The goblins attack", scene.description)
    
    def test_scene_id_generation(self):
        """Test that scene IDs are unique."""
        analysis = {
            "scene_type": {"primary_type": "exploration"},
            "game_state": {"location": "Forest"}
        }
        structured_data = {}
        
        scene1 = self._create_scene(analysis, structured_data)
        scene2 = self._create_scene(analysis, structured_data)
        
        self.assertNotEqual(scene1.scene_id, scene2.scene_id)
        self.assertIn("exploration", scene1.scene_id)

    def test_filters_players_from_npcs(self):
        """Ensure player characters are not recorded as NPCs via character_resolution."""
        analysis = {
            "scene_type": {"primary_type": "narrative"},
            "game_state": {"location": "Dockside"},
            "players": [
                {"character_id": "pc:lysander_moonwhisper", "name": "Lysander Moonwhisper"},
                {"character_id": "pc:shadow", "name": "Shadow"}
            ]
        }

        structured_data = {
            "narrative": "The docks are busy with activity.",
            "character_resolution": {
                "players": [
                    {"display_name": "Lysander Moonwhisper", "character_id": "pc:lysander_moonwhisper"},
                    {"display_name": "Shadow", "character_id": "pc:shadow"}
                ],
                "npcs": [
                    {"display_name": "Goblin Lookout", "character_id": "npc:goblin_lookout"},
                    {"display_name": "Captain Mira Quickspark", "character_id": "npc:captain_mira"},
                    {"display_name": "Dockworker Rynn", "character_id": "npc:dockworker_rynn"}
                ],
                "monsters": []
            }
        }

        scene = self._create_scene(analysis, structured_data)

        self.assertEqual(scene.location_id, "Dockside")
        self.assertIn("Goblin Lookout", scene.npcs_involved)
        self.assertIn("Captain Mira Quickspark", scene.npcs_involved)
        self.assertIn("Dockworker Rynn", scene.npcs_involved)
        self.assertNotIn("Shadow", scene.npcs_involved)
        self.assertNotIn("Lysander Moonwhisper", scene.npcs_involved)

    def test_npc_dict_string_values_preserved(self):
        """NPC character_resolution entries should properly surface NPCs while filtering players."""
        analysis = {
            "scene_type": {"primary_type": "narrative"},
            "game_state": {"location": "Harbor"},
            "players": [
                {"character_id": "pc:shadow", "name": "Shadow"}
            ]
        }
        structured_data = {
            "narrative": "At the harbor docks.",
            "character_resolution": {
                "players": [
                    {"display_name": "Shadow", "character_id": "pc:shadow"}
                ],
                "npcs": [
                    {"display_name": "Captain Mira Quickspark", "character_id": "npc:captain_mira"},
                    {"display_name": "Dockworker Rynn", "character_id": "npc:dockworker_rynn"}
                ],
                "monsters": []
            }
        }

        scene = self._create_scene(analysis, structured_data)

        self.assertIn("Captain Mira Quickspark", scene.npcs_involved)
        self.assertIn("Dockworker Rynn", scene.npcs_involved)
        self.assertNotIn("Shadow", scene.npcs_involved)


class TestSceneIntegration(unittest.TestCase):
    """Test SceneIntegration functionality."""

    def setUp(self):
        """Set up test environment."""
        # Clear SimpleCampaignManager singleton before test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]

        # Create temp directory for campaign storage
        self.temp_dir = tempfile.mkdtemp()
        os.environ['CAMPAIGN_STORAGE_PATH'] = self.temp_dir
        os.environ['ENVIRONMENT_NAME'] = 'test'

        self.turn_manager = TurnManager()
        self.integration = SceneIntegration(turn_manager=self.turn_manager)
        self.turn_manager.scene_integration = self.integration
        self.campaign_id = "test_campaign"

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clear SimpleCampaignManager singleton after test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]
    
    def test_process_scene_transition(self):
        """Test processing a scene transition."""
        analysis = {
            "scene_type": {"primary_type": "combat"},
            "game_state": {"location": "Arena"},
            "active_characters": ["Gladiator"],
            "complexity": {"score": 7, "primary_challenge": "Boss fight"}
        }
        
        structured_data = {
            "narrative": "The champion enters the arena!"
        }
        
        # Process transition (first scene)
        scene_info = self.integration.process_scene_transition(
            self.campaign_id, analysis, structured_data
        )
        
        self.assertIsNotNone(scene_info)
        self.assertTrue(scene_info["transition_occurred"])
        self.assertEqual(scene_info["scene_type"], "combat")
        self.assertEqual(scene_info["location"], "Arena")
        self.assertIn("scene_id", scene_info)
    
    def test_no_transition(self):
        """Test when no transition occurs."""
        # Set up initial scene
        initial_analysis = {
            "scene_type": {"primary_type": "social"},
            "game_state": {"location": "Tavern"}
        }
        self.integration.process_scene_transition(
            self.campaign_id, initial_analysis, {}
        )
        
        # Same scene, no transition
        same_analysis = {
            "scene_type": {"primary_type": "social"},
            "game_state": {"location": "Tavern"}
        }
        
        scene_info = self.integration.process_scene_transition(
            self.campaign_id, same_analysis, {}
        )
        
        self.assertIsNotNone(scene_info)
        self.assertFalse(scene_info["transition_occurred"])
    
    def test_add_scene_to_structured_data(self):
        """Test adding scene info to structured data."""
        structured_data = {
            "narrative": "Test narrative",
            "turn": "Player's turn"
        }
        
        scene_info = {
            "scene_id": "scene_001",
            "scene_type": "combat",
            "location": "Battlefield"
        }
        
        updated = self.integration.add_scene_to_structured_data(
            structured_data, scene_info
        )
        
        self.assertIn("scene", updated)
        self.assertEqual(updated["scene"]["scene_id"], "scene_001")
        self.assertEqual(updated["scene_id"], "scene_001")  # Backward compatibility
        self.assertEqual(updated["narrative"], "Test narrative")  # Original data preserved


if __name__ == "__main__":
    unittest.main()
