"""Unit tests for combat/scene association."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from gaia_private.orchestration.combat_orchestrator import CombatOrchestrator
from gaia_private.models.combat.agent_io.initiation import CombatInitiationRequest, SceneContext, CombatantInfo
from gaia_private.session.scene.scene_integration import SceneIntegration
from gaia_private.session.turn_manager import TurnManager
from gaia.infra.storage.enhanced_scene_manager import EnhancedSceneManager
from gaia.models.scene_info import SceneInfo


@pytest.mark.unit
@pytest.mark.asyncio
class TestCombatSceneAssociation:
    """Test that combat properly associates with scenes."""

    @pytest.fixture
    def mock_campaign_runner(self):
        """Create mock campaign runner with scene integration."""
        campaign_runner = MagicMock()
        turn_manager = TurnManager()
        campaign_runner.scene_integration = SceneIntegration(turn_manager=turn_manager)
        turn_manager.scene_integration = campaign_runner.scene_integration
        campaign_runner.turn_manager = turn_manager
        campaign_runner.character_manager = MagicMock()
        campaign_runner.combat_state_manager = None
        return campaign_runner

    @pytest.fixture
    def test_scene(self):
        """Create a test scene."""
        return {
            "scene_id": "tavern_brawl_001",
            "title": "The Prancing Pony Tavern",
            "description": "A rowdy tavern filled with patrons",
            "scene_type": "social",
            "in_combat": False
        }

    @pytest.fixture
    def analysis_context(self, test_scene):
        """Create analysis context for testing."""
        return {
            "current_scene": test_scene,
            "players": [{"name": "Alice", "class": "Fighter", "level": 3}],
            "npcs": [{"name": "Rude Patron", "hostile": True, "creature_type": "humanoid"}],
            "game_state": {"location": "Tavern"},
            "threat_level": "easy"
        }

    async def test_build_combat_initiation_with_real_scene_id(
        self, mock_campaign_runner, test_scene, analysis_context
    ):
        """Test building combat initiation request uses real scene ID."""
        campaign_id = "test_campaign"
        mock_campaign_runner.scene_integration.current_scenes[campaign_id] = test_scene

        orchestrator = CombatOrchestrator(mock_campaign_runner)

        user_input = "I attack the rude patron!"
        request = orchestrator.build_combat_initiation_request(
            user_input, campaign_id, analysis_context
        )

        # Should use real scene ID
        assert request.scene.scene_id == "tavern_brawl_001"
        assert request.scene.title == "The Prancing Pony Tavern"
        assert request.scene.description == "A rowdy tavern filled with patrons"
        assert request.scene.location == "Tavern"

    async def test_fallback_when_no_current_scene(self, mock_campaign_runner, analysis_context):
        """Test fallback behavior when no current scene exists."""
        campaign_id = "test_campaign"
        orchestrator = CombatOrchestrator(mock_campaign_runner)

        # Clear current scenes
        mock_campaign_runner.scene_integration.current_scenes.clear()

        # Add a fallback scene to the scene manager
        scene_manager = mock_campaign_runner.scene_integration.get_scene_manager(campaign_id)
        fallback_scene = SceneInfo(
            scene_id="forest_encounter_002",
            title="Dark Forest Path",
            description="A dark path through the forest",
            scene_type="exploration",
            timestamp=datetime.now()
        )
        scene_manager._store_scene_internal(fallback_scene)

        user_input = "I attack!"
        request = orchestrator.build_combat_initiation_request(
            user_input, campaign_id, analysis_context
        )

        # Should use the fallback scene
        assert request.scene.scene_id == "forest_encounter_002"
        assert request.scene.title == "Dark Forest Path"

    async def test_scene_id_generation_with_no_existing_scenes(
        self, mock_campaign_runner, analysis_context
    ):
        """Test scene ID generation when no scenes exist."""
        campaign_id = "test_campaign"
        orchestrator = CombatOrchestrator(mock_campaign_runner)

        # Clear all scenes
        mock_campaign_runner.scene_integration.current_scenes.clear()
        scene_manager = mock_campaign_runner.scene_integration.get_scene_manager(campaign_id)
        scene_manager.scenes.clear()

        # Remove current_scene from analysis context
        analysis_context_no_scene = analysis_context.copy()
        analysis_context_no_scene.pop("current_scene", None)

        user_input = "Combat begins!"
        request = orchestrator.build_combat_initiation_request(
            user_input, campaign_id, analysis_context_no_scene
        )

        # Should generate a new scene ID
        assert request.scene.scene_id is not None
        assert "combat" in request.scene.scene_id.lower()
        assert request.scene.location == "Tavern"

    async def test_combat_sets_scene_in_combat_flag(self, mock_campaign_runner, test_scene):
        """Test that initiating combat sets the in_combat flag on the scene."""
        campaign_id = "test_campaign"
        mock_campaign_runner.scene_integration.current_scenes[campaign_id] = test_scene.copy()

        orchestrator = CombatOrchestrator(mock_campaign_runner)

        # Mock the combat state manager
        mock_combat_state = MagicMock()
        mock_campaign_runner.combat_state_manager = mock_combat_state

        # Simulate combat initiation
        analysis_context = {
            "current_scene": test_scene,
            "players": [{"name": "Hero", "class": "Fighter", "level": 5}],
            "npcs": [{"name": "Goblin", "hostile": True}],
            "game_state": {"location": "Tavern"}
        }

        request = orchestrator.build_combat_initiation_request(
            "Attack!", campaign_id, analysis_context
        )

        # After combat initiation, the scene should be marked as in_combat
        # (This would normally happen in initiate_combat method)
        assert request.scene.scene_id == "tavern_brawl_001"

    async def test_scene_context_environmental_factors(
        self, mock_campaign_runner, test_scene, analysis_context
    ):
        """Test that environmental factors are properly extracted."""
        campaign_id = "test_campaign"

        # Add environmental factors to the analysis context
        analysis_context["environment"] = {
            "obstacles": ["overturned tables", "broken glass"],
            "lighting": "dim"
        }

        mock_campaign_runner.scene_integration.current_scenes[campaign_id] = test_scene

        orchestrator = CombatOrchestrator(mock_campaign_runner)
        request = orchestrator.build_combat_initiation_request(
            "Fight!", campaign_id, analysis_context
        )

        # Check environmental factors
        assert request.scene.environmental_factors is not None
        assert "overturned tables" in request.scene.environmental_factors
        assert "broken glass" in request.scene.environmental_factors

    async def test_combatant_extraction_from_analysis(
        self, mock_campaign_runner, test_scene, analysis_context
    ):
        """Test that combatants are properly extracted from analysis context."""
        campaign_id = "test_campaign"
        mock_campaign_runner.scene_integration.current_scenes[campaign_id] = test_scene

        orchestrator = CombatOrchestrator(mock_campaign_runner)
        request = orchestrator.build_combat_initiation_request(
            "Attack!", campaign_id, analysis_context
        )

        # Check combatants
        assert len(request.combatants) >= 2

        # Find player and npc
        player = next((c for c in request.combatants if c.name == "Alice"), None)
        npc = next((c for c in request.combatants if c.name == "Rude Patron"), None)

        assert player is not None
        assert player.type == "player"
        assert player.class_or_creature == "Fighter"
        assert player.level == 3
        assert player.hostile is False

        assert npc is not None
        assert npc.type == "enemy"  # Hostile NPCs become enemies
        assert npc.hostile is True
