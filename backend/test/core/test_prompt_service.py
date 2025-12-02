"""
Tests for PromptService - database-backed prompt loading and template resolution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from gaia_private.prompts.prompt_service import PromptService, PromptNotFoundError
from gaia_private.prompts.models.db_models import Prompt


@pytest.fixture
def mock_db_session():
    """Mock async database session"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def prompt_service(mock_db_session):
    """PromptService instance with mocked database"""
    return PromptService(mock_db_session)


@pytest.fixture
def sample_prompt():
    """Sample prompt for testing"""
    prompt = MagicMock(spec=Prompt)
    prompt.prompt_id = "test-id"
    prompt.agent_type = "streaming_dm"
    prompt.prompt_key = "unified_streaming"
    prompt.category = "dungeon_master"
    prompt.version_number = 1
    prompt.is_active = True
    prompt.prompt_text = "You are a DM. Context: {{scene_description}}"
    prompt.description = "Test prompt"
    prompt.created_at = MagicMock()
    return prompt


class TestGetPrompt:
    """Tests for get_prompt method"""

    @pytest.mark.asyncio
    async def test_get_prompt_from_database(self, prompt_service, mock_db_session, sample_prompt):
        """Test loading prompt from database"""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_prompt
        mock_db_session.execute.return_value = mock_result

        # Get prompt
        result = await prompt_service.get_prompt('streaming_dm', 'unified_streaming')

        # Verify
        assert result == sample_prompt.prompt_text
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_prompt_uses_cache(self, prompt_service, mock_db_session, sample_prompt):
        """Test that subsequent requests use cache"""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_prompt
        mock_db_session.execute.return_value = mock_result

        # First call - loads from DB
        result1 = await prompt_service.get_prompt('streaming_dm', 'unified_streaming')
        assert result1 == sample_prompt.prompt_text
        assert mock_db_session.execute.call_count == 1

        # Second call - uses cache
        result2 = await prompt_service.get_prompt('streaming_dm', 'unified_streaming')
        assert result2 == sample_prompt.prompt_text
        assert mock_db_session.execute.call_count == 1  # Still 1, not called again

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(self, prompt_service, mock_db_session):
        """Test error when prompt doesn't exist"""
        # Mock database returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Should raise PromptNotFoundError
        with pytest.raises(PromptNotFoundError):
            await prompt_service.get_prompt('nonexistent', 'nonexistent')


class TestResolveTemplate:
    """Tests for resolve_template method"""

    @pytest.mark.asyncio
    async def test_resolve_runtime_variables(self, prompt_service):
        """Test resolving runtime template variables"""
        prompt_text = "Scene ID: {{scene_id}}, Campaign: {{campaign_id}}"
        template_vars = {
            'scene_id': '123',
            'campaign_id': '456'
        }

        result = await prompt_service.resolve_template(prompt_text, template_vars)

        assert result == "Scene ID: 123, Campaign: 456"

    @pytest.mark.asyncio
    async def test_resolve_cross_prompt_reference(self, prompt_service, mock_db_session):
        """Test resolving cross-prompt references"""
        # Mock the core_persona prompt
        core_persona_prompt = MagicMock(spec=Prompt)
        core_persona_prompt.prompt_text = "You are an experienced DM."
        core_persona_result = MagicMock()
        core_persona_result.scalar_one_or_none.return_value = core_persona_prompt
        mock_db_session.execute.return_value = core_persona_result

        prompt_text = "{{core_persona}}\n\nYour task: Generate narrative."

        result = await prompt_service.resolve_template(prompt_text, {})

        assert result == "You are an experienced DM.\n\nYour task: Generate narrative."

    @pytest.mark.asyncio
    async def test_resolve_mixed_variables(self, prompt_service, mock_db_session):
        """Test resolving both runtime vars and cross-prompt references"""
        # Mock the core_persona prompt
        core_persona_prompt = MagicMock(spec=Prompt)
        core_persona_prompt.prompt_text = "You are a DM."
        core_persona_result = MagicMock()
        core_persona_result.scalar_one_or_none.return_value = core_persona_prompt
        mock_db_session.execute.return_value = core_persona_result

        prompt_text = "{{core_persona}}\n\nScene: {{scene_id}}"
        template_vars = {'scene_id': '789'}

        result = await prompt_service.resolve_template(prompt_text, template_vars)

        assert result == "You are a DM.\n\nScene: 789"

    @pytest.mark.asyncio
    async def test_resolve_missing_variable_warning(self, prompt_service, mock_db_session):
        """Test that missing variables are left as-is with warning"""
        # Mock database returning None for unknown prompt
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        prompt_text = "Value: {{unknown_var}}"

        result = await prompt_service.resolve_template(prompt_text, {})

        # Should leave placeholder as-is
        assert result == "Value: {{unknown_var}}"

    @pytest.mark.asyncio
    async def test_resolve_empty_template_vars(self, prompt_service):
        """Test resolving with no template variables"""
        prompt_text = "Static prompt text"

        result = await prompt_service.resolve_template(prompt_text, {})

        assert result == "Static prompt text"

    @pytest.mark.asyncio
    async def test_resolve_none_values(self, prompt_service):
        """Test resolving None values in template vars"""
        prompt_text = "Value: {{nullable}}"
        template_vars = {'nullable': None}

        result = await prompt_service.resolve_template(prompt_text, template_vars)

        assert result == "Value: "  # None becomes empty string


