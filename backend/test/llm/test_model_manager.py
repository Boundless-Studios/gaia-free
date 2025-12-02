"""Tests for LLM model management."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import os
from gaia.infra.llm.model_manager import get_provider_for_model, create_model_provider_for_model, resolve_model_and_provider, get_default_model_and_provider, get_model_provider_for_resolved_model, resolve_model, ModelName
from gaia.infra.llm.providers.model_providers import OllamaModelProvider, ClaudeModelProvider

class TestModelManager:
    """Test model manager functionality."""
    
    def test_get_provider_for_parasail_model(self):
        """Test getting provider for Parasail models."""

        provider_type = get_provider_for_model(ModelName.DEEPSEEK_3_1.value)

        assert provider_type == "parasail"
    
    def test_get_provider_for_claude_model(self):
        """Test getting provider for Claude models."""
        
        provider_type = get_provider_for_model("claude-3-5-sonnet-20241022")
        
        assert provider_type == "claude"
    
    def test_get_provider_for_unknown_model(self):
        """Test getting provider for unknown models defaults to Claude."""

        provider_type = get_provider_for_model("gpt-4")

        assert provider_type == "claude"  # Default fallback
    
    def test_unknown_model_returns_default(self):
        """Test unknown model returns default provider."""

        provider_type = get_provider_for_model("unknown-model")

        assert provider_type == "claude"  # Default fallback
    
    def test_model_resolution(self):
        """Test model name resolution."""

        # Test with specific Claude model
        provider_type, model_name = resolve_model_and_provider("claude-3-5-sonnet-20241022")
        assert provider_type == "claude"
        assert model_name == "claude-3-5-sonnet-20241022"

        # Test with None (uses default logic)
        provider_type, model_name = resolve_model_and_provider()
        assert provider_type in ["parasail", "claude"]
        assert model_name is not None

    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable"
    )
    def test_model_provider_creation(self):
        """Test creating model providers."""
        # Test Parasail provider creation
        provider, model_name = create_model_provider_for_model(ModelName.DEEPSEEK_3_1.value)
        assert provider is not None
        assert model_name == ModelName.DEEPSEEK_3_1.value

        # Test Claude provider creation
        provider, model_name = create_model_provider_for_model("claude-3-5-sonnet-20241022")
        assert provider is not None

class TestLLMProvider:
    """Test LLM provider selection and usage."""

    @pytest.mark.asyncio
    async def test_anthropic_provider_requires_parameters(self):
        """Test Anthropic provider requires base_url and api_key."""

        # Should work with required parameters
        provider = ClaudeModelProvider("https://api.anthropic.com/v1", "test-key")
        assert provider.client is not None

class TestModelSelection:
    """Test model selection logic."""

    def test_agent_model_preferences(self):
        """Test that agents have appropriate model preferences."""

        # Test that we can get appropriate models for different agent types
        dm_model = "claude-3-5-sonnet-20241022"  # High-quality model for DM
        analyzer_model = ModelName.DEEPSEEK_3_1.value  # Fast model for analyzer

        # DM should prefer high-quality models
        dm_provider = get_provider_for_model(dm_model)
        assert dm_provider == "claude"

        # Analyzer should prefer fast models
        analyzer_provider = get_provider_for_model(analyzer_model)
        assert analyzer_provider == "parasail"
    
    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable"
    )
    def test_model_resolution_with_fallback(self):
        """Test model resolution with fallback logic."""

        # Test resolution of known model
        resolved = resolve_model(ModelName.DEEPSEEK_3_1.value)
        assert resolved == ModelName.DEEPSEEK_3_1.value

        # Test resolution of unknown model (should fallback)
        resolved = resolve_model("unknown-model")
        assert resolved is not None
    
    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable"
    )
    def test_default_model_and_provider(self):
        """Test getting default model and provider."""

        provider, model_name = get_default_model_and_provider()

        assert provider is not None
        assert model_name is not None
        assert hasattr(provider, 'get_model')
    
    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable"
    )
    def test_model_provider_for_resolved_model(self):
        """Test getting provider for resolved model."""

        # Test with Parasail model
        provider = get_model_provider_for_resolved_model(ModelName.DEEPSEEK_3_1.value)
        assert provider is not None
        assert hasattr(provider, 'get_model')