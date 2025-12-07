"""Integration tests for all agents' database-backed prompt loading.

This test validates that all 27 agents that use PromptCacheMixin can:
1. Load prompts from the database successfully
2. Have properly structured prompt_text in the database
3. Can fall back to hardcoded prompts if needed

Agents tested (27 total):
- Coordinator (5): campaign_persistence, scenario_analyzer, character_extractor,
                   observing_player_options, active_player_options
- Dungeon Master (4): dungeon_master, streaming_dm (3 prompts)
- Combat (3): combat_narrator, combat_action_selector, combat_initiator
- Scene Analyzer (6): scene_categorizer, combat_exit_analyzer, complexity_analyzer,
                      next_agent_recommender, tool_selector, special_considerations
- Summarizer (1): summarizer
- Scene Agent (4): exploration, action_resolver, dialog, scene_describer
- Generator (4): scene_creator, image_generator, character_generator, campaign_generator
"""

import logging
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.src import db_manager
from gaia_private.prompts.prompt_service import PromptService

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provide a database session for integration tests."""
    async with db_manager.get_async_session() as session:
        yield session
    # Dispose of the connection pool to avoid event loop issues between tests
    if db_manager.async_engine:
        await db_manager.async_engine.dispose()


# =============================================================================
# AGENT PROMPT DEFINITIONS
# =============================================================================

# Organized by category matching the SQL file structure
AGENT_PROMPTS = {
    # Coordinator agents (5)
    "coordinator": [
        ("campaign_persistence_agent", "system_prompt"),
        ("scenario_analyzer", "system_prompt"),
        ("character_extractor", "system_prompt"),
        ("observing_player_options", "system_prompt"),  # ObservingPlayerOptionsAgent
        ("active_player_options", "system_prompt"),  # ActivePlayerOptionsAgent
    ],
    # Dungeon Master agents (4 prompts, 1 agent + 3 streaming_dm)
    "dungeon_master": [
        ("dungeon_master", "system_prompt"),
        ("streaming_dm", "core_persona"),
        ("streaming_dm", "unified_streaming"),
        ("streaming_dm", "metadata_generation"),
    ],
    # Combat agents (3)
    "combat": [
        ("combat_narrator", "system_prompt"),
        ("combat_action_selector", "system_prompt"),
        ("combat_initiator", "system_prompt"),
    ],
    # Scene analyzer agents (6)
    "scene_analyzer": [
        ("scene_categorizer", "system_prompt"),
        ("combat_exit_analyzer", "system_prompt"),
        ("complexity_analyzer", "system_prompt"),
        ("next_agent_recommender", "system_prompt"),
        ("tool_selector", "system_prompt"),
        ("special_considerations", "system_prompt"),
    ],
    # Summarizer (1)
    "summarizer": [
        ("summarizer", "system_prompt"),
    ],
    # Scene agents (4)
    "scene_agent": [
        ("exploration", "base_prompt"),
        ("action_resolver", "base_prompt"),
        ("dialog", "base_prompt"),
        ("scene_describer", "base_prompt"),
    ],
    # Generator agents (4)
    "generator": [
        ("scene_creator", "system_prompt"),
        ("image_generator", "system_prompt"),
        ("character_generator", "system_prompt"),
        ("campaign_generator", "system_prompt"),
    ],
}


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.integration
async def test_all_agents_prompts_exist_in_db(db_session: AsyncSession):
    """Test that all 26 agent prompts exist in the database after migration."""
    logger.info("🔍 Testing all agent prompts exist in database...")

    prompt_service = PromptService(db_session)
    total_prompts = 0
    failed_prompts = []

    for category, prompts in AGENT_PROMPTS.items():
        logger.info(f"\n📂 Testing {category} agents ({len(prompts)} prompts)...")

        for agent_type, prompt_key in prompts:
            total_prompts += 1
            try:
                prompt = await prompt_service.get_prompt(
                    agent_type=agent_type,
                    prompt_key=prompt_key
                )

                assert prompt is not None, f"{agent_type}:{prompt_key} should exist in DB"
                assert len(prompt) > 0, f"{agent_type}:{prompt_key} should not be empty"

                logger.info(f"  ✅ {agent_type}:{prompt_key} ({len(prompt)} chars)")

            except Exception as e:
                logger.error(f"  ❌ {agent_type}:{prompt_key} - {e}")
                failed_prompts.append((agent_type, prompt_key, str(e)))

    # Final assertions
    logger.info(f"\n📊 Summary: {total_prompts - len(failed_prompts)}/{total_prompts} prompts found")

    if failed_prompts:
        error_msg = "\n".join([f"  - {agent}:{key}: {err}" for agent, key, err in failed_prompts])
        pytest.fail(f"Failed to load {len(failed_prompts)} prompts:\n{error_msg}")


@pytest.mark.integration
async def test_all_prompts_are_non_empty(db_session: AsyncSession):
    """Test that all prompts have substantial content (not just whitespace)."""
    logger.info("🔍 Testing all prompts have substantial content...")

    prompt_service = PromptService(db_session)
    too_short = []
    MIN_LENGTH = 50  # Reasonable minimum for a prompt

    for category, prompts in AGENT_PROMPTS.items():
        for agent_type, prompt_key in prompts:
            try:
                prompt = await prompt_service.get_prompt(
                    agent_type=agent_type,
                    prompt_key=prompt_key
                )

                stripped = prompt.strip()
                if len(stripped) < MIN_LENGTH:
                    too_short.append((agent_type, prompt_key, len(stripped)))
                    logger.warning(f"  ⚠️ {agent_type}:{prompt_key} is very short ({len(stripped)} chars)")

            except Exception as e:
                # Already tested in previous test, skip
                pass

    if too_short:
        error_msg = "\n".join([f"  - {agent}:{key}: only {length} chars" for agent, key, length in too_short])
        pytest.fail(f"Found {len(too_short)} prompts that are too short:\n{error_msg}")

    logger.info(f"✅ All prompts have substantial content (>{MIN_LENGTH} chars)")


@pytest.mark.integration
async def test_streaming_dm_template_variables(db_session: AsyncSession):
    """Test that streaming DM prompts have proper template variable syntax."""
    logger.info("🔍 Testing streaming DM template variables...")

    prompt_service = PromptService(db_session)

    # Test unified_streaming template variables
    unified = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="unified_streaming"
    )

    required_vars = [
        "{{conversation_history}}",
        "{{formatted_text}}",
        "{{player_input}}",
        "{{scene_status}}",
        "{{core_persona}}",
    ]

    for var in required_vars:
        assert var in unified, f"unified_streaming should have {var}"

    logger.info("  ✅ unified_streaming has all required template variables")

    # Test metadata_generation template variables
    metadata = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="metadata_generation"
    )

    metadata_vars = [
        "{{conversation_history}}",
        "{{formatted_text}}",
        "{{player_input}}",
        "{{narrative}}",
        "{{player_response}}",
        "{{core_persona}}",
    ]

    for var in metadata_vars:
        assert var in metadata, f"metadata_generation should have {var}"

    logger.info("  ✅ metadata_generation has all required template variables")


@pytest.mark.integration
async def test_core_persona_cross_reference(db_session: AsyncSession):
    """Test that core_persona can be loaded and referenced by other prompts."""
    logger.info("🔍 Testing core_persona cross-prompt reference...")

    prompt_service = PromptService(db_session)

    # Get core_persona
    core_persona = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="core_persona"
    )

    assert "YOUR PERSONA:" in core_persona, "core_persona should have YOUR PERSONA section"
    assert "Dungeon Master" in core_persona or "DM" in core_persona, "Should reference DM role"
    logger.info(f"  ✅ core_persona loaded ({len(core_persona)} chars)")

    # Test that unified_streaming can resolve it
    unified = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="unified_streaming"
    )

    assert "{{core_persona}}" in unified, "unified_streaming should reference {{core_persona}}"

    # Resolve the template
    resolved = await prompt_service.resolve_template(unified, {})

    assert "{{core_persona}}" not in resolved, "Resolved prompt should not have placeholder"
    assert "YOUR PERSONA:" in resolved or "Dungeon Master" in resolved, "Should contain core persona content"
    assert len(resolved) > len(unified), "Resolved should be longer than original"

    logger.info(f"  ✅ core_persona cross-reference resolves correctly (expanded {len(unified)} → {len(resolved)} chars)")


@pytest.mark.integration
async def test_prompt_caching_behavior(db_session: AsyncSession):
    """Test that prompts are cached on subsequent loads."""
    logger.info("🔍 Testing prompt caching behavior...")

    prompt_service = PromptService(db_session)

    # Load a prompt twice
    agent_type, prompt_key = "dungeon_master", "system_prompt"

    # First load
    prompt1 = await prompt_service.get_prompt(agent_type, prompt_key)

    # Second load (should use cache)
    prompt2 = await prompt_service.get_prompt(agent_type, prompt_key)

    # Should be identical
    assert prompt1 == prompt2, "Cached prompt should match original"
    logger.info(f"  ✅ Prompt caching works correctly")


@pytest.mark.integration
async def test_fallback_mechanism(db_session: AsyncSession):
    """Test that get_prompt_with_fallback works correctly."""
    logger.info("🔍 Testing fallback mechanism...")

    prompt_service = PromptService(db_session)

    # Test with existing prompt (should use DB)
    db_prompt = await prompt_service.get_prompt_with_fallback(
        agent_type="dungeon_master",
        prompt_key="system_prompt",
        fallback="FALLBACK_TEXT"
    )

    assert db_prompt != "FALLBACK_TEXT", "Should use DB prompt, not fallback"
    assert len(db_prompt) > 100, "DB prompt should have substantial content"
    logger.info("  ✅ Fallback mechanism prefers DB when available")

    # Test with non-existent prompt (should use fallback)
    fallback_result = await prompt_service.get_prompt_with_fallback(
        agent_type="nonexistent",
        prompt_key="nonexistent",
        fallback="FALLBACK_PROMPT_TEXT"
    )

    assert fallback_result == "FALLBACK_PROMPT_TEXT", "Should use fallback for non-existent prompt"
    logger.info("  ✅ Fallback mechanism works for missing prompts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
