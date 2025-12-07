"""
Integration tests for player options agents.

Tests that:
1. Both player_options and active_player_options prompts exist in DB
2. Prompts contain required template variables
3. Template resolution works correctly
4. JSON output format is specified
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
    if db_manager.async_engine:
        await db_manager.async_engine.dispose()


# =============================================================================
# PROMPT EXISTENCE TESTS
# =============================================================================

@pytest.mark.integration
async def test_player_options_prompt_exists(db_session: AsyncSession):
    """Test that player_options (observing) prompt exists in database."""
    prompt_service = PromptService(db_session)

    prompt = await prompt_service.get_prompt(
        agent_type="player_options",
        prompt_key="system_prompt"
    )

    assert prompt is not None, "player_options prompt should exist"
    assert len(prompt) > 100, "Prompt should have substantial content"

    logger.info(f"✅ player_options prompt loaded ({len(prompt)} chars)")


@pytest.mark.integration
async def test_active_player_options_prompt_exists(db_session: AsyncSession):
    """Test that active_player_options prompt exists in database."""
    prompt_service = PromptService(db_session)

    prompt = await prompt_service.get_prompt(
        agent_type="active_player_options",
        prompt_key="system_prompt"
    )

    assert prompt is not None, "active_player_options prompt should exist"
    assert len(prompt) > 100, "Prompt should have substantial content"

    logger.info(f"✅ active_player_options prompt loaded ({len(prompt)} chars)")


# =============================================================================
# TEMPLATE VARIABLE TESTS
# =============================================================================

@pytest.mark.integration
async def test_player_options_has_required_variables(db_session: AsyncSession):
    """Test that player_options prompt has required template variables."""
    prompt_service = PromptService(db_session)

    prompt = await prompt_service.get_prompt(
        agent_type="player_options",
        prompt_key="system_prompt"
    )

    required_vars = [
        "{{scene_narrative}}",
        "{{current_char_name}}",
        "{{next_char_name}}",
        "{{character_context}}"
    ]

    for var in required_vars:
        assert var in prompt, f"player_options should have {var}"

    logger.info("✅ player_options has all required template variables")


@pytest.mark.integration
async def test_active_player_options_has_required_variables(db_session: AsyncSession):
    """Test that active_player_options prompt has required template variables."""
    prompt_service = PromptService(db_session)

    prompt = await prompt_service.get_prompt(
        agent_type="active_player_options",
        prompt_key="system_prompt"
    )

    required_vars = [
        "{{scene_narrative}}",
        "{{current_char_name}}",
        "{{next_char_name}}",
        "{{character_context}}"
    ]

    for var in required_vars:
        assert var in prompt, f"active_player_options should have {var}"

    logger.info("✅ active_player_options has all required template variables")




# =============================================================================
# TEMPLATE RESOLUTION TESTS
# =============================================================================

@pytest.mark.integration
async def test_template_resolution_works(db_session: AsyncSession):
    """Test that template variables can be resolved."""
    prompt_service = PromptService(db_session)

    prompt = await prompt_service.get_prompt(
        agent_type="active_player_options",
        prompt_key="system_prompt"
    )

    template_vars = {
        "scene_narrative": "The dragon breathes fire at the party!",
        "current_char_name": "Gandalf",
        "next_char_name": "Aragorn",
        "character_context": "A skilled ranger with a magic sword"
    }

    resolved = await prompt_service.resolve_template(prompt, template_vars)

    # All placeholders should be replaced
    assert "{{scene_narrative}}" not in resolved
    assert "{{current_char_name}}" not in resolved
    assert "{{next_char_name}}" not in resolved
    assert "{{character_context}}" not in resolved

    # Values should be present
    assert "dragon breathes fire" in resolved
    assert "Gandalf" in resolved
    assert "Aragorn" in resolved
    assert "skilled ranger" in resolved

    logger.info("✅ Template resolution works correctly")


@pytest.mark.integration
async def test_json_output_format_specified(db_session: AsyncSession):
    """Test that both prompts specify JSON output format."""
    prompt_service = PromptService(db_session)

    for agent_type in ["player_options", "active_player_options"]:
        prompt = await prompt_service.get_prompt(
            agent_type=agent_type,
            prompt_key="system_prompt"
        )

        # Should specify JSON output with player_options key
        assert "json" in prompt.lower() or "JSON" in prompt, f"{agent_type} should mention JSON"
        assert "player_options" in prompt, f"{agent_type} should mention player_options key"

        logger.info(f"✅ {agent_type} specifies JSON output format")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
