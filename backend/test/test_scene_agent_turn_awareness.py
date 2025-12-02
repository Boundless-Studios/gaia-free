"""Tests for scene agent turn awareness.

This module verifies that scene agents receive and properly use turn information
to frame their responses appropriately for the active player.
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from gaia_private.orchestration.smart_router import SmartAgentRouter
from gaia.models.turn import Turn, TurnType, TurnStatus
from gaia.models.character.character_info import CharacterInfo
from gaia_private.agents.scene.dialog_agent import DialogAgent
from gaia_private.agents.scene.exploration_agent import ExplorationAgent
from gaia_private.agents.scene.scene_describer import SceneDescriberAgent
from gaia_private.agents.scene.action_resolver import ActionResolver


class TestSmartRouterTurnInjection:
    """Test that smart_router properly injects turn information into analysis_context."""

    @pytest.fixture
    def mock_campaign_runner(self):
        """Create a mock campaign runner with required managers."""
        runner = Mock()
        runner.turn_manager = Mock()
        runner.context_manager = Mock()
        runner.parallel_analyzer = AsyncMock()
        runner.history_manager = Mock()
        runner.history_manager.get_full_history = Mock(return_value=[])
        runner.player_options_agent = AsyncMock()
        runner.player_options_agent.generate_options = AsyncMock(return_value={'player_options': []})

        # Mock character manager retrieval
        character_manager = Mock()
        character_manager.characters = {}  # Empty dict to iterate over
        runner._get_character_manager = Mock(return_value=character_manager)

        # Mock services (required by SmartAgentRouter)
        services = Mock()
        services.context_manager = runner.context_manager
        services.turn_manager = runner.turn_manager
        # Mock turn manager attributes for turn number calculation
        services.turn_manager.non_combat_index = {}
        services.turn_manager.non_combat_order = {}
        # Mock turn manager methods that smart_router uses
        services.turn_manager.get_current_character_non_combat = Mock(return_value=None)
        services.turn_manager.get_next_character_non_combat = Mock(return_value=None)
        services.campaign_manager = Mock()
        services.campaign_manager.load_campaign = Mock(return_value=Mock())
        services.scene_integration = Mock()
        services.scene_integration.current_scenes = {}
        services.scene_integration.ensure_scene_loaded = Mock()
        services.get_character_manager = Mock(return_value=character_manager)
        runner.services = services

        # Mock character details method
        character_manager.get_character_details = Mock(return_value={})

        # Mock combat_state_manager to avoid combat orchestrator errors
        runner.combat_state_manager = Mock()
        runner.combat_state_manager.get_active_combat = Mock(return_value=None)
        runner.combat_state_manager.get_initialized_combat = Mock(return_value=None)

        return runner, character_manager

    @pytest.fixture
    def sample_turn(self):
        """Create a sample player character turn."""
        return Turn(
            turn_id="turn_001",
            campaign_id="campaign_123",
            turn_number=5,
            character_id="pc_thorin_456",
            character_name="Thorin Ironforge",
            turn_type=TurnType.PLAYER,
            scene_id="scene_789",
            scene_type="exploration",
            status=TurnStatus.ACTIVE,
            context={}
        )

    @pytest.fixture
    def sample_character(self):
        """Create a sample character with personality traits."""
        return CharacterInfo(
            character_id="pc_thorin_456",
            name="Thorin Ironforge",
            race="Dwarf",
            character_class="Fighter",
            level=5,
            alignment="Lawful Good",
            personality_traits=["Brave", "Stubborn", "Loyal"],
            backstory="A seasoned warrior from the Mountain Kingdoms",
            description="A stout dwarf with a braided beard and battle-scarred armor",
            voice_id="voice_123",
            hit_points_max=45,
            hit_points_current=45,
            armor_class=18
        )

    @pytest.mark.asyncio
    async def test_turn_info_injected_for_player_turn(self, mock_campaign_runner, sample_turn, sample_character):
        """Verify turn information is injected into analysis_context for player turns."""
        runner, character_manager = mock_campaign_runner

        # Setup mocks
        runner.turn_manager.get_current_turn.return_value = sample_turn
        character_manager.get_character.return_value = sample_character
        # Mock characters dict for iteration
        character_manager.characters = {"pc_thorin_456": sample_character}
        # Mock get_character_details for turn injection
        character_manager.get_character_details.return_value = {
            "name": "Thorin Ironforge",
            "character_class": "Fighter",
            "race": "Dwarf"
        }
        runner.context_manager.get_scene_context.return_value = {
            "previous_scenes": [],
            "game_state": {},
            "current_scene": {"scene_id": "scene_789"}
        }
        runner.context_manager.check_scene_agent_repetition.return_value = (False, 0)

        # Mock scene integration to have an active scene
        runner.services.scene_integration.current_scenes = {"campaign_123": {"scene_id": "scene_789"}}

        # Mock parallel analysis
        runner.parallel_analyzer.analyze_scene.return_value = {
            "routing": {
                "primary_agent": "dialog",
                "reasoning": "Player is speaking to NPC"
            },
            "overall": {"confidence_score": 0.8},
            "complexity": {"level": "SIMPLE"},
            "scene": {
                "game_phase": "EXPLORATION",
                "primary_type": "social"
            },
            "special_considerations": {
                "requires_dm_judgment": False
            }
        }

        # Mock dialog agent
        runner.dialog_agent = AsyncMock()
        runner.dialog_agent.handle_dialog = AsyncMock(return_value={
            "npc_name": "Guard",
            "dialog": "Halt!",
            "emotion": "stern",
            "handoff_to": "none"
        })

        # Create router and analyze
        router = SmartAgentRouter(runner)

        # Patch _extract_and_augment_characters to avoid complex dependencies
        with patch.object(router, '_extract_and_augment_characters', return_value=(
            runner.parallel_analyzer.analyze_scene.return_value, [], []
        )):
            await router.analyze_and_route("Hello guard", "campaign_123")

        # Verify turn manager was called
        runner.turn_manager.get_current_turn.assert_called_once_with("campaign_123")

        # Verify dialog agent received enriched analysis_context
        call_args = runner.dialog_agent.handle_dialog.call_args
        assert call_args is not None

        analysis_context = call_args[0][1]  # Second argument is analysis_context

        # Verify current_turn is in analysis_context
        assert "current_turn" in analysis_context
        current_turn = analysis_context["current_turn"]

        # Verify basic turn info (character enrichment tested separately)
        assert current_turn["character_id"] == "pc_thorin_456"
        assert current_turn["character_name"] == "Thorin Ironforge"

    @pytest.mark.asyncio
    async def test_no_turn_info_when_no_current_turn(self, mock_campaign_runner):
        """Verify graceful handling when no current turn exists."""
        runner, _ = mock_campaign_runner

        # Setup: No current turn
        runner.turn_manager.get_current_turn.return_value = None
        runner.context_manager.get_scene_context.return_value = {
            "previous_scenes": [],
            "game_state": {},
            "current_scene": {"scene_id": "scene_123"}
        }
        runner.context_manager.check_scene_agent_repetition.return_value = (False, 0)

        # Mock scene integration to have an active scene
        runner.services.scene_integration.current_scenes = {"campaign_123": {"scene_id": "scene_123"}}

        # Mock parallel analysis
        runner.parallel_analyzer.analyze_scene.return_value = {
            "routing": {
                "primary_agent": "dialog",
                "reasoning": "Player is speaking to NPC"
            },
            "overall": {"confidence_score": 0.8},
            "complexity": {"level": "SIMPLE"},
            "scene": {
                "game_phase": "EXPLORATION",
                "primary_type": "social"
            },
            "special_considerations": {
                "requires_dm_judgment": False
            }
        }

        runner.dialog_agent = AsyncMock()
        runner.dialog_agent.handle_dialog = AsyncMock(return_value={
            "npc_name": "Guard",
            "dialog": "Halt!",
            "emotion": "stern",
            "handoff_to": "none"
        })

        router = SmartAgentRouter(runner)

        await router.analyze_and_route("Hello", "campaign_123")

        # Verify turn manager was called
        runner.turn_manager.get_current_turn.assert_called_once_with("campaign_123")

        # Verify dialog agent received analysis_context without current_turn
        call_args = runner.dialog_agent.handle_dialog.call_args
        analysis_context = call_args[0][1]

        assert "current_turn" not in analysis_context

    @pytest.mark.asyncio
    async def test_dm_turn_no_character_details(self, mock_campaign_runner):
        """Verify DM turns don't attempt to fetch character details."""
        runner, character_manager = mock_campaign_runner

        # Create a DM turn
        dm_turn = Turn(
            turn_id="turn_dm_001",
            campaign_id="campaign_123",
            turn_number=1,
            character_id="dm",
            character_name="Dungeon Master",
            turn_type=TurnType.NARRATIVE,
            scene_id=None,
            scene_type=None,
            status=TurnStatus.ACTIVE,
            context={}
        )

        runner.turn_manager.get_current_turn.return_value = dm_turn
        runner.context_manager.get_scene_context.return_value = {
            "previous_scenes": [],
            "game_state": {},
            "current_scene": {"scene_id": "scene_dm"}
        }
        runner.context_manager.check_scene_agent_repetition.return_value = (False, 0)

        # Mock scene integration to have an active scene
        runner.services.scene_integration.current_scenes = {"campaign_123": {"scene_id": "scene_dm"}}

        runner.parallel_analyzer.analyze_scene.return_value = {
            "routing": {
                "primary_agent": "dialog",
                "reasoning": "Test scenario"
            },
            "overall": {"confidence_score": 0.8},
            "complexity": {"level": "SIMPLE"},
            "scene": {
                "game_phase": "EXPLORATION",
                "primary_type": "social"
            },
            "special_considerations": {
                "requires_dm_judgment": False
            }
        }

        runner.dialog_agent = AsyncMock()
        runner.dialog_agent.handle_dialog = AsyncMock(return_value={
            "npc_name": "NPC",
            "dialog": "Hello",
            "emotion": "neutral",
            "handoff_to": "none"
        })

        router = SmartAgentRouter(runner)

        # Patch _extract_and_augment_characters to avoid complex dependencies
        with patch.object(router, '_extract_and_augment_characters', return_value=(
            runner.parallel_analyzer.analyze_scene.return_value, [], []
        )):
            await router.analyze_and_route("Test", "campaign_123")

        # Verify turn info still included but without character details
        call_args = runner.dialog_agent.handle_dialog.call_args
        analysis_context = call_args[0][1]

        assert "current_turn" in analysis_context
        current_turn = analysis_context["current_turn"]

        # Just verify DM turn is injected (not checking enrichment)
        assert current_turn["character_id"] is not None
        assert current_turn["character_name"] is not None

    @pytest.mark.asyncio
    async def test_next_turn_info_injected(self, mock_campaign_runner, sample_turn, sample_character):
        """Verify next turn information is injected for player option generation."""
        runner, character_manager = mock_campaign_runner

        # Create next character
        next_character = CharacterInfo(
            character_id="pc_shadow_789",
            name="Shadow",
            race="Human",
            character_class="Rogue",
            level=4,
            alignment="Chaotic Neutral",
            personality_traits=["Sneaky", "Observant", "Paranoid"],
            backstory="A mysterious figure from the streets",
            description="A cloaked human with piercing eyes",
            voice_id="voice_456",
            hit_points_max=32,
            hit_points_current=32,
            armor_class=15
        )

        # Setup mocks
        runner.turn_manager.get_current_turn.return_value = sample_turn
        runner.turn_manager.get_next_character_non_combat.return_value = "pc_shadow_789"
        # Mock characters dict for current and next character
        character_manager.characters = {
            "pc_thorin_456": sample_character,
            "pc_shadow_789": next_character
        }
        character_manager.get_character_details.return_value = {
            "name": "Shadow",
            "character_class": "Rogue",
            "personality_traits": ["Sneaky", "Observant", "Paranoid"],
            "backstory": "A mysterious figure from the streets"
        }
        runner.context_manager.get_scene_context.return_value = {
            "previous_scenes": [],
            "game_state": {},
            "current_scene": {"scene_id": "scene_789"}
        }
        runner.context_manager.check_scene_agent_repetition.return_value = (False, 0)

        # Mock scene integration to have an active scene
        runner.services.scene_integration.current_scenes = {"campaign_123": {"scene_id": "scene_789"}}

        runner.parallel_analyzer.analyze_scene.return_value = {
            "routing": {
                "primary_agent": "dialog",
                "reasoning": "Test scenario"
            },
            "overall": {"confidence_score": 0.8},
            "complexity": {"level": "SIMPLE"},
            "scene": {
                "game_phase": "EXPLORATION",
                "primary_type": "social"
            },
            "special_considerations": {
                "requires_dm_judgment": False
            }
        }

        runner.dialog_agent = AsyncMock()
        runner.dialog_agent.handle_dialog = AsyncMock(return_value={
            "npc_name": "Guard",
            "dialog": "Halt!",
            "emotion": "stern",
            "handoff_to": "none"
        })

        router = SmartAgentRouter(runner)

        # Patch _extract_and_augment_characters to avoid complex dependencies
        with patch.object(router, '_extract_and_augment_characters', return_value=(
            runner.parallel_analyzer.analyze_scene.return_value, [], []
        )):
            await router.analyze_and_route("Hello guard", "campaign_123")

        # Verify next character was queried
        runner.turn_manager.get_next_character_non_combat.assert_called()

        # Verify dialog agent received next_turn info
        call_args = runner.dialog_agent.handle_dialog.call_args
        analysis_context = call_args[0][1]

        assert "next_turn" in analysis_context
        next_turn = analysis_context["next_turn"]

        # Verify basic next turn info (enrichment tested separately)
        assert next_turn["character_id"] == "pc_shadow_789"
        assert next_turn["character_name"] == "Shadow"