class TestGetPromptWithFallback:
    """Tests for get_prompt_with_fallback method"""

    @pytest.mark.asyncio
    async def test_fallback_when_not_found(self, prompt_service, mock_db_session):
        """Test using fallback when prompt not in database"""
        # Mock database returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        fallback = "Fallback prompt text"
        result = await prompt_service.get_prompt_with_fallback(
            'test_agent', 'test_key', fallback
        )

        assert result == fallback

    @pytest.mark.asyncio
    async def test_fallback_on_database_error(self, prompt_service, mock_db_session):
        """Test using fallback when database throws error"""
        # Mock database throwing exception
        mock_db_session.execute.side_effect = Exception("Database error")

        fallback = "Fallback prompt text"
        result = await prompt_service.get_prompt_with_fallback(
            'test_agent', 'test_key', fallback
        )

        assert result == fallback

    @pytest.mark.asyncio
    async def test_uses_database_when_available(self, prompt_service, mock_db_session, sample_prompt):
        """Test using database prompt when available"""
        # Mock database returning prompt
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_prompt
        mock_db_session.execute.return_value = mock_result

        fallback = "Fallback prompt text"
        result = await prompt_service.get_prompt_with_fallback(
            'streaming_dm', 'unified_streaming', fallback
        )

        assert result == sample_prompt.prompt_text
        assert result != fallback


class TestCacheInvalidation:
    """Tests for cache invalidation"""

    @pytest.mark.asyncio
    async def test_invalidate_all_cache(self, prompt_service, mock_db_session, sample_prompt):
        """Test clearing entire cache"""
        # Load prompt into cache
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_prompt
        mock_db_session.execute.return_value = mock_result

        await prompt_service.get_prompt('streaming_dm', 'unified_streaming')
        assert len(prompt_service._cache) > 0

        # Invalidate cache
        await prompt_service.invalidate_cache()
        assert len(prompt_service._cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_agent_type_cache(self, prompt_service, mock_db_session):
        """Test clearing cache for specific agent type"""
        # Manually add items to cache
        prompt_service._cache['streaming_dm:prompt1'] = "text1"
        prompt_service._cache['streaming_dm:prompt2'] = "text2"
        prompt_service._cache['combat_agent:prompt1'] = "text3"

        # Invalidate only streaming_dm cache
        await prompt_service.invalidate_cache('streaming_dm')

        assert 'streaming_dm:prompt1' not in prompt_service._cache
        assert 'streaming_dm:prompt2' not in prompt_service._cache
        assert 'combat_agent:prompt1' in prompt_service._cache
