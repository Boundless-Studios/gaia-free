"""
Unit tests for PlayerOptionsService and player options flow.

Tests:
1. Service generates different options for active vs passive players
2. Options are correctly returned with proper structure
3. Error handling for individual player failures
"""

import pytest
import pytest_asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from gaia.services.player_options_service import (
    PlayerOptionsService,
    ObservationsManager,
    get_observations_manager,
)
from gaia.models.connected_player import ConnectedPlayer
from gaia.models.character_options import CharacterOptions
from gaia.models.personalized_player_options import PersonalizedPlayerOptions
from gaia.models.player_observation import PlayerObservation
from gaia.models.pending_observations import PendingObservations

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_active_agent():
    """Mock ActivePlayerOptionsAgent that returns action-oriented options."""
    agent = AsyncMock()
    agent.generate_options = AsyncMock(return_value={
        "player_options": [
            "Attack the goblin with your sword",
            "Cast fireball at the enemies",
            "Dodge behind the pillar",
            "Search for hidden traps",
            "Rally your companions"
        ]
    })
    return agent


@pytest.fixture
def mock_passive_agent():
    """Mock ObservingPlayerOptionsAgent that returns observation-focused options."""
    agent = AsyncMock()
    agent.generate_options = AsyncMock(return_value={
        "player_options": [
            "You notice the goblin seems tired",
            "Something about the shadows seems off",
            "The air feels charged with magic",
            "Your ally's stance suggests they're ready to act",
            "A faint scratching sound comes from the walls"
        ]
    })
    return agent


@pytest.fixture
def connected_players():
    """Create a list of connected players for testing."""
    return [
        ConnectedPlayer(
            character_id="char_active",
            character_name="Aragorn",
            user_id="user_1",
            seat_id="seat_1",
            is_dm=False
        ),
        ConnectedPlayer(
            character_id="char_passive_1",
            character_name="Legolas",
            user_id="user_2",
            seat_id="seat_2",
            is_dm=False
        ),
        ConnectedPlayer(
            character_id="char_passive_2",
            character_name="Gimli",
            user_id="user_3",
            seat_id="seat_3",
            is_dm=False
        ),
        ConnectedPlayer(
            character_id="char_dm",
            character_name="Dungeon Master",
            user_id="user_dm",
            seat_id="seat_dm",
            is_dm=True  # Should be filtered out
        ),
    ]


# =============================================================================
# UNIT TESTS - PlayerOptionsService
# =============================================================================

