"""
Model management system with provider mapping and configuration.

Note: Ollama support is deprecated. The system now uses remote generation (Claude, Parasail) only.
"""
import os
import logging
from typing import Dict, Optional, Tuple, List, Callable, Any, Awaitable, TypeVar
from enum import Enum
from agents import ModelProvider
from gaia.infra.llm.providers.model_providers import ClaudeModelProvider, ParasailModelProvider

logger = logging.getLogger(__name__)

class ModelName(Enum):
    """Enum for all available model names across providers."""

    # Claude models
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-20250219"
    CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"

    # Parasail models
    KIMI_K2_THINKING = "moonshotai/Kimi-K2-Instruct-0905"
    DEEPSEEK_3_1 = "deepseek-ai/DeepSeek-V3.1"
    QWEN_NEXT = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    ANUBIS = "TheDrummer/Anubis-70B"
    SKYFALL = "TheDrummer/Skyfall-36B-v2"

    # Parasail image models
    OMNIGEN_V1 = "Shitao/OmniGen-v1"

    @classmethod
    def from_string(cls, model_string: str) -> Optional['ModelName']:
        """Convert a string to ModelName enum if it exists."""
        for model in cls:
            if model.value == model_string:
                return model
        return None

class PreferredModels(Enum):
    #KIMI = ModelName.ANUBIS.value
    #DEEPSEEK=ModelName.SKYFALL.value
    KIMI = ModelName.KIMI_K2_THINKING.value
    DEEPSEEK = ModelName.DEEPSEEK_3_1.value
    QWEN = ModelName.QWEN_NEXT.value
    SONNET = ModelName.CLAUDE_SONNET_4.value
    
    
# Model to provider mapping
MODEL_PROVIDER_MAP = {
    # Claude models
    ModelName.CLAUDE_3_7_SONNET.value: "claude",
    ModelName.CLAUDE_SONNET_4.value: "claude",

    # Parasail models
    ModelName.KIMI_K2_THINKING.value: "parasail",
    ModelName.DEEPSEEK_3_1.value: "parasail",
    ModelName.ANUBIS.value: "parasail",
    ModelName.SKYFALL.value: "parasail",
    ModelName.QWEN_NEXT.value: "parasail",

    # Parasail image models
    ModelName.OMNIGEN_V1.value: "parasail-image",
}

# Default models for providers
DEFAULT_CLAUDE_MODEL = ModelName.CLAUDE_3_7_SONNET.value
DEFAULT_PARASAIL_MODEL = ModelName.KIMI_K2_THINKING.value

# Model fallback chain - defines what models to try if primary fails
# Each entry maps a model to its ordered list of fallback models
MODEL_FALLBACK_CHAIN: Dict[str, list[str]] = {
    # DeepSeek falls back to Claude Sonnet 4
    ModelName.DEEPSEEK_3_1.value: [
        ModelName.CLAUDE_SONNET_4.value
    ],
    # Kimi falls back to DeepSeek, then Claude
    ModelName.KIMI_K2_THINKING.value: [
        ModelName.DEEPSEEK_3_1.value,
        ModelName.CLAUDE_SONNET_4.value
    ],
    # Anubis and Skyfall fall back to DeepSeek, then Claude
    ModelName.ANUBIS.value: [
        ModelName.DEEPSEEK_3_1.value,
        ModelName.CLAUDE_SONNET_4.value
    ],
    ModelName.SKYFALL.value: [
        ModelName.DEEPSEEK_3_1.value,
        ModelName.CLAUDE_SONNET_4.value
    ],
    # Claude models don't have fallbacks (they are the fallback)
    # No entries for Claude models means they return empty list
}

# Default fallback for models not in the chain
DEFAULT_FALLBACK_CHAIN = [ModelName.CLAUDE_SONNET_4.value]


def get_fallback_models(model_key: str) -> list[str]:
    """
    Get the fallback chain for a given model.

    Args:
        model_key: The primary model key to get fallbacks for

    Returns:
        List of fallback model keys in order of preference.
        Returns empty list if model is a final fallback (like Claude models).
    """
    # Check if model has explicit fallback chain
    if model_key in MODEL_FALLBACK_CHAIN:
        return MODEL_FALLBACK_CHAIN[model_key].copy()

    # Check if this is a Claude model (no fallback needed)
    provider = MODEL_PROVIDER_MAP.get(model_key)
    if provider == "claude":
        return []  # Claude models are the ultimate fallback

    # For unknown models or Parasail models without explicit chain, use default
    logger.info(f"No explicit fallback chain for {model_key}, using default")
    return DEFAULT_FALLBACK_CHAIN.copy()


def get_provider_for_model(model_key: str) -> str:
    """Get the provider for a given model key."""
    provider = MODEL_PROVIDER_MAP.get(model_key)
    if provider is None:
        logger.warning(f"Unknown model key: {model_key}. Defaulting to Claude.")
        return "claude"
    return provider

