"""Tests for SceneCreator PC/NPC context extraction."""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from gaia_private.agents.generators.scene_creator import (
    SceneCreatorAgent,
    SceneCreatorHooks
)
from gaia.models.scene_info import SceneInfo


@pytest.fixture(autouse=True)
def scene_storage_env(tmp_path, monkeypatch):
    """Ensure scene storage environment variables exist for tests."""
    monkeypatch.setenv("CAMPAIGN_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    yield


class TestSceneCreatorPCNPCContext:
    """Test that SceneCreator properly extracts PC and NPC information from context."""

    @pytest.fixture
    def scene_creator_agent(self):
        """Create SceneCreator agent instance."""
        return SceneCreatorAgent(campaign_id="test-campaign")

    @pytest.mark.asyncio
    async def test_context_pcs_and_npcs_extraction(self, scene_creator_agent):
        """Test that hooks extract PCs and NPCs from context properly."""
        agent = scene_creator_agent.as_openai_agent()

        # Create context with player and NPC data
        context = {
            "campaign_id": "test-campaign",
            "players": [
                {"character_id": "pc:alice", "name": "Alice"},
                {"character_id": "pc:bob", "name": "Bob"}
            ],
            "npcs": [
                {"name": "Goblin Chief", "id": "npc:goblin_chief"},
                {"name": "Guard Captain", "id": "npc:guard"}
            ]
        }

        # Mock output that doesn't specify PCs/NPCs
        output = {
            "title": "The Goblin Ambush",
            "description": "You encounter goblins on the road",
            "scene_type": "combat",
            "location_id": "forest_road"
        }

        mock_agent = Mock()

        await agent.hooks.on_end(context, mock_agent, output)

        # Verify scene_data was created
        assert agent.hooks.scene_data is not None
        assert isinstance(agent.hooks.scene_data, SceneInfo)

        # Verify PCs were extracted from context
        assert agent.hooks.scene_data.pcs_present == ["pc:alice", "pc:bob"]

        # Verify NPCs were extracted from context
        assert "npc:goblin_chief" in agent.hooks.scene_data.npcs_present
        assert "npc:guard" in agent.hooks.scene_data.npcs_present

    @pytest.mark.asyncio
    async def test_context_pcs_override_output(self, scene_creator_agent):
        """Test that context PCs override agent output."""
        agent = scene_creator_agent.as_openai_agent()

        # Context with correct PC data
        context = {
            "campaign_id": "test-campaign",
            "players": [
                {"character_id": "pc:alice", "name": "Alice"},
                {"character_id": "pc:bob", "name": "Bob"}
            ],
            "npcs": []
        }

        # Output that incorrectly lists PCs as NPCs
        output = {
            "title": "The Town Square",
            "description": "You are in the town square",
            "scene_type": "social",
            "location_id": "town_square",
            "npcs": ["Alice", "Bob"],  # WRONG - these should be PCs
            "pcs": []  # WRONG - missing PCs
        }

        mock_agent = Mock()

        await agent.hooks.on_end(context, mock_agent, output)

        # Verify scene_data was created
        assert agent.hooks.scene_data is not None

        # Context should override incorrect output
        assert agent.hooks.scene_data.pcs_present == ["pc:alice", "pc:bob"]
        assert agent.hooks.scene_data.npcs_present == []

    @pytest.mark.asyncio
    async def test_no_fallback_to_output_when_no_context(self, scene_creator_agent):
        """Test that empty context results in empty PC/NPC lists (no fallback to output)."""
        agent = scene_creator_agent.as_openai_agent()

        # Context without player/NPC data
        context = {
            "campaign_id": "test-campaign"
        }

        # Output with PC/NPC data (should be ignored)
        output = {
            "title": "The Inn",
            "description": "You enter the inn",
            "scene_type": "social",
            "location_id": "tavern",
            "pcs_present": ["pc:charlie"],  # Should be ignored
            "npcs_present": ["Innkeeper"]  # Should be ignored
        }

        mock_agent = Mock()

        await agent.hooks.on_end(context, mock_agent, output)

        # Verify scene_data was created
        assert agent.hooks.scene_data is not None

        # Should NOT use output data - context is the only source of truth
        assert agent.hooks.scene_data.pcs_present == []
        assert agent.hooks.scene_data.npcs_present == []

    @pytest.mark.asyncio
    async def test_string_player_ids_in_context(self, scene_creator_agent):
        """Test that string player IDs in context are handled correctly."""
        agent = scene_creator_agent.as_openai_agent()

        # Context with simple string IDs
        context = {
            "campaign_id": "test-campaign",
            "players": ["pc:alice", "pc:bob"],  # Simple strings
            "npcs": ["Goblin", "Orc"]  # Simple strings
        }

        output = {
            "title": "Combat",
            "description": "Battle!",
            "scene_type": "combat"
        }

        mock_agent = Mock()

        await agent.hooks.on_end(context, mock_agent, output)

        # Verify scene_data was created
        assert agent.hooks.scene_data is not None

        # Should handle string IDs correctly
        assert agent.hooks.scene_data.pcs_present == ["pc:alice", "pc:bob"]
        assert agent.hooks.scene_data.npcs_present == ["Goblin", "Orc"]

    @pytest.mark.asyncio
    async def test_empty_context_uses_defaults(self, scene_creator_agent):
        """Test that empty context results in empty PC/NPC lists."""
        agent = scene_creator_agent.as_openai_agent()

        # Empty context
        context = {}

        # String output (no structured data)
        output = "A simple narrative description"

        mock_agent = Mock()

        await agent.hooks.on_end(context, mock_agent, output)

        # Verify scene_data was created
        assert agent.hooks.scene_data is not None

        # Should have empty PC/NPC lists
        assert agent.hooks.scene_data.pcs_present == []
        assert agent.hooks.scene_data.npcs_present == []