class TestPlayerOptionsService:
    """Unit tests for PlayerOptionsService."""

    @pytest.mark.unit
    async def test_generates_different_options_for_active_vs_passive(
        self,
        mock_active_agent,
        mock_passive_agent,
        connected_players
    ):
        """Test that active and passive players get different types of options."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent

            result = await service.generate_all_player_options(
                connected_players=connected_players,
                active_character_id="char_active",
                scene_narrative="The goblin charges forward!",
                previous_char_name="Gandalf",
            )

            # Verify structure
            assert isinstance(result, PersonalizedPlayerOptions)
            assert result.active_character_id == "char_active"

            # Should have 3 characters (DM filtered out)
            assert len(result.characters) == 3

            # Active player should get action-oriented options
            active_opts = result.characters["char_active"]
            assert active_opts.is_active is True
            assert "Attack" in active_opts.options[0] or "Cast" in active_opts.options[1]

            # Passive players should get observation options
            passive_1_opts = result.characters["char_passive_1"]
            assert passive_1_opts.is_active is False
            assert "notice" in passive_1_opts.options[0] or "seems" in passive_1_opts.options[1]

            passive_2_opts = result.characters["char_passive_2"]
            assert passive_2_opts.is_active is False

            logger.info("✅ Different options generated for active vs passive players")

    @pytest.mark.unit
    async def test_active_agent_called_for_turn_taker(
        self,
        mock_active_agent,
        mock_passive_agent,
        connected_players
    ):
        """Test that ActivePlayerOptionsAgent is used for the turn-taking player."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent

            await service.generate_all_player_options(
                connected_players=connected_players,
                active_character_id="char_active",
                scene_narrative="The dragon roars!",
                previous_char_name="Gandalf"
            )

            # Active agent should be called once (for the active player)
            assert mock_active_agent.generate_options.call_count == 1

            # Passive agent should be called twice (for the two passive players)
            assert mock_passive_agent.generate_options.call_count == 2

            # Verify active agent was called with correct character
            active_call = mock_active_agent.generate_options.call_args
            assert active_call.kwargs["next_char_name"] == "Aragorn"

            logger.info("✅ Correct agent called for each player type")

    @pytest.mark.unit
    async def test_dm_filtered_from_options_generation(
        self,
        mock_active_agent,
        mock_passive_agent,
        connected_players
    ):
        """Test that DM character is filtered out from options generation."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent

            result = await service.generate_all_player_options(
                connected_players=connected_players,
                active_character_id="char_active",
                scene_narrative="Combat begins!",
                previous_char_name="Gandalf"
            )

            # DM should not be in the results
            assert "char_dm" not in result.characters
            assert len(result.characters) == 3

            logger.info("✅ DM correctly filtered from options generation")

    @pytest.mark.unit
    async def test_handles_individual_player_failure(
        self,
        mock_active_agent,
        mock_passive_agent,
        connected_players
    ):
        """Test that failure for one player doesn't affect others."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent

            call_count = 0
            async def sometimes_fail(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 2:  # Fail on second call
                    raise Exception("Agent error")
                return {"player_options": ["Option 1"]}

            mock_passive_agent.generate_options = AsyncMock(side_effect=sometimes_fail)

            result = await service.generate_all_player_options(
                connected_players=connected_players,
                active_character_id="char_active",
                scene_narrative="Test failure handling",
                previous_char_name="Gandalf",
            )

            # Should still have results for all players
            assert len(result.characters) == 3

            # One player should have empty options due to failure
            empty_count = sum(1 for c in result.characters.values() if len(c.options) == 0)
            assert empty_count == 1

            logger.info("✅ Individual player failure handled gracefully")

    @pytest.mark.unit
    async def test_empty_player_list_returns_empty_result(self, mock_active_agent, mock_passive_agent):
        """Test that empty player list returns empty result."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent

            result = await service.generate_all_player_options(
                connected_players=[],
                active_character_id="char_1",
                scene_narrative="Test",
                previous_char_name="Gandalf"
            )

            assert len(result.characters) == 0

            logger.info("✅ Empty player list handled correctly")

    @pytest.mark.unit
    async def test_generate_active_player_options_only(
        self,
        mock_active_agent,
        mock_passive_agent
    ):
        """Test generating options for just the active player."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent

            result = await service.generate_active_player_options_only(
                active_character_id="char_1",
                active_character_name="Aragorn",
                scene_narrative="The battle begins!",
                previous_char_name="Gandalf",
                character_context="A skilled ranger"
            )

            assert isinstance(result, CharacterOptions)
            assert result.character_id == "char_1"
            assert result.character_name == "Aragorn"
            assert result.is_active is True
            assert len(result.options) > 0

            # Only active agent should be called
            assert mock_active_agent.generate_options.call_count == 1
            assert mock_passive_agent.generate_options.call_count == 0

            logger.info("✅ Active player only generation works")


# =============================================================================
# UNIT TESTS - Data Models
# =============================================================================

class TestPlayerOptionsModels:
    """Unit tests for player options data models."""

    @pytest.mark.unit
    def test_personalized_options_structure(self):
        """Test PersonalizedPlayerOptions structure and methods."""
        options = PersonalizedPlayerOptions(
            active_character_id="char_1",
            scene_narrative="Test narrative",
            generated_at=datetime.now()
        )

        options.add_character_options(
            character_id="char_1",
            character_name="Hero",
            options=["Attack", "Defend"],
            is_active=True
        )

        options.add_character_options(
            character_id="char_2",
            character_name="Sidekick",
            options=["Observe", "Wait"],
            is_active=False
        )

        # Test retrieval
        assert options.get_options_for_character("char_1") is not None
        assert options.get_options_for_character("char_1").is_active is True
        assert options.get_active_character_options().character_name == "Hero"

        # Test legacy format
        legacy = options.to_legacy_format()
        assert legacy == ["Attack", "Defend"]

        legacy_char_2 = options.to_legacy_format("char_2")
        assert legacy_char_2 == ["Observe", "Wait"]

        logger.info("✅ PersonalizedPlayerOptions model works correctly")

    @pytest.mark.unit
    def test_character_options_serialization(self):
        """Test CharacterOptions to_dict and from_dict."""
        original = CharacterOptions(
            character_id="char_1",
            character_name="Hero",
            options=["Option 1", "Option 2"],
            is_active=True,
            generated_at=datetime.now()
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = CharacterOptions.from_dict(data)

        assert restored.character_id == original.character_id
        assert restored.character_name == original.character_name
        assert restored.options == original.options
        assert restored.is_active == original.is_active

        logger.info("✅ CharacterOptions serialization works")


# =============================================================================
# UNIT TESTS - ObservationsManager
# =============================================================================

class TestObservationsManager:
    """Unit tests for ObservationsManager."""

    @pytest.mark.unit
    def test_add_and_retrieve_observations(self):
        """Test adding and retrieving observations."""
        manager = ObservationsManager()

        obs = manager.add_observation(
            session_id="session_1",
            primary_character_id="char_active",
            primary_character_name="Aragorn",
            observer_character_id="char_observer",
            observer_character_name="Legolas",
            observation_text="I notice the enemy flanking"
        )

        assert obs.character_name == "Legolas"
        assert obs.included_in_turn is False

        pending = manager.get_pending_observations("session_1")
        assert pending is not None
        assert len(pending.observations) == 1

        logger.info("✅ ObservationsManager add/retrieve works")

    @pytest.mark.unit
    def test_format_observations_for_submission(self):
        """Test formatting observations for primary player's submission."""
        manager = ObservationsManager()

        manager.add_observation(
            session_id="session_1",
            primary_character_id="char_active",
            primary_character_name="Aragorn",
            observer_character_id="char_1",
            observer_character_name="Legolas",
            observation_text="Enemy on the left"
        )

        manager.add_observation(
            session_id="session_1",
            primary_character_id="char_active",
            primary_character_name="Aragorn",
            observer_character_id="char_2",
            observer_character_name="Gimli",
            observation_text="Dwarf ready to charge"
        )

        formatted = manager.format_observations_for_submission("session_1")

        assert "[Legolas observes]: Enemy on the left" in formatted
        assert "[Gimli observes]: Dwarf ready to charge" in formatted

        logger.info("✅ Observation formatting works")

    @pytest.mark.unit
    def test_mark_observations_included(self):
        """Test marking observations as included."""
        manager = ObservationsManager()

        manager.add_observation(
            session_id="session_1",
            primary_character_id="char_active",
            primary_character_name="Aragorn",
            observer_character_id="char_1",
            observer_character_name="Legolas",
            observation_text="Test observation"
        )

        # Mark all as included
        manager.mark_all_included("session_1")

        unincluded = manager.get_unincluded_observations("session_1")
        assert len(unincluded) == 0

        logger.info("✅ Observation marking works")

    @pytest.mark.unit
    def test_global_observations_manager(self):
        """Test global observations manager singleton."""
        manager1 = get_observations_manager()
        manager2 = get_observations_manager()

        assert manager1 is manager2

        logger.info("✅ Global observations manager singleton works")


class TestGenerateOptionsDict:
    """Unit tests for generate_options_dict method."""

    @pytest.mark.unit
    async def test_generate_options_dict_returns_dict(
        self,
        mock_active_agent,
        mock_passive_agent
    ):
        """Test that generate_options_dict returns a dict from PersonalizedPlayerOptions.to_dict()."""
        # Mock get_connected_players_from_campaign
        mock_players = [
            ConnectedPlayer(
                character_id="char_1",
                character_name="Hero",
                user_id="user_1",
                seat_id="seat_1",
                is_dm=False
            )
        ]

        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent
            service.get_scene_player_characters = MagicMock(return_value=mock_players)

            structured_data = {
                "narrative": "The adventure begins!",
                "turn_info": {
                    "active_character_id": "char_1",
                    "previous_character_name": "Gandalf"
                }
            }

            result = await service.generate_options_dict(
                campaign_id="test_campaign",
                structured_data=structured_data
            )

            assert result is not None
            assert isinstance(result, dict)
            assert result["active_character_id"] == "char_1"
            assert "char_1" in result["characters"]
            assert result["characters"]["char_1"]["is_active"] is True

            logger.info("✅ generate_options_dict returns correct dict structure")

    @pytest.mark.unit
    async def test_generate_options_dict_no_players_returns_none(
        self,
        mock_active_agent,
        mock_passive_agent
    ):
        """Test that generate_options_dict returns None when no players found."""
        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent
            service.get_scene_player_characters = MagicMock(return_value=[])

            result = await service.generate_options_dict(
                campaign_id="test_campaign",
                structured_data={"narrative": "Test"}
            )

            assert result is None

            logger.info("✅ generate_options_dict returns None for no players")

    @pytest.mark.unit
    async def test_generate_options_dict_no_narrative_returns_none(
        self,
        mock_active_agent,
        mock_passive_agent
    ):
        """Test that generate_options_dict returns None when no narrative."""
        mock_players = [
            ConnectedPlayer(
                character_id="char_1",
                character_name="Hero",
                user_id="user_1",
                seat_id="seat_1",
                is_dm=False
            )
        ]

        with patch.object(PlayerOptionsService, '__init__', lambda self: None):
            service = PlayerOptionsService()
            service._active_agent = mock_active_agent
            service._passive_agent = mock_passive_agent
            service.get_scene_player_characters = MagicMock(return_value=mock_players)

            result = await service.generate_options_dict(
                campaign_id="test_campaign",
                structured_data={}  # No narrative
            )

            assert result is None

            logger.info("✅ generate_options_dict returns None for no narrative")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])
