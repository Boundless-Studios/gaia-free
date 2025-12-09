"""
Model providers for different LLM services.
"""
import os
import logging
from agents import ModelProvider, OpenAIChatCompletionsModel, Model
from openai import AsyncOpenAI
from backend.src.gaia.infra.llm.model_manager import PreferredModels
from gaia.infra.llm.providers.ollama import ollama_manager

logger = logging.getLogger(__name__)

# Provider configuration
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL") or "claude-3-7-sonnet-20250219"
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL") or "https://api.anthropic.com/v1"

# Parasail configuration
PARASAIL_API_KEY = os.getenv("PARASAIL_API_KEY")
PARASAIL_BASE_URL = "https://api.parasail.io/v1"
PARASAIL_MODEL = PreferredModels.KIMI

class ClaudeModelProvider(ModelProvider):
    """Custom model provider for Claude."""
    
    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key
        )
    
    def get_model(self, model_name: str | None) -> Model:
        """Get the Claude model."""
        selected_model = model_name or CLAUDE_MODEL
        return OpenAIChatCompletionsModel(
            model=selected_model,
            openai_client=self.client
        )
    
    async def create_chat_completion(self, messages, **kwargs):
        """Create chat completion using Claude."""
        try:
            response = await self.client.chat.completions.create(
                messages=messages,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

class OllamaModelProvider(ModelProvider):
    """
    DEPRECATED: Custom model provider for Ollama.

    Ollama support has been removed. This class is kept for backward compatibility
    but will raise an error if used.
    """

    def __init__(self, base_url: str = "http://localhost:11434/v1"):
        raise RuntimeError(
            "OllamaModelProvider is deprecated and disabled. "
            "Ollama support has been removed. Use Claude or Parasail providers instead."
        )

    def get_model(self, model_name: str | None) -> Model:
        """Get the Ollama model - DEPRECATED."""
        raise RuntimeError(
            "OllamaModelProvider is deprecated. Use Claude or Parasail providers instead."
        )

    async def create_chat_completion(self, messages, **kwargs):
        """Create chat completion using Ollama - DEPRECATED."""
        raise RuntimeError(
            "OllamaModelProvider is deprecated. Use Claude or Parasail providers instead."
        )

class ParasailModelProvider(ModelProvider):
    """Custom model provider for Parasail API (Kimi K2)."""
    
    def __init__(self, base_url: str = PARASAIL_BASE_URL, api_key: str = None):
        if not api_key:
            api_key = PARASAIL_API_KEY
        
        if not api_key:
            raise ValueError("PARASAIL_API_KEY not found in environment variables")
        
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key
        )
    
    def get_model(self, model_name: str | None) -> Model:
        """Get the Parasail model."""
        selected_model = model_name or PARASAIL_MODEL
        return OpenAIChatCompletionsModel(
            model=selected_model,
            openai_client=self.client
        )
    
    async def create_chat_completion(self, messages, model: str | None = None, **kwargs):
        """Create chat completion using Parasail API."""
        try:
            selected_model = model or PARASAIL_MODEL
            response = await self.client.chat.completions.create(
                messages=messages,
                model=selected_model,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Parasail API error: {e}")
            raise