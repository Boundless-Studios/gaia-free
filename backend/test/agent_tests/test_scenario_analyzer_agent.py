"""Tests for ScenarioAnalyzer agent configuration, hooks, and internal methods."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

# Import the actual ScenarioAnalyzer agent
from gaia_private.agents.utility.scenario_analyzer import (
    ScenarioAnalyzerAgent,
    ScenarioAnalyzerHooks
)
from gaia.engine.game_configuration import GAME_CONFIGS, GameStyle, GameConfiguration
from gaia.infra.llm.model_manager import ModelName
from agents import Agent

class TestScenarioAnalyzerHooksIntegration:
    """Test ScenarioAnalyzer agent hooks integration - verify hooks are configured and called."""
    
    @pytest.fixture
    def scenario_analyzer_agent(self):
        """Create ScenarioAnalyzer agent instance."""
        return ScenarioAnalyzerAgent()
    
    @pytest.fixture
    def mock_hooks(self):
        """Create mock hooks for testing."""
        hooks = Mock(spec=ScenarioAnalyzerHooks)
        hooks.on_end = AsyncMock()
        return hooks
    
    def test_agent_configured_with_hooks(self, scenario_analyzer_agent):
        """Test that the ScenarioAnalyzer agent is configured with hooks."""
        agent = scenario_analyzer_agent.as_openai_agent()
        
        # Verify hooks are configured
        assert hasattr(agent, 'hooks')
        assert isinstance(agent.hooks, ScenarioAnalyzerHooks)
        
        # Verify hooks have the expected methods
        assert hasattr(agent.hooks, 'on_end')
        assert callable(agent.hooks.on_end)


class TestScenarioAnalyzerAgentIntegration:
    """Test ScenarioAnalyzer agent integration with hooks."""
    
    @pytest.fixture
    def scenario_analyzer_agent(self):
        """Create ScenarioAnalyzer agent instance."""
        return ScenarioAnalyzerAgent()
    
    @pytest.fixture
    def mock_hooks(self):
        """Create mock hooks for testing."""
        hooks = Mock(spec=ScenarioAnalyzerHooks)
        hooks.on_end = AsyncMock()
        return hooks
    
    def test_agent_has_hooks_configured(self, scenario_analyzer_agent):
        """Test that the agent has hooks configured."""
        agent = scenario_analyzer_agent.as_openai_agent()
        assert hasattr(agent, 'hooks')
        assert isinstance(agent.hooks, ScenarioAnalyzerHooks)
    
    def test_agent_configuration_completeness(self, scenario_analyzer_agent):
        """Test that the agent has all required configurations."""
        agent = scenario_analyzer_agent.as_openai_agent()
        
        # Check required attributes
        assert hasattr(agent, 'name')
        assert hasattr(agent, 'instructions')
        assert hasattr(agent, 'model')
        assert hasattr(agent, 'tools')
        assert hasattr(agent, 'hooks')
        
        # Check that hooks are properly configured
        assert isinstance(agent.hooks, ScenarioAnalyzerHooks)
        
        # Check that tools are properly configured (should be empty for scenario analyzer)
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0
    
    def test_agent_tools_configured(self, scenario_analyzer_agent):
        """Test that the agent has the expected tools configured."""
        agent = scenario_analyzer_agent.as_openai_agent()
        
        # Check that tools are configured (should be empty for scenario analyzer)
        assert hasattr(agent, 'tools')
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0  # ScenarioAnalyzer has no tools
    
    def test_agent_model_settings_configured(self, scenario_analyzer_agent):
        """Test that the agent has proper model settings configured."""
        agent = scenario_analyzer_agent.as_openai_agent()
        
        # Check that model settings are configured
        assert hasattr(agent, 'model_settings')
        assert agent.model_settings is not None
        
        # Check specific settings
        assert hasattr(agent.model_settings, 'temperature')
        
        # Verify expected values
        assert agent.model_settings.temperature == 0.3
    
    def test_agent_name_and_description(self, scenario_analyzer_agent):
        """Test that the agent has correct name and description."""
        agent_instance = scenario_analyzer_agent
        assert agent_instance.name == "Scenario Analyzer"
        assert agent_instance.description == "Analyzes player input to determine complexity, relevant mechanics, and optimal approach"
    
    def test_agent_model_default(self, scenario_analyzer_agent):
        """Test that the agent has a valid model configured."""
        agent_instance = scenario_analyzer_agent
        # Check that model is configured (non-empty)
        assert agent_instance.model
        assert isinstance(agent_instance.model, str)
        # Check that model is valid (exists in ModelName enum)
        assert ModelName.from_string(agent_instance.model) is not None
    
    def test_agent_system_prompt(self, scenario_analyzer_agent):
        """Test that the agent has a system prompt configured."""
        agent_instance = scenario_analyzer_agent
        assert hasattr(agent_instance, 'system_prompt')
        assert isinstance(agent_instance.system_prompt, str)
        assert len(agent_instance.system_prompt) > 0
        
        # Check for key content in system prompt
        prompt = agent_instance.system_prompt
        assert "complexity" in prompt.lower()
        assert "analyze" in prompt.lower()
        assert "json" in prompt.lower()
    
    def test_agent_current_game_config_default(self, scenario_analyzer_agent):
        """Test that the agent has correct default game configuration."""
        agent_instance = scenario_analyzer_agent
        assert hasattr(agent_instance, 'current_game_config')
        assert isinstance(agent_instance.current_game_config, GameConfiguration)
        assert agent_instance.current_game_config.style == GameStyle.BALANCED
    
    def test_agent_ruling_cache_default(self, scenario_analyzer_agent):
        """Test that the agent has correct default ruling cache."""
        agent_instance = scenario_analyzer_agent
        assert hasattr(agent_instance, 'ruling_cache')
        assert isinstance(agent_instance.ruling_cache, dict)
        assert len(agent_instance.ruling_cache) == 0
    
    def test_agent_tool_use_behavior(self, scenario_analyzer_agent):
        """Test that the agent has proper tool use behavior configured."""
        agent = scenario_analyzer_agent.as_openai_agent()
        
        # Check tool use behavior
        assert hasattr(agent, 'tool_use_behavior')
        assert agent.tool_use_behavior == "run_llm_again"


class TestScenarioAnalyzerSelectGameConfig:
    """Test the _select_game_config method functionality."""
    
    @pytest.fixture
    def scenario_analyzer_agent(self):
        """Create ScenarioAnalyzer agent instance."""
        return ScenarioAnalyzerAgent()
    
    def test_select_game_config_default_balanced(self, scenario_analyzer_agent):
        """Test that _select_game_config returns balanced config by default."""
        analysis = {
            "game_style_recommendation": "balanced",
            "complexity_score": 5
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result.style == GameStyle.BALANCED
        assert result == scenario_analyzer_agent.current_game_config
    
    def test_select_game_config_tutorial_with_new_player(self, scenario_analyzer_agent):
        """Test that _select_game_config returns tutorial config for new players."""
        analysis = {
            "game_style_recommendation": "tutorial",
            "complexity_score": 2,
            "special_considerations": ["new player", "learning rules"]
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result.style == GameStyle.TUTORIAL
        assert result != scenario_analyzer_agent.current_game_config
    
    def test_select_game_config_tutorial_without_new_player(self, scenario_analyzer_agent):
        """Test that _select_game_config returns current config for tutorial without new player."""
        analysis = {
            "game_style_recommendation": "tutorial",
            "complexity_score": 2,
            "special_considerations": ["experienced player"]
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
    
    def test_select_game_config_cinematic_high_complexity(self, scenario_analyzer_agent):
        """Test that _select_game_config returns modified cinematic config for high complexity."""
        analysis = {
            "game_style_recommendation": "cinematic",
            "complexity_score": 9  # High complexity
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result.style == GameStyle.CINEMATIC
        assert result != scenario_analyzer_agent.current_game_config
        
        # Check that rule_strictness was increased (but capped at 0.5)
        original_cinematic = GAME_CONFIGS[GameStyle.CINEMATIC]
        assert result.rule_strictness == min(0.5, original_cinematic.rule_strictness + 0.3)
    
    def test_select_game_config_cinematic_low_complexity(self, scenario_analyzer_agent):
        """Test that _select_game_config returns current config for low complexity cinematic."""
        analysis = {
            "game_style_recommendation": "cinematic",
            "complexity_score": 3  # Low complexity
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
    
    def test_select_game_config_tactical_style(self, scenario_analyzer_agent):
        """Test that _select_game_config returns current config for tactical style."""
        analysis = {
            "game_style_recommendation": "tactical",
            "complexity_score": 6
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
    
    def test_select_game_config_narrative_style(self, scenario_analyzer_agent):
        """Test that _select_game_config returns current config for narrative style."""
        analysis = {
            "game_style_recommendation": "narrative",
            "complexity_score": 4
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
    
    def test_select_game_config_missing_recommendation(self, scenario_analyzer_agent):
        """Test that _select_game_config handles missing game_style_recommendation."""
        analysis = {
            "complexity_score": 5
            # Missing game_style_recommendation
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
    
    def test_select_game_config_missing_complexity_score(self, scenario_analyzer_agent):
        """Test that _select_game_config handles missing complexity_score."""
        analysis = {
            "game_style_recommendation": "cinematic"
            # Missing complexity_score
        }
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
    
    def test_select_game_config_empty_analysis(self, scenario_analyzer_agent):
        """Test that _select_game_config handles empty analysis."""
        analysis = {}
        
        result = scenario_analyzer_agent._select_game_config(analysis)
        
        assert isinstance(result, GameConfiguration)
        assert result == scenario_analyzer_agent.current_game_config  # Should return current config
        
        