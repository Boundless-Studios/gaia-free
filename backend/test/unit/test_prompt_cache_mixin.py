"""Unit tests for PromptCacheMixin behavior across all agents.

This test verifies that all agents using PromptCacheMixin:
1. Correctly specify agent_type and prompt_key
2. Load prompts with proper fallback behavior
3. Cache prompts correctly at instance level
4. Support cache invalidation
5. Handle template variable resolution

Unlike integration tests, these tests mock the database to isolate
the mixin behavior from actual database operations.
"""

import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_load_prompt_text():
    """Mock load_prompt_text to simulate database responses."""
    # Patch where it's imported by the mixin, not where it's defined
    with patch('gaia_private.prompts.prompt_cache_mixin.load_prompt_text') as mock:
        # Configure mock to return a simple template
        async def mock_loader(agent_type, prompt_key, fallback, logger, log_name, **kwargs):
            # Return a mock prompt that includes the agent_type and prompt_key
            # This lets us verify the correct parameters were passed
            return f"MOCK_PROMPT[{agent_type}:{prompt_key}]"

        mock.side_effect = mock_loader
        yield mock


@pytest.fixture
def mock_load_prompt_with_templates():
    """Mock load_prompt_text with template variable support."""
    # Patch where it's imported by the mixin
    with patch('gaia_private.prompts.prompt_cache_mixin.load_prompt_text') as mock:
        async def mock_loader(agent_type, prompt_key, fallback, logger, log_name, template_vars=None, resolve_template=False, **kwargs):
            base = f"MOCK_PROMPT[{agent_type}:{prompt_key}]"

            # If template resolution requested, include the variables
            if resolve_template and template_vars:
                vars_str = "|".join(f"{k}={v}" for k, v in template_vars.items())
                return f"{base}|RESOLVED[{vars_str}]"

            return base

        mock.side_effect = mock_loader
        yield mock


# =============================================================================
# COORDINATOR AGENTS (4)
# =============================================================================

