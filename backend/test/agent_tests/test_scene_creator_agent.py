"""Tests for SceneCreator agent configuration and hooks."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Import the actual SceneCreator agent
from gaia_private.agents.generators.scene_creator import (
    SceneCreatorAgent,
    SceneCreatorHooks
)
from gaia.infra.llm.model_manager import ModelName
from agents import Agent
from gaia.models.scene_info import SceneInfo


@pytest.fixture(autouse=True)
def scene_storage_env(tmp_path, monkeypatch):
    """Ensure scene storage environment variables exist for tests."""
    monkeypatch.setenv("CAMPAIGN_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    yield

class TestSceneCreatorHooksIntegration:
    """Test SceneCreator agent hooks integration - verify hooks are configured and called."""
    
    @pytest.fixture
    def scene_creator_agent(self):
        """Create SceneCreator agent instance."""
        return SceneCreatorAgent()
    
    @pytest.fixture
    def mock_hooks(self):
        """Create mock hooks for testing."""
        hooks = Mock(spec=SceneCreatorHooks)
        hooks.on_end = AsyncMock()
        hooks.scene_data = None
        return hooks

    def test_agent_configured_with_hooks(self, scene_creator_agent):
        """Test that the SceneCreator agent is configured with hooks."""
        agent = scene_creator_agent.as_openai_agent()

        # Verify hooks are configured
        assert hasattr(agent, 'hooks')
        assert isinstance(agent.hooks, SceneCreatorHooks)

        # Verify hooks have the expected methods
        assert hasattr(agent.hooks, 'on_end')
        assert callable(agent.hooks.on_end)

        # Verify scene_data attribute exists (for campaign_runner to retrieve)
        assert hasattr(agent.hooks, 'scene_data')

    def test_hooks_scene_data_storage(self, scene_creator_agent):
        """Test that hooks store scene data for campaign_runner retrieval."""
        # Create agent
        agent_instance = SceneCreatorAgent(campaign_id="test-campaign")
        agent = agent_instance.as_openai_agent()

        # Verify hooks have scene_data attribute
        assert hasattr(agent.hooks, 'scene_data')
        assert agent.hooks.scene_data is None  # Initially None


class TestSceneCreatorAgentIntegration:
    """Test SceneCreator agent integration with hooks."""
    
    @pytest.fixture
    def scene_creator_agent(self):
        """Create SceneCreator agent instance."""
        return SceneCreatorAgent()
    
    @pytest.fixture
    def mock_hooks(self):
        """Create mock hooks for testing."""
        hooks = Mock(spec=SceneCreatorHooks)
        hooks.on_end = AsyncMock()
        hooks.scene_data = None
        return hooks

    def test_agent_has_hooks_configured(self, scene_creator_agent):
        """Test that the agent has hooks configured."""
        agent = scene_creator_agent.as_openai_agent()
        assert hasattr(agent, 'hooks')
        assert isinstance(agent.hooks, SceneCreatorHooks)

    def test_agent_configuration_completeness(self, scene_creator_agent):
        """Test that the agent has all required configurations."""
        agent = scene_creator_agent.as_openai_agent()

        # Check required attributes
        assert hasattr(agent, 'name')
        assert hasattr(agent, 'instructions')
        assert hasattr(agent, 'model')
        assert hasattr(agent, 'tools')
        assert hasattr(agent, 'hooks')

        # Check that hooks are properly configured
        assert isinstance(agent.hooks, SceneCreatorHooks)

        # Check that tools are properly configured (should be empty for scene creator)
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0
    
    def test_agent_tools_configured(self, scene_creator_agent):
        """Test that the agent has the expected tools configured."""
        agent = scene_creator_agent.as_openai_agent()
        
        # Check that tools are configured (should be empty for scene creator)
        assert hasattr(agent, 'tools')
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0  # SceneCreator has no tools
    
    def test_agent_model_settings_configured(self, scene_creator_agent):
        """Test that the agent has proper model settings configured."""
        agent = scene_creator_agent.as_openai_agent()
        
        # Check that model settings are configured
        assert hasattr(agent, 'model_settings')
        assert agent.model_settings is not None
        
        # Check specific settings
        assert hasattr(agent.model_settings, 'temperature')

        # Verify temperature is set to a reasonable value
        assert 0.0 <= agent.model_settings.temperature <= 1.0
    
    def test_agent_campaign_id_parameter(self, scene_creator_agent):
        """Test that the agent accepts campaign_id parameter."""
        # Test with default campaign_id
        agent_instance = SceneCreatorAgent()
        assert agent_instance.campaign_id == "default"

        # Test with custom campaign_id
        agent_instance = SceneCreatorAgent(campaign_id="custom-campaign")
        assert agent_instance.campaign_id == "custom-campaign"

        # Verify hooks have scene_data attribute for campaign_runner
        agent = agent_instance.as_openai_agent()
        assert hasattr(agent.hooks, 'scene_data')
    
    def test_agent_name_and_description(self, scene_creator_agent):
        """Test that the agent has correct name and description."""
        agent_instance = scene_creator_agent
        assert agent_instance.name == "Scene Creator"
        assert agent_instance.description == "Creates a scene for a D&D campaign"
    
    def test_agent_model_default(self, scene_creator_agent):
        """Test that the agent has a valid model configured."""
        agent_instance = scene_creator_agent
        # Check that model is configured (non-empty)
        assert agent_instance.model
        assert isinstance(agent_instance.model, str)
        # Check that model is valid (exists in ModelName enum)
        assert ModelName.from_string(agent_instance.model) is not None
    
    def test_agent_system_prompt(self, scene_creator_agent):
        """Test that the agent has a system prompt configured."""
        agent_instance = scene_creator_agent
        assert hasattr(agent_instance, 'system_prompt')
        assert isinstance(agent_instance.system_prompt, str)
        assert len(agent_instance.system_prompt) > 0
    
    @pytest.mark.asyncio
    async def test_hooks_scene_data_preparation(self, scene_creator_agent):
        """Test that hooks properly prepare scene data for campaign_runner."""
        # Create agent with real hooks
        agent = scene_creator_agent.as_openai_agent()

        context = {"test": "context"}
        mock_agent = Mock()
        output = "Test scene output"

        # Initially scene_data should be None
        assert agent.hooks.scene_data is None

        await agent.hooks.on_end(context, mock_agent, output)

        # After on_end, scene_data should be populated
        assert agent.hooks.scene_data is not None
        assert isinstance(agent.hooks.scene_data, SceneInfo)
        assert agent.hooks.scene_data.description == "Test scene output"
        assert agent.hooks.scene_data.metadata["raw_output"] == "Test scene output"
    
    @pytest.mark.asyncio
    async def test_hooks_scene_data_with_pydantic_model(self, scene_creator_agent):
        """Test that hooks properly prepare scene data when output is a Pydantic model."""
        # Create agent with real hooks
        agent = scene_creator_agent.as_openai_agent()

        mock_output = Mock()
        mock_output.model_dump.return_value = {
            "narrative": "Test narrative",
            "characters": "Test characters"
        }

        context = {"test": "context"}
        mock_agent = Mock()

        await agent.hooks.on_end(context, mock_agent, mock_output)

        assert agent.hooks.scene_data is not None
        assert isinstance(agent.hooks.scene_data, SceneInfo)
        assert "Test narrative" in agent.hooks.scene_data.description
        assert agent.hooks.scene_data.metadata["raw_output"] == {
            "narrative": "Test narrative",
            "characters": "Test characters"
        }
    
    @pytest.mark.asyncio
    async def test_hooks_error_handling(self, scene_creator_agent):
        """Test that hooks handle errors gracefully when preparing scene data."""
        # Create agent with real hooks
        agent = scene_creator_agent.as_openai_agent()

        # Mock logging to capture error messages
        with patch('gaia_private.agents.generators.scene_creator.logging.getLogger') as mock_logger:
            mock_logger_instance = Mock()
            mock_logger.return_value = mock_logger_instance

            # Test the on_end hook with invalid output that causes JSON serialization error
            context = {"test": "context"}
            mock_agent = Mock()

            # Create an output that will cause serialization issues
            class BadOutput:
                def __init__(self):
                    self.circular_ref = self

            output = {"bad_data": BadOutput()}

            # Should not raise an exception
            await agent.hooks.on_end(context, mock_agent, output)

            # Verify error was logged (may be called multiple times for error + traceback)
            assert mock_logger_instance.error.called
            # Check that at least one call contains the error message
            error_calls = [str(call) for call in mock_logger_instance.error.call_args_list]
            assert any("Error preparing scene data" in str(call) for call in error_calls) 
