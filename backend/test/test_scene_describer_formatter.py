"""Tests for scene describer response formatting."""
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaia_private.orchestration.smart_router import SmartAgentRouter


class TestSceneDescriberFormatter:
    """Test the scene describer response formatter."""

    @pytest.mark.asyncio
    async def test_format_with_observations(self):
        """Should format summary + observations without redundancy."""
        # Mock campaign runner with minimal setup
        from unittest.mock import Mock, AsyncMock

        class MockCampaignRunner:
            context_manager = None
            character_manager = None
            history_manager = None
            parallel_analyzer = None
            player_options_agent = AsyncMock()

            def __init__(self):
                # Add services mock
                self.services = Mock()
                self.services.context_manager = None
                self.services.turn_manager = None
                # Mock player options agent to avoid errors
                self.player_options_agent.generate_options = AsyncMock(return_value={'player_options': []})

        router = SmartAgentRouter(MockCampaignRunner())
        # Bypass initialization that requires parallel_analyzer
        router.last_parallel_analysis = None

        # Mock agent response
        agent_response = {
            "summary": "The tavern is lit by flickering candlelight, casting dancing shadows across the wooden tables.",
            "observations": [
                {
                    "description": "The lighting in the room",
                    "observation_type": "visual",
                    "difficulty_class": 5,
                    "roll": 12,
                    "success": True,
                    "margin": 7,
                    "flavor": "The warm candlelight illuminates the room, casting dancing shadows on the walls.",
                    "include": True
                },
                {
                    "description": "A cloaked figure in the corner",
                    "observation_type": "visual",
                    "difficulty_class": 12,
                    "roll": 20,
                    "success": True,
                    "margin": 8,
                    "flavor": "Your sharp perception immediately catches the intense gaze of a cloaked figure!",
                    "include": True
                },
                {
                    "description": "A faint scent in the air",
                    "observation_type": "olfactory",
                    "difficulty_class": 10,
                    "roll": 9,
                    "success": False,
                    "margin": -1,
                    "flavor": "A scent tickles at your nose briefly, but you can't quite place it.",
                    "include": True
                }
            ]
        }

        # Format the response
        formatted = await router._format_scene_response(
            agent_response,
            "scene_describer",
            "test_campaign_id",
            {}
        )

        answer = formatted["structured_data"]["answer"]

        # Verify structure
        assert "The tavern is lit by flickering candlelight" in answer
        assert "━" in answer  # Separator
        assert "Perception Checks:" in answer

        # Verify observations use description (not flavor)
        assert "✓ The lighting in the room [Roll: 12 vs DC 5]" in answer
        assert "✓ A cloaked figure in the corner [Roll: 20 vs DC 12]" in answer
        assert "≈ A faint scent in the air [Roll: 9 vs DC 10]" in answer

        # Verify flavor text is NOT duplicated in observations
        assert "warm candlelight illuminates the room" not in answer.split("Perception Checks:")[1]
        assert "sharp perception immediately catches" not in answer.split("Perception Checks:")[1]

        print("\n--- Formatted Output ---")
        print(answer)

    @pytest.mark.asyncio
    async def test_format_without_observations(self):
        """Should return only summary when no observations included."""
        from unittest.mock import Mock, AsyncMock

        class MockCampaignRunner:
            context_manager = None
            character_manager = None
            history_manager = None
            parallel_analyzer = None
            player_options_agent = AsyncMock()

            def __init__(self):
                # Add services mock
                self.services = Mock()
                self.services.context_manager = None
                self.services.turn_manager = None
                self.player_options_agent.generate_options = AsyncMock(return_value={'player_options': []})

        router = SmartAgentRouter(MockCampaignRunner())
        router.last_parallel_analysis = None

        agent_response = {
            "summary": "You observe the scene around you.",
            "observations": []
        }

        formatted = await router._format_scene_response(
            agent_response,
            "scene_describer",
            "test_campaign_id",
            {}
        )

        answer = formatted["structured_data"]["answer"]

        # Should only have summary
        assert answer == "You observe the scene around you."
        assert "━" not in answer
        assert "Perception Checks:" not in answer

    @pytest.mark.asyncio
    async def test_format_filters_clear_failures(self):
        """Should exclude clear failures (include=False)."""
        from unittest.mock import Mock, AsyncMock

        class MockCampaignRunner:
            context_manager = None
            character_manager = None
            history_manager = None
            parallel_analyzer = None
            player_options_agent = AsyncMock()

            def __init__(self):
                # Add services mock
                self.services = Mock()
                self.services.context_manager = None
                self.services.turn_manager = None
                self.player_options_agent.generate_options = AsyncMock(return_value={'player_options': []})

        router = SmartAgentRouter(MockCampaignRunner())
        router.last_parallel_analysis = None

        agent_response = {
            "summary": "You scan the area carefully.",
            "observations": [
                {
                    "description": "Something obvious",
                    "difficulty_class": 5,
                    "roll": 15,
                    "success": True,
                    "margin": 10,
                    "flavor": "You notice it clearly.",
                    "include": True
                },
                {
                    "description": "Something hidden",
                    "difficulty_class": 20,
                    "roll": 10,
                    "success": False,
                    "margin": -10,
                    "flavor": "",
                    "include": False  # Clear failure - should be excluded
                }
            ]
        }

        formatted = await router._format_scene_response(
            agent_response,
            "scene_describer",
            "test_campaign_id",
            {}
        )

        answer = formatted["structured_data"]["answer"]

        # Should include success
        assert "✓ Something obvious [Roll: 15 vs DC 5]" in answer

        # Should NOT include clear failure
        assert "Something hidden" not in answer
        assert "Roll: 10 vs DC 20" not in answer


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