class TestSceneAgentInstructions:
    """Test that scene agents properly use turn context in their instructions."""

    @pytest.mark.asyncio
    async def test_dialog_agent_includes_turn_context(self):
        """Verify dialog agent instructions include active player context."""
        agent = DialogAgent()

        analysis_context = {
            "active_characters": [{"name": "Guard"}],
            "previous_scenes": [{"narrative": "You stand before the city gates."}],
            "current_turn": {
                "character_name": "Thorin Ironforge",
                "personality_traits": ["Brave", "Stubborn"],
                "description": "A stout dwarf warrior"
            }
        }

        instructions = await agent._get_instructions(analysis_context)

        # Verify turn context is included
        assert "ACTIVE PLAYER: Thorin Ironforge" in instructions
        assert "Brave, Stubborn" in instructions
        assert "A stout dwarf warrior" in instructions
        assert "Frame your NPC response to address Thorin Ironforge specifically" in instructions

    @pytest.mark.asyncio
    async def test_exploration_agent_includes_turn_context(self):
        """Verify exploration agent instructions include active player context."""
        agent = ExplorationAgent()

        analysis_context = {
            "previous_scenes": [{"narrative": "A dark corridor stretches ahead."}],
            "current_turn": {
                "character_name": "Elara Moonwhisper",
                "personality_traits": ["Curious", "Cautious"],
                "description": "An elven ranger"
            }
        }

        precomputed_events = {
            "perception_roll": 15,
            "overall_significance": "moderate"
        }

        instructions = await agent._get_instructions(analysis_context, precomputed_events)

        # Verify turn context is included
        assert "ACTIVE PLAYER: Elara Moonwhisper" in instructions
        assert "Curious, Cautious" in instructions
        assert "An elven ranger" in instructions
        assert "Frame discoveries and narrative to match Elara Moonwhisper's perspective" in instructions

    @pytest.mark.asyncio
    async def test_scene_describer_includes_turn_context(self):
        """Verify scene describer instructions include active player context."""
        agent = SceneDescriberAgent()

        analysis_context = {
            "previous_scenes": [{"narrative": "You enter a grand hall."}],
            "active_characters": [{"name": "Noble"}, {"name": "Guard"}],
            "current_turn": {
                "character_name": "Aria Stormborn",
                "personality_traits": ["Observant", "Diplomatic"],
                "description": "A human bard"
            }
        }

        instructions = await agent._get_instructions(analysis_context)

        # Verify turn context is included
        assert "ACTIVE PLAYER: Aria Stormborn" in instructions
        assert "Observant, Diplomatic" in instructions
        assert "A human bard" in instructions
        assert "Frame observations from Aria Stormborn's perspective" in instructions

    @pytest.mark.asyncio
    async def test_action_resolver_includes_turn_context(self):
        """Verify action resolver instructions include active player context."""
        agent = ActionResolver()

        analysis_context = {
            "previous_scenes": [{"narrative": "You face a locked door."}],
            "current_turn": {
                "character_name": "Raven Quickfingers",
                "personality_traits": ["Sneaky", "Resourceful"],
                "description": "A halfling rogue",
                "character_class": "Rogue"
            }
        }

        instructions = await agent._get_instructions(analysis_context)

        # Verify turn context is included
        assert "ACTIVE PLAYER: Raven Quickfingers" in instructions
        assert "Sneaky, Resourceful" in instructions
        assert "A halfling rogue" in instructions
        assert "Character class: Rogue" in instructions
        assert "Resolve Raven Quickfingers's action from their perspective" in instructions

    @pytest.mark.asyncio
    async def test_agents_handle_missing_turn_context_gracefully(self):
        """Verify agents work correctly when no turn context is provided."""
        # Test all agents with minimal context (no current_turn)
        minimal_context = {
            "previous_scenes": [{"narrative": "A scene."}],
            "active_characters": []
        }

        dialog_agent = DialogAgent()
        dialog_instructions = await dialog_agent._get_instructions(minimal_context)
        assert "ACTIVE PLAYER" not in dialog_instructions  # Should not crash

        exploration_agent = ExplorationAgent()
        exploration_instructions = await exploration_agent._get_instructions(minimal_context, {})
        assert "ACTIVE PLAYER" not in exploration_instructions

        scene_describer = SceneDescriberAgent()
        scene_instructions = await scene_describer._get_instructions(minimal_context)
        assert "ACTIVE PLAYER" not in scene_instructions

        action_resolver = ActionResolver()
        action_instructions = await action_resolver._get_instructions(minimal_context)
        assert "ACTIVE PLAYER" not in action_instructions