def resolve_model_and_provider(model_key: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolve model key to provider and model name.
    
    Args:
        model_key: Optional model key. If None, uses default provider logic.
        
    Returns:
        Tuple of (provider_type, resolved_model_name)
    """
    if model_key:
        provider_type = get_provider_for_model(model_key)
        return provider_type, model_key
    else:
        # Use legacy PROVIDER environment variable for backward compatibility
        legacy_provider = os.getenv("PROVIDER", "claude").lower()

        if legacy_provider == "claude":
            return "claude", DEFAULT_CLAUDE_MODEL
        elif legacy_provider == "parasail":
            return "parasail", DEFAULT_PARASAIL_MODEL
        else:
            logger.warning(f"Unknown PROVIDER: {legacy_provider}. Defaulting to Claude.")
            return "claude", DEFAULT_CLAUDE_MODEL


def get_default_model_and_provider() -> Tuple[ModelProvider, str]:
    """Get the default model and provider using the new model manager."""
    # Environment variables for Claude configuration
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")

    provider_type, model_name = resolve_model_and_provider()

    if provider_type == "claude":
        if not CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY is required for Claude provider")
        return ClaudeModelProvider(CLAUDE_BASE_URL, CLAUDE_API_KEY), model_name
    elif provider_type == "parasail":
        return ParasailModelProvider(), model_name
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")


def create_model_provider_for_model(model_key: str) -> Tuple[ModelProvider, str]:
    """Create a model provider for a specific model key and return the actual model to use."""
    # Environment variables for Claude configuration
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")

    provider_type = get_provider_for_model(model_key)

    if provider_type == "claude":
        if not CLAUDE_API_KEY:
            raise ValueError(f"CLAUDE_API_KEY is required for model {model_key}")
        return ClaudeModelProvider(CLAUDE_BASE_URL, CLAUDE_API_KEY), model_key
    elif provider_type == "parasail":
        return ParasailModelProvider(), model_key
    elif provider_type == "parasail-image":
        # Image models can't be used as regular LLM providers
        raise ValueError(f"Model {model_key} is an image generation model, not suitable for text generation")
    else:
        raise ValueError(f"Unsupported provider type: {provider_type} for model {model_key}")


def resolve_model(model_key: str) -> str:
    """Resolve a model key to the actual model name that should be used, handling fallbacks automatically."""
    _, actual_model = create_model_provider_for_model(model_key)
    return actual_model


def get_model_provider_for_resolved_model(resolved_model: str) -> ModelProvider:
    """Get the appropriate provider for a resolved model name."""
    provider_type = get_provider_for_model(resolved_model)

    if provider_type == "claude":
        CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
        CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")
        if not CLAUDE_API_KEY:
            raise ValueError(f"CLAUDE_API_KEY is required for model {resolved_model}")
        return ClaudeModelProvider(CLAUDE_BASE_URL, CLAUDE_API_KEY)
    elif provider_type == "parasail":
        return ParasailModelProvider()
    else:
        raise ValueError(f"Unsupported provider type: {provider_type} for model {resolved_model}")


def log_model_initialization(model_provider: ModelProvider, model_name: str) -> None:
    """Log model initialization details."""
    if isinstance(model_provider, ClaudeModelProvider):
        provider_type = "claude"
    elif isinstance(model_provider, ParasailModelProvider):
        provider_type = "parasail"
    else:
        provider_type = "unknown"
    logger.info(f"Initialized model provider: {provider_type}, model: {model_name}")


T = TypeVar('T')


async def retry_with_fallback(
    model_key: str,
    operation: Callable[[str, ModelProvider], Awaitable[T]],
    max_retries_per_model: int = 2,
    retry_on_validation_failure: bool = True
) -> Tuple[T, str]:
    """
    Execute an async operation with automatic model fallback on failure.

    Args:
        model_key: The primary model to try first
        operation: Async function that takes (model_name, model_provider) and returns result
        max_retries_per_model: Number of retries per model for validation failures
        retry_on_validation_failure: Whether to retry on validation failures vs immediate fallback

    Returns:
        Tuple of (result, successful_model_key)

    Raises:
        Exception: If all models in the fallback chain fail

    Example:
        async def generate_text(model: str, provider: ModelProvider) -> str:
            # Your generation logic here
            return await provider.generate(...)

        result, model_used = await retry_with_fallback(
            generate_text
        )
    """
    # Build the full chain: primary model + fallbacks
    models_to_try = [model_key] + get_fallback_models(model_key)

    last_error = None

    for model in models_to_try:
        logger.info(f"🔄 Trying model: {model}")

        # Retry logic for each model
        for retry in range(max_retries_per_model):
            try:
                retry_msg = f" (retry {retry + 1}/{max_retries_per_model})" if retry > 0 else ""
                logger.info(f"  Attempting with model: {model}{retry_msg}")

                # Get provider for this model
                provider = get_model_provider_for_resolved_model(model)

                # Execute the operation
                result = await operation(model, provider)

                logger.info(f"✅ Successfully completed with model: {model}")
                return result, model

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                error_type = type(e).__name__

                # Check if it's a provider/API failure (immediate fallback)
                is_provider_failure = (
                    "429" in str(e) or
                    "rate limit" in error_str or
                    "overloaded" in error_str or
                    "api" in error_str or
                    "connection" in error_str or
                    "timeout" in error_str or
                    "badrequesterror" in error_type.lower() or
                    "credit balance" in error_str or
                    "insufficient" in error_str or
                    "runtimeerror" in error_type.lower()
                )

                if is_provider_failure:
                    logger.warning(f"⚠️ Provider failure with {model}: {e}")
                    logger.info(f"  Skipping retries, moving to next model in fallback chain")
                    break  # Skip to next model

                # For validation failures, retry if enabled
                if retry_on_validation_failure and retry < max_retries_per_model - 1:
                    logger.warning(f"⚠️ Validation failure with {model}: {e}")
                    logger.info(f"  Will retry with same model")
                    continue  # Retry same model
                else:
                    logger.warning(f"⚠️ Failed with {model}: {e}")
                    break  # Move to next model

    # All models failed
    error_msg = f"All models in fallback chain failed. Last error: {last_error}"
    logger.error(f"❌ {error_msg}")
    raise Exception(error_msg) from last_error