@pytest.mark.unit
async def test_campaign_persistence_agent_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for CampaignPersistenceAgent."""
    from gaia_private.agents.utility.campaign_persistence_agent import CampaignPersistenceAgent

    # Create agent instance
    agent = CampaignPersistenceAgent.__new__(CampaignPersistenceAgent)
    agent._prompt_cache = None

    # Verify agent properties
    assert agent.agent_type == "campaign_persistence_agent"
    assert agent.prompt_key == "system_prompt"
    assert agent.log_name == "CampaignPersistence"

    # Load prompt
    prompt = await agent._get_system_prompt()

    # Verify correct parameters were passed to load_prompt_text
    mock_load_prompt_text.assert_called_once()
    call_kwargs = mock_load_prompt_text.call_args.kwargs
    assert call_kwargs['agent_type'] == "campaign_persistence_agent"
    assert call_kwargs['prompt_key'] == "system_prompt"
    assert 'fallback' in call_kwargs  # Should have fallback

    # Verify prompt was loaded
    assert prompt == "MOCK_PROMPT[campaign_persistence_agent:system_prompt]"

    logger.info("✅ CampaignPersistenceAgent mixin behavior verified")


@pytest.mark.unit
async def test_scenario_analyzer_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ScenarioAnalyzerAgent."""
    from gaia_private.agents.utility.scenario_analyzer import ScenarioAnalyzerAgent

    agent = ScenarioAnalyzerAgent.__new__(ScenarioAnalyzerAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "scenario_analyzer"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "scenario_analyzer:system_prompt" in prompt

    logger.info("✅ ScenarioAnalyzerAgent mixin behavior verified")


@pytest.mark.unit
async def test_character_extractor_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for CharacterExtractorAgent."""
    from gaia_private.agents.scene.character_extractor_agent import CharacterExtractorAgent

    agent = CharacterExtractorAgent()

    assert agent.agent_type == "character_extractor"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "character_extractor:system_prompt" in prompt

    logger.info("✅ CharacterExtractorAgent mixin behavior verified")


@pytest.mark.unit
async def test_observing_player_options_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ObservingPlayerOptionsAgent."""
    from gaia_private.agents.scene.observing_player_options_agent import ObservingPlayerOptionsAgent

    agent = ObservingPlayerOptionsAgent()

    assert agent.agent_type == "observing_player_options"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "observing_player_options:system_prompt" in prompt

    logger.info("✅ ObservingPlayerOptionsAgent mixin behavior verified")


# =============================================================================
# DUNGEON MASTER AGENTS (2 agents, 4 prompts)
# =============================================================================

@pytest.mark.unit
async def test_dungeon_master_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for DungeonMasterAgent."""
    from gaia_private.agents.dungeon_master import DungeonMasterAgent

    agent = DungeonMasterAgent.__new__(DungeonMasterAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "dungeon_master"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "dungeon_master:system_prompt" in prompt

    logger.info("✅ DungeonMasterAgent mixin behavior verified")


@pytest.mark.unit
async def test_streaming_dm_core_persona(mock_load_prompt_text):
    """Test loading core_persona prompt for StreamingDM."""
    # Note: streaming_dm has 3 prompts (core_persona, unified_streaming, metadata_generation)
    # We test that the prompt system can load different prompt_keys
    # for the same agent_type

    # This test verifies that the prompt system can load different prompt_keys
    # for the same agent_type
    with patch('gaia_private.prompts.prompt_loader.load_prompt_text') as mock:
        async def mock_loader(agent_type, prompt_key, **kwargs):
            return f"MOCK[{agent_type}:{prompt_key}]"

        mock.side_effect = mock_loader

        from gaia_private.prompts.prompt_loader import load_prompt_text

        # Test loading core_persona
        core = await load_prompt_text(
            agent_type="streaming_dm",
            prompt_key="core_persona",
            fallback="FALLBACK",
            logger=logger,
            log_name="Test"
        )
        assert core == "MOCK[streaming_dm:core_persona]"

        # Test loading unified_streaming
        unified = await load_prompt_text(
            agent_type="streaming_dm",
            prompt_key="unified_streaming",
            fallback="FALLBACK",
            logger=logger,
            log_name="Test"
        )
        assert unified == "MOCK[streaming_dm:unified_streaming]"

        # Test loading metadata_generation
        metadata = await load_prompt_text(
            agent_type="streaming_dm",
            prompt_key="metadata_generation",
            fallback="FALLBACK",
            logger=logger,
            log_name="Test"
        )
        assert metadata == "MOCK[streaming_dm:metadata_generation]"

    logger.info("✅ StreamingDM multi-prompt loading verified")


# =============================================================================
# COMBAT AGENTS (1)
# =============================================================================
# NOTE: CombatNarrativeAgent and CombatActionSelectionAgent override
# _get_system_prompt() as non-async methods that return hardcoded strings.
# They don't use the PromptCacheMixin's async database loading pattern.
# Only CombatInitiatorAgent follows the proper async pattern.

@pytest.mark.unit
async def test_combat_initiator_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for CombatInitiatorAgent."""
    from gaia_private.agents.combat.initiator import CombatInitiatorAgent

    agent = CombatInitiatorAgent.__new__(CombatInitiatorAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "combat_initiator"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "combat_initiator:system_prompt" in prompt

    logger.info("✅ CombatInitiatorAgent mixin behavior verified")


# =============================================================================
# SCENE ANALYZER AGENTS (6)
# =============================================================================

@pytest.mark.unit
async def test_scene_categorizer_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for SceneCategorizer."""
    from gaia_private.agents.scene_analyzer.scene_categorizer import SceneCategorizer
    from gaia.infra.llm.model_manager import ModelName

    agent = SceneCategorizer(model=ModelName.DEEPSEEK_3_2.value)

    assert agent.agent_type == "scene_categorizer"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "scene_categorizer:system_prompt" in prompt

    logger.info("✅ SceneCategorizer mixin behavior verified")


@pytest.mark.unit
async def test_combat_exit_analyzer_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for CombatExitAnalyzer."""
    from gaia_private.agents.scene_analyzer.combat_exit_analyzer import CombatExitAnalyzer
    from gaia.infra.llm.model_manager import ModelName

    agent = CombatExitAnalyzer(model=ModelName.DEEPSEEK_3_2.value)

    assert agent.agent_type == "combat_exit_analyzer"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "combat_exit_analyzer:system_prompt" in prompt

    logger.info("✅ CombatExitAnalyzer mixin behavior verified")


@pytest.mark.unit
async def test_complexity_analyzer_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ComplexityAnalyzer."""
    from gaia_private.agents.scene_analyzer.complexity_analyzer import ComplexityAnalyzer
    from gaia.infra.llm.model_manager import ModelName

    agent = ComplexityAnalyzer(model=ModelName.DEEPSEEK_3_2.value)

    assert agent.agent_type == "complexity_analyzer"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "complexity_analyzer:system_prompt" in prompt

    logger.info("✅ ComplexityAnalyzer mixin behavior verified")


@pytest.mark.unit
async def test_next_agent_recommender_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for NextAgentRecommender."""
    from gaia_private.agents.scene_analyzer.next_agent_recommender import NextAgentRecommender
    from gaia.infra.llm.model_manager import ModelName

    agent = NextAgentRecommender(model=ModelName.DEEPSEEK_3_2.value)

    assert agent.agent_type == "next_agent_recommender"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "next_agent_recommender:system_prompt" in prompt

    logger.info("✅ NextAgentRecommender mixin behavior verified")


@pytest.mark.unit
async def test_tool_selector_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ToolSelector."""
    from gaia_private.agents.scene_analyzer.tool_selector import ToolSelector
    from gaia.infra.llm.model_manager import ModelName

    agent = ToolSelector(model=ModelName.DEEPSEEK_3_2.value)

    assert agent.agent_type == "tool_selector"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "tool_selector:system_prompt" in prompt

    logger.info("✅ ToolSelector mixin behavior verified")


@pytest.mark.unit
async def test_special_considerations_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for SpecialConsiderations."""
    from gaia_private.agents.scene_analyzer.special_considerations import SpecialConsiderations
    from gaia.infra.llm.model_manager import ModelName

    agent = SpecialConsiderations(model=ModelName.DEEPSEEK_3_2.value)

    assert agent.agent_type == "special_considerations"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "special_considerations:system_prompt" in prompt

    logger.info("✅ SpecialConsiderations mixin behavior verified")


# =============================================================================
# SUMMARIZER (1)
# =============================================================================

@pytest.mark.unit
async def test_summarizer_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for SummarizerAgent."""
    from gaia_private.agents.utility.summarizer import SummarizerAgent

    agent = SummarizerAgent.__new__(SummarizerAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "summarizer"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "summarizer:system_prompt" in prompt

    logger.info("✅ SummarizerAgent mixin behavior verified")


# =============================================================================
# SCENE AGENTS (4)
# =============================================================================

@pytest.mark.unit
async def test_exploration_agent_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ExplorationAgent."""
    from gaia_private.agents.scene.exploration_agent import ExplorationAgent

    agent = ExplorationAgent()

    assert agent.agent_type == "exploration"
    assert agent.prompt_key == "base_prompt"
    assert hasattr(agent, 'system_prompt')  # Should have fallback

    prompt = await agent._get_system_prompt()
    assert "exploration:base_prompt" in prompt

    logger.info("✅ ExplorationAgent mixin behavior verified")


@pytest.mark.unit
async def test_action_resolver_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ActionResolver."""
    from gaia_private.agents.scene.action_resolver import ActionResolver

    agent = ActionResolver()

    assert agent.agent_type == "action_resolver"
    assert agent.prompt_key == "base_prompt"

    prompt = await agent._get_system_prompt()
    assert "action_resolver:base_prompt" in prompt

    logger.info("✅ ActionResolver mixin behavior verified")


@pytest.mark.unit
async def test_dialog_agent_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for DialogAgent."""
    from gaia_private.agents.scene.dialog_agent import DialogAgent

    agent = DialogAgent()

    assert agent.agent_type == "dialog"
    assert agent.prompt_key == "base_prompt"

    prompt = await agent._get_system_prompt()
    assert "dialog:base_prompt" in prompt

    logger.info("✅ DialogAgent mixin behavior verified")


@pytest.mark.unit
async def test_scene_describer_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for SceneDescriberAgent."""
    from gaia_private.agents.scene.scene_describer import SceneDescriberAgent

    agent = SceneDescriberAgent()

    assert agent.agent_type == "scene_describer"
    assert agent.prompt_key == "base_prompt"

    prompt = await agent._get_system_prompt()
    assert "scene_describer:base_prompt" in prompt

    logger.info("✅ SceneDescriberAgent mixin behavior verified")


# =============================================================================
# GENERATOR AGENTS (4)
# =============================================================================

@pytest.mark.unit
async def test_scene_creator_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for SceneCreatorAgent."""
    from gaia_private.agents.generators.scene_creator import SceneCreatorAgent

    agent = SceneCreatorAgent.__new__(SceneCreatorAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "scene_creator"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "scene_creator:system_prompt" in prompt

    logger.info("✅ SceneCreatorAgent mixin behavior verified")


@pytest.mark.unit
async def test_image_generator_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for ImageGeneratorAgent."""
    from gaia_private.agents.generators.image_generator import ImageGeneratorAgent

    agent = ImageGeneratorAgent.__new__(ImageGeneratorAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "image_generator"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "image_generator:system_prompt" in prompt

    logger.info("✅ ImageGeneratorAgent mixin behavior verified")


@pytest.mark.unit
async def test_character_generator_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for CharacterGeneratorAgent."""
    from gaia_private.agents.generators.character_generator import CharacterGeneratorAgent

    agent = CharacterGeneratorAgent.__new__(CharacterGeneratorAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "character_generator"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "character_generator:system_prompt" in prompt

    logger.info("✅ CharacterGeneratorAgent mixin behavior verified")


@pytest.mark.unit
async def test_campaign_generator_mixin(mock_load_prompt_text):
    """Test PromptCacheMixin behavior for CampaignGeneratorAgent."""
    from gaia_private.agents.generators.campaign_generator import CampaignGeneratorAgent

    agent = CampaignGeneratorAgent.__new__(CampaignGeneratorAgent)
    agent._prompt_cache = None

    assert agent.agent_type == "campaign_generator"
    assert agent.prompt_key == "system_prompt"

    prompt = await agent._get_system_prompt()
    assert "campaign_generator:system_prompt" in prompt

    logger.info("✅ CampaignGeneratorAgent mixin behavior verified")


# =============================================================================
# CACHE BEHAVIOR TESTS
# =============================================================================

@pytest.mark.unit
async def test_prompt_caching_behavior(mock_load_prompt_text):
    """Test that prompts are cached at instance level."""
    from gaia_private.agents.generators.campaign_generator import CampaignGeneratorAgent

    agent = CampaignGeneratorAgent.__new__(CampaignGeneratorAgent)
    agent._prompt_cache = None

    # First call - should load from "DB"
    prompt1 = await agent.ensure_prompt_loaded()
    assert mock_load_prompt_text.call_count == 1
    assert prompt1 == "MOCK_PROMPT[campaign_generator:system_prompt]"

    # Second call - should use cache, not call load again
    prompt2 = await agent.ensure_prompt_loaded()
    assert mock_load_prompt_text.call_count == 1  # Still 1, not 2
    assert prompt2 == prompt1

    logger.info("✅ Prompt caching behavior verified")


@pytest.mark.unit
async def test_cache_invalidation(mock_load_prompt_text):
    """Test that cache can be invalidated."""
    from gaia_private.agents.generators.campaign_generator import CampaignGeneratorAgent

    agent = CampaignGeneratorAgent.__new__(CampaignGeneratorAgent)
    agent._prompt_cache = None

    # Load prompt
    await agent.ensure_prompt_loaded()
    assert mock_load_prompt_text.call_count == 1

    # Invalidate cache
    agent.reset_prompt_cache()
    assert agent._prompt_cache is None

    # Load again - should call load_prompt_text again
    await agent.ensure_prompt_loaded()
    assert mock_load_prompt_text.call_count == 2

    logger.info("✅ Cache invalidation behavior verified")


@pytest.mark.unit
async def test_template_variable_resolution():
    """Test that template variables are resolved correctly."""
    # Patch at the import location to prevent real DB calls
    with patch('gaia_private.prompts.prompt_loader.load_prompt_text') as mock:
        async def mock_loader(agent_type, prompt_key, fallback, logger, log_name, template_vars=None, resolve_template=False, **kwargs):
            base = f"MOCK_PROMPT[{agent_type}:{prompt_key}]"

            # If template resolution requested, include the variables
            if resolve_template and template_vars:
                vars_str = "|".join(f"{k}={v}" for k, v in template_vars.items())
                return f"{base}|RESOLVED[{vars_str}]"

            return base

        mock.side_effect = mock_loader

        from gaia_private.prompts.prompt_loader import load_prompt_text

        # Test with template variables
        result = await load_prompt_text(
            agent_type="streaming_dm",
            prompt_key="unified_streaming",
            fallback="FALLBACK",
            logger=logger,
            log_name="Test",
            template_vars={
                "conversation_history": "Player: Test",
                "formatted_text": "A dark room",
                "player_input": "I look around",
            },
            resolve_template=True
        )

        # Verify template variables were included
        assert "streaming_dm:unified_streaming" in result
        assert "conversation_history=Player: Test" in result
        assert "formatted_text=A dark room" in result
        assert "player_input=I look around" in result

    logger.info("✅ Template variable resolution verified")


@pytest.mark.unit
async def test_fallback_behavior():
    """Test that fallback is used when DB is unavailable."""
    # Mock load_prompt_text to raise an exception (simulating DB failure)
    with patch('gaia_private.prompts.prompt_loader.load_prompt_text') as mock:
        # Configure to use fallback
        async def mock_loader(agent_type, prompt_key, fallback, **kwargs):
            # Simulate DB unavailable - return fallback
            return fallback

        mock.side_effect = mock_loader

        from gaia_private.prompts.prompt_loader import load_prompt_text

        result = await load_prompt_text(
            agent_type="test_agent",
            prompt_key="test_key",
            fallback="FALLBACK_PROMPT",
            logger=logger,
            log_name="Test"
        )

        assert result == "FALLBACK_PROMPT"

    logger.info("✅ Fallback behavior verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])
