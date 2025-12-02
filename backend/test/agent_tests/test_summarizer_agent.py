"""Tests for Summarizer agent configuration and hooks."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Import the actual Summarizer agent
from gaia_private.agents.utility.summarizer import (
    SummarizerAgent,
    SummarizerHooks
)
from gaia.infra.llm.model_manager import ModelName
from agents import Agent

class TestSummarizerHooksIntegration:
    """Test Summarizer agent hooks integration - verify hooks are configured and called."""
    
    @pytest.fixture
    def summarizer_agent(self):
        """Create Summarizer agent instance."""
        return SummarizerAgent()
    
    @pytest.fixture
    def mock_hooks(self):
        """Create mock hooks for testing."""
        hooks = Mock(spec=SummarizerHooks)
        hooks.on_end = AsyncMock()
        return hooks
    
    def test_agent_configured_with_hooks(self, summarizer_agent):
        """Test that the Summarizer agent is configured with hooks."""
        agent = summarizer_agent.as_openai_agent()
        
        # Verify hooks are configured
        assert hasattr(agent, 'hooks')
        assert isinstance(agent.hooks, SummarizerHooks)
        
        # Verify hooks have the expected methods
        assert hasattr(agent.hooks, 'on_end')
        assert callable(agent.hooks.on_end)


class TestSummarizerAgentIntegration:
    """Test Summarizer agent integration with hooks."""
    
    @pytest.fixture
    def summarizer_agent(self):
        """Create Summarizer agent instance."""
        return SummarizerAgent()
    
    @pytest.fixture
    def mock_hooks(self):
        """Create mock hooks for testing."""
        hooks = Mock(spec=SummarizerHooks)
        hooks.on_end = AsyncMock()
        return hooks
    
    def test_agent_has_hooks_configured(self, summarizer_agent):
        """Test that the agent has hooks configured."""
        agent = summarizer_agent.as_openai_agent()
        assert hasattr(agent, 'hooks')
        assert isinstance(agent.hooks, SummarizerHooks)
    
    def test_agent_configuration_completeness(self, summarizer_agent):
        """Test that the agent has all required configurations."""
        agent = summarizer_agent.as_openai_agent()
        
        # Check required attributes
        assert hasattr(agent, 'name')
        assert hasattr(agent, 'instructions')
        assert hasattr(agent, 'model')
        assert hasattr(agent, 'tools')
        assert hasattr(agent, 'hooks')
        
        # Check that hooks are properly configured
        assert isinstance(agent.hooks, SummarizerHooks)
        
        # Check that tools are properly configured (should be empty for summarizer)
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0
    
    def test_agent_tools_configured(self, summarizer_agent):
        """Test that the agent has the expected tools configured."""
        agent = summarizer_agent.as_openai_agent()
        
        # Check that tools are configured (should be empty for summarizer)
        assert hasattr(agent, 'tools')
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0  # Summarizer has no tools
    
    def test_agent_model_settings_configured(self, summarizer_agent):
        """Test that the agent has proper model settings configured."""
        agent = summarizer_agent.as_openai_agent()
        
        # Check that model settings are configured
        assert hasattr(agent, 'model_settings')
        assert agent.model_settings is not None
        
        # Check specific settings
        assert hasattr(agent.model_settings, 'temperature')

        # Verify temperature is set to a reasonable value
        assert 0.0 <= agent.model_settings.temperature <= 1.0
    
    def test_agent_name_and_description(self, summarizer_agent):
        """Test that the agent has correct name and description."""
        agent_instance = summarizer_agent
        assert agent_instance.name == "Campaign Summarizer"
        # Check description contains key elements (not exact match to avoid brittleness)
        desc = agent_instance.description
        assert "summaries" in desc.lower()
        assert "campaign" in desc.lower()
        assert "narrative" in desc.lower()
    
    def test_agent_model_default(self, summarizer_agent):
        """Test that the agent has a valid model configured."""
        agent_instance = summarizer_agent
        # Check that model is configured (non-empty)
        assert agent_instance.model
        assert isinstance(agent_instance.model, str)
        # Check that model is valid (exists in ModelName enum)
        assert ModelName.from_string(agent_instance.model) is not None
    
    def test_agent_system_prompt(self, summarizer_agent):
        """Test that the agent has a system prompt configured."""
        agent_instance = summarizer_agent
        assert hasattr(agent_instance, 'system_prompt')
        assert isinstance(agent_instance.system_prompt, str)
        assert len(agent_instance.system_prompt) > 0
        
        # Check for key content in system prompt
        prompt = agent_instance.system_prompt
        assert "summarize" in prompt.lower()
        assert "conversation" in prompt.lower()
        assert "json" in prompt.lower()
    
    def test_agent_tool_use_behavior(self, summarizer_agent):
        """Test that the agent has proper tool use behavior configured."""
        agent = summarizer_agent.as_openai_agent()
        
        # Check tool use behavior
        assert hasattr(agent, 'tool_use_behavior')
        assert agent.tool_use_behavior == "run_llm_again"
    
    @pytest.mark.asyncio
    async def test_hooks_logging_behavior(self, summarizer_agent):
        """Test that hooks properly log summarization output."""
        # Create agent with real hooks
        agent = summarizer_agent.as_openai_agent()
        
        # Mock logging to capture log messages
        with patch('gaia_private.agents.utility.summarizer.logging.getLogger') as mock_logger:
            mock_logger_instance = Mock()
            mock_logger.return_value = mock_logger_instance
            
            # Test the on_end hook directly
            context = {"test": "context"}
            mock_agent = Mock()
            output = '{"summary": "Players completed the quest", "key_events": ["victory"]}'
            
            await agent.hooks.on_end(context, mock_agent, output)
            
            # Verify logging calls were made
            mock_logger.assert_called()
            mock_logger_instance.info.assert_called()
            
            # Check that info messages contain expected content
            info_calls = mock_logger_instance.info.call_args_list
            info_messages = [call[0][0] for call in info_calls]
            assert any("Summarizer" in msg for msg in info_messages)
            assert any("Agent execution ended" in msg for msg in info_messages) 