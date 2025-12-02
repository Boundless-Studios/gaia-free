"""
Central image generation configuration.
Aggregates providers and manages global settings.

This is a thin aggregation layer that imports provider-specific configurations
and provides a unified interface for accessing all models and providers.
"""

import logging
from typing import Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================

# Which provider to prefer by default
DEFAULT_PROVIDER = "runware"


def get_providers():
    """
    Get provider registry dynamically.

    Import providers here to avoid circular dependencies.
    Returns dict of {provider_name: ProviderInfo}
    """
    try:
        from gaia.infra.image.providers.runware import RUNWARE_PROVIDER
    except ImportError:
        logger.warning("Could not import RUNWARE_PROVIDER")
        RUNWARE_PROVIDER = None

    try:
        from gaia.infra.image.providers.flux import FLUX_LOCAL_PROVIDER
    except ImportError:
        logger.warning("Could not import FLUX_LOCAL_PROVIDER")
        FLUX_LOCAL_PROVIDER = None

    try:
        from gaia.infra.image.providers.gemini import GEMINI_PROVIDER
    except ImportError:
        logger.warning("Could not import GEMINI_PROVIDER")
        GEMINI_PROVIDER = None

    providers = {}
    if RUNWARE_PROVIDER:
        providers["runware"] = RUNWARE_PROVIDER
    if FLUX_LOCAL_PROVIDER:
        providers["flux_local"] = FLUX_LOCAL_PROVIDER
    if GEMINI_PROVIDER:
        providers["gemini"] = GEMINI_PROVIDER

    return providers


def get_default_model() -> str:
    """Get the default model for the default provider"""
    providers = get_providers()
    provider = providers.get(DEFAULT_PROVIDER)
    if provider:
        return provider.default_model
    # Fallback to highest priority provider
    if providers:
        sorted_providers = sorted(providers.values(), key=lambda p: p.priority)
        return sorted_providers[0].default_model if sorted_providers else "lightning_4step"
    return "lightning_4step"  # Hard fallback


# Current model (can be changed at runtime)
CURRENT_MODEL = get_default_model()


class ImageGenerationConfig:
    """Aggregates configuration from all providers"""

    def __init__(self):
        self.current_model = CURRENT_MODEL
        self.providers = get_providers()

    def get_all_models(self) -> Dict[str, Tuple[str, Any]]:
        """
        Get all models from all providers.

        Returns: {model_key: (provider_name, model_config)}
        """
        all_models = {}
        for provider_name, provider_info in self.providers.items():
            for model_key, model_config in provider_info.models.items():
                all_models[model_key] = (provider_name, model_config)
        return all_models

    def get_current_config(self):
        """Get configuration for currently selected model"""
        all_models = self.get_all_models()
        if self.current_model in all_models:
            provider_name, model_config = all_models[self.current_model]
            return model_config
        # Fallback to default
        logger.warning(f"Model '{self.current_model}' not found, using default")
        default_model = get_default_model()
        if default_model in all_models:
            self.current_model = default_model
            provider_name, model_config = all_models[default_model]
            return model_config
        raise ValueError(f"No models available! Tried: {self.current_model}, {default_model}")

    def get_provider_for_model(self, model_key: str) -> Optional[str]:
        """Get which provider owns this model"""
        all_models = self.get_all_models()
        if model_key in all_models:
            provider_name, _ = all_models[model_key]
            return provider_name
        return None

    def set_model(self, model_key: str) -> bool:
        """Set the current model (only if it exists)"""
        all_models = self.get_all_models()
        if model_key in all_models:
            self.current_model = model_key
            return True
        logger.error(f"Unknown model: {model_key}")
        return False

    def get_available_models(self) -> Dict[str, str]:
        """Get list of available models (backward compatibility)"""
        all_models = self.get_all_models()
        return {key: config.name for key, (provider, config) in all_models.items()}

    def parse_size_string(self, size_str: str) -> Tuple[int, int]:
        """Parse size string like '1024x768' into (width, height)"""
        if 'x' in size_str:
            width, height = map(int, size_str.split('x'))
            return width, height
        else:
            # Square size
            size = int(size_str)
            return size, size


# Global configuration instance (singleton)
_config = None


def get_image_config() -> ImageGenerationConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = ImageGenerationConfig()
    return _config
