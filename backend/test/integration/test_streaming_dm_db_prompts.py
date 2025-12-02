"""Integration tests for streaming DM database-backed prompt loading.

These tests require a running database and verify that:
1. SQL migrations create the correct prompt structure
2. Prompts load from the database with template variables
3. Cross-prompt references like {{core_persona}} resolve correctly
4. Template variable resolution works with real DB data
"""

import logging
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.src import db_manager
from gaia_private.prompts.prompt_service import PromptService
from gaia_private.prompts.prompt_loader import load_prompt_text
from gaia_private.agents.dungeon_master.prompts import (
    UNIFIED_STREAMING_DM_PROMPT,
    METADATA_GENERATION_PROMPT,
)

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


@pytest.mark.integration
async def test_streaming_dm_prompts_exist_in_db(db_session: AsyncSession):
    """Test that streaming DM prompts exist in the database after migration."""
    logger.info("🔍 Testing streaming DM prompts exist in database...")

    prompt_service = PromptService(db_session)

    # Test that unified_streaming prompt exists
    logger.info("Checking unified_streaming prompt...")
    unified_prompt = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="unified_streaming"
    )
    assert unified_prompt is not None, "unified_streaming prompt should exist in DB"
    assert len(unified_prompt) > 0, "unified_streaming prompt should not be empty"
    logger.info(f"✅ Found unified_streaming prompt ({len(unified_prompt)} chars)")

    # Test that metadata_generation prompt exists
    logger.info("Checking metadata_generation prompt...")
    metadata_prompt = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="metadata_generation"
    )
    assert metadata_prompt is not None, "metadata_generation prompt should exist in DB"
    assert len(metadata_prompt) > 0, "metadata_generation prompt should not be empty"
    logger.info(f"✅ Found metadata_generation prompt ({len(metadata_prompt)} chars)")


@pytest.mark.integration
async def test_streaming_dm_prompts_have_template_variables(db_session: AsyncSession):
    """Test that DB prompts contain template variable placeholders."""
    logger.info("🔍 Testing streaming DM prompts have template variables...")

    prompt_service = PromptService(db_session)

    # Check unified_streaming has template variables
    unified_prompt = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="unified_streaming"
    )

    assert "{{conversation_history}}" in unified_prompt, "Should have conversation_history template"
    assert "{{formatted_text}}" in unified_prompt, "Should have formatted_text template"
    assert "{{player_input}}" in unified_prompt, "Should have player_input template"
    assert "{{scene_status}}" in unified_prompt, "Should have scene_status template"
    assert "{{core_persona}}" in unified_prompt, "Should have core_persona cross-prompt reference"
    logger.info("✅ unified_streaming has all expected template variables")

    # Check metadata_generation has template variables
    metadata_prompt = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="metadata_generation"
    )

    assert "{{conversation_history}}" in metadata_prompt, "Should have conversation_history template"
    assert "{{formatted_text}}" in metadata_prompt, "Should have formatted_text template"
    assert "{{player_input}}" in metadata_prompt, "Should have player_input template"
    assert "{{narrative}}" in metadata_prompt, "Should have narrative template"
    assert "{{player_response}}" in metadata_prompt, "Should have player_response template"
    assert "{{core_persona}}" in metadata_prompt, "Should have core_persona cross-prompt reference"
    logger.info("✅ metadata_generation has all expected template variables")


@pytest.mark.integration
async def test_cross_prompt_reference_resolution(db_session: AsyncSession):
    """Test that cross-prompt references like {{core_persona}} resolve from DB."""
    logger.info("🔍 Testing cross-prompt reference resolution...")

    prompt_service = PromptService(db_session)

    # Get prompt with core_persona placeholder
    unified_prompt = await prompt_service.get_prompt(
        agent_type="streaming_dm",
        prompt_key="unified_streaming"
    )

    assert "{{core_persona}}" in unified_prompt, "Raw prompt should have placeholder"
    logger.info("✅ Raw prompt contains {{core_persona}} placeholder")

    # Resolve templates (should replace {{core_persona}} with actual content)
    resolved_prompt = await prompt_service.resolve_template(unified_prompt, {})

    assert "{{core_persona}}" not in resolved_prompt, "Resolved prompt should not have placeholder"
    assert "Dungeon Master" in resolved_prompt or "DM" in resolved_prompt, "Should contain DM persona content"
    assert len(resolved_prompt) > len(unified_prompt), "Resolved prompt should be longer"
    logger.info(f"✅ Cross-prompt reference resolved (expanded from {len(unified_prompt)} to {len(resolved_prompt)} chars)")


@pytest.mark.integration
async def test_template_variable_resolution_from_db(db_session: AsyncSession):
    """Test that runtime template variables resolve correctly with DB-loaded prompts."""
    logger.info("🔍 Testing template variable resolution from database...")

    prompt_service = PromptService(db_session)

    # Get prompt from database
    unified_prompt = await prompt_service.get_prompt_with_fallback(
        agent_type="streaming_dm",
        prompt_key="unified_streaming",
        fallback=UNIFIED_STREAMING_DM_PROMPT
    )

    # Resolve with runtime variables
    test_vars = {
        "conversation_history": "Player: I draw my sword.",
        "formatted_text": "A dark cavern with glowing crystals.",
        "player_input": "I approach the crystals carefully.",
        "scene_status": "",
    }

    resolved_prompt = await prompt_service.resolve_template(unified_prompt, test_vars)

    # Verify runtime variables were resolved
    assert "I draw my sword" in resolved_prompt, "Should contain conversation_history value"
    assert "glowing crystals" in resolved_prompt, "Should contain formatted_text value"
    assert "approach the crystals" in resolved_prompt, "Should contain player_input value"

    # Verify template placeholders are gone
    assert "{{conversation_history}}" not in resolved_prompt
    assert "{{formatted_text}}" not in resolved_prompt
    assert "{{player_input}}" not in resolved_prompt
    assert "{{scene_status}}" not in resolved_prompt
    assert "{{core_persona}}" not in resolved_prompt

    logger.info("✅ All template variables resolved correctly from DB prompt")


@pytest.mark.integration
async def test_load_prompt_text_with_db_available():
    """Test load_prompt_text function when database is available."""
    logger.info("🔍 Testing load_prompt_text with real database...")

    # Load using load_prompt_text (should use DB, not fallback)
    unified_result = await load_prompt_text(
        agent_type="streaming_dm",
        prompt_key="unified_streaming",
        fallback=UNIFIED_STREAMING_DM_PROMPT,
        logger=logger,
        log_name="TestDBLoad",
        template_vars={
            "conversation_history": "DB test history",
            "formatted_text": "DB test scene",
            "player_input": "DB test input",
            "scene_status": "DB test status",
        },
        resolve_template=True,
    )

    # Verify template variables were resolved
    assert "DB test history" in unified_result, "Should resolve conversation_history"
    assert "DB test scene" in unified_result, "Should resolve formatted_text"
    assert "DB test input" in unified_result, "Should resolve player_input"
    assert "DB test status" in unified_result, "Should resolve scene_status"

    # Verify no unresolved placeholders
    assert "{{conversation_history}}" not in unified_result
    assert "{{formatted_text}}" not in unified_result
    assert "{{player_input}}" not in unified_result
    assert "{{scene_status}}" not in unified_result
    assert "{{core_persona}}" not in unified_result

    logger.info("✅ load_prompt_text works correctly with database")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
