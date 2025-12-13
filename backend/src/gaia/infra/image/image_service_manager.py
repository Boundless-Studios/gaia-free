"""
Image Service Manager
Central router that manages all image generation providers and routes requests appropriately.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from gaia.infra.image.image_provider import ImageProvider
from gaia.infra.image.image_config import get_image_config

logger = logging.getLogger(__name__)


class ImageServiceManager:
    """
    Central manager that routes image generation requests to appropriate services.

    This manager implements the Strategy pattern, maintaining a registry of image providers
    and routing requests based on model capabilities and configuration.
    """

    def __init__(self):
        self.config = get_image_config()
        self.providers: Dict[str, ImageProvider] = {}
        self._providers_initialized = False
        self._runware_pool = None  # Lazy-initialized pool for parallel generation
        self._register_providers()

    def _register_providers(self):
        """Discover and register all available image providers (only once)."""
        if self._providers_initialized:
            logger.debug("Providers already initialized, skipping registration")
            return

        # Import providers dynamically to avoid circular dependencies
        from gaia.infra.image.providers.flux import get_flux_local_image_service
        from gaia.infra.image.providers.runware import get_runware_image_service
        from gaia.infra.image.providers.gemini import get_gemini_image_service

        # Register providers (singletons will return None if not configured)
        flux_service = get_flux_local_image_service()
        if flux_service:
            self.providers["flux_local"] = flux_service
            logger.info("Registered Flux Local image provider")

        runware_service = get_runware_image_service()
        if runware_service:
            self.providers["runware"] = runware_service
            logger.info("Registered Runware image provider")

        gemini_service = get_gemini_image_service()
        if gemini_service:
            self.providers["gemini"] = gemini_service
            logger.info("Registered Gemini image provider")

        if not self.providers:
            logger.warning("No image providers registered! Image generation will not be available.")
        else:
            provider_list = ", ".join(self.providers.keys())
            logger.info(f"Image Service Manager initialized with {len(self.providers)} provider(s): {provider_list}")

        self._providers_initialized = True

    def get_available_provider_with_fallback(self) -> tuple[str, str]:
        """
        Get the best available provider and its default model.

        Returns: (provider_name, model_key)

        Raises: RuntimeError if no providers available

        This is DETERMINISTIC - same inputs = same outputs.
        No runtime surprises.
        """
        from gaia.infra.image.image_config import DEFAULT_PROVIDER

        # Get all provider configs
        provider_configs = self.config.providers

        # Try default provider first
        if DEFAULT_PROVIDER in provider_configs:
            provider_config = provider_configs[DEFAULT_PROVIDER]
            if DEFAULT_PROVIDER in self.providers and \
               self.providers[DEFAULT_PROVIDER].is_available():
                logger.info(f"✅ Using preferred provider: {DEFAULT_PROVIDER} "
                           f"with model: {provider_config.default_model}")
                return (DEFAULT_PROVIDER, provider_config.default_model)
            else:
                logger.warning(f"⚠️  Preferred provider '{DEFAULT_PROVIDER}' is not available")

        # Fallback: try providers in priority order
        sorted_providers = sorted(
            [(name, info) for name, info in provider_configs.items()],
            key=lambda x: x[1].priority
        )

        for provider_name, provider_config in sorted_providers:
            if provider_name in self.providers and \
               self.providers[provider_name].is_available():
                logger.warning(f"🔄 Using fallback provider: {provider_name} "
                              f"with model: {provider_config.default_model}")
                return (provider_name, provider_config.default_model)

        # No providers available
        raise RuntimeError(
            "No image providers available! Please configure at least one provider:\n"
            "- Runware: Set RUNWARE_API_KEY environment variable\n"
            "- Flux Local: Ensure CUDA GPU is available\n"
            "- Gemini: Set GEMINI_API_KEY environment variable"
        )

    def get_provider_for_model(self, model: Optional[str] = None) -> Optional[ImageProvider]:
        """
        Get the appropriate provider for the specified model or current config.

        Uses deterministic fallback logic via get_available_provider_with_fallback().

        Args:
            model: Model identifier (model_key to look up in config)

        Returns:
            ImageProvider instance or None if no suitable provider found
        """
        # Priority 1: Explicit model key lookup
        if model:
            provider_name = self.config.get_provider_for_model(model)
            if provider_name and provider_name in self.providers:
                provider = self.providers[provider_name]
                if provider.is_available():
                    logger.debug(f"Selected {provider_name} provider for model: {model}")
                    return provider
                else:
                    logger.warning(f"Provider {provider_name} for model {model} is not available")

        # Priority 2: Use current config model
        try:
            current_model_key = self.config.current_model
            provider_name = self.config.get_provider_for_model(current_model_key)

            if provider_name and provider_name in self.providers:
                provider = self.providers[provider_name]
                if provider.is_available():
                    logger.debug(f"Using current config provider: {provider_name}")
                    return provider
                else:
                    logger.warning(f"Current provider {provider_name} is not available")

        except Exception as e:
            logger.error(f"Could not get current config: {e}")

        # Priority 3: Use deterministic fallback
        try:
            provider_name, model_key = self.get_available_provider_with_fallback()
            if provider_name in self.providers:
                logger.info(f"Using fallback provider: {provider_name} with model: {model_key}")
                return self.providers[provider_name]
        except RuntimeError as e:
            logger.error(f"No providers available: {e}")
            return None

        logger.error("No image providers available!")
        return None

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        response_format: str = "b64_json",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate image using the appropriate provider.

        Routes to provider based on model parameter or current configuration.

        Args:
            prompt: Text description of the image
            width: Image width in pixels (default: 1024)
            height: Image height in pixels (default: 1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" for file path, "b64_json" for base64)
            negative_prompt: What to avoid in the image (optional)
            seed: Random seed for reproducibility (optional)
            guidance_scale: How closely to follow the prompt (optional)
            num_inference_steps: Number of denoising steps (optional)
            model: Specific model to use (optional - will use config if not specified)
            **kwargs: Provider-specific additional parameters

        Returns:
            Dict with structure:
            {
                "success": bool,
                "images": [...],
                "provider": str,
                "model": str,
                "error": str (if success=False)
            }
        """
        # Resolve model_key if not specified
        # This ensures providers receive the current model_key from config
        model_key = model if model is not None else self.config.current_model
        logger.debug(f"Using model_key: {model_key} (from {'parameter' if model else 'config'})")

        # Get appropriate provider
        provider = self.get_provider_for_model(model_key)

        if not provider:
            return {
                "success": False,
                "error": "No image provider available for the requested model",
                "images": [],
                "provider": "none"
            }

        # Route to provider with the resolved model_key
        try:
            result = await provider.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                n=n,
                response_format=response_format,
                negative_prompt=negative_prompt,
                seed=seed,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                model=model_key,
                **kwargs
            )
            return result
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return {
                "success": False,
                "error": f"Image generation failed: {str(e)}",
                "images": [],
                "provider": provider.get_provider_name() if provider else "unknown"
            }

    def get_available_models(self) -> Dict[str, Any]:
        """
        Get all available models from all providers.

        Returns:
            Dict with list of models from all providers
        """
        all_models = []

        for provider_name, provider in self.providers.items():
            try:
                if hasattr(provider, 'get_available_models'):
                    # Provider has a specific method to list models
                    models = provider.get_available_models()
                    if isinstance(models, list):
                        all_models.extend(models)
                else:
                    # Fallback: use model info
                    info = provider.get_model_info()
                    all_models.append({
                        "id": info.get("model_key", provider_name),
                        "name": info.get("model", provider_name),
                        "provider": provider_name,
                        "type": "text-to-image"
                    })
            except Exception as e:
                logger.warning(f"Could not get models from {provider_name}: {e}")

        return {"models": all_models}

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get health status of all registered providers.

        Returns:
            Dict mapping provider names to health status
        """
        health = {}

        for provider_name, provider in self.providers.items():
            try:
                info = provider.get_model_info()
                health[provider_name] = {
                    "available": provider.is_available(),
                    "model": info.get("model", "unknown")
                }
            except Exception as e:
                logger.error(f"Error checking health for {provider_name}: {e}")
                health[provider_name] = {
                    "available": False,
                    "error": str(e)
                }

        return health

    def get_provider_capabilities(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get capabilities of a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Dict of capabilities or None if provider not found
        """
        provider = self.providers.get(provider_name)
        if not provider:
            return None

        try:
            caps = provider.get_capabilities()
            return {
                "supports_negative_prompt": caps.supports_negative_prompt,
                "supports_seed": caps.supports_seed,
                "supports_guidance_scale": caps.supports_guidance_scale,
                "supports_inference_steps": caps.supports_inference_steps,
                "supports_variable_size": caps.supports_variable_size,
                "max_width": caps.max_width,
                "max_height": caps.max_height,
                "supported_formats": caps.supported_formats
            }
        except Exception as e:
            logger.error(f"Error getting capabilities for {provider_name}: {e}")
            return None

    def switch_model(self, model_key: str) -> Dict[str, Any]:
        """
        Switch to a different image generation model.

        This delegates to the appropriate provider(s) to handle resource management.

        Args:
            model_key: The model key to switch to

        Returns:
            Dict with model information and success status
        """
        # Check if model exists
        all_models = self.config.get_all_models()
        if model_key not in all_models:
            return {
                "success": False,
                "error": f"Unknown model: {model_key}"
            }

        # Get the provider for the new model
        new_provider_name = self.config.get_provider_for_model(model_key)
        if not new_provider_name:
            return {
                "success": False,
                "error": f"No provider found for model: {model_key}"
            }

        # Switch the model in the global config
        success = self.config.set_model(model_key)
        if not success:
            return {
                "success": False,
                "error": "Failed to switch model in config"
            }

        # Notify the provider that owns this model
        # Each provider handles its own resource management (GPU cleanup, config updates, etc.)
        if new_provider_name in self.providers:
            provider = self.providers[new_provider_name]
            if hasattr(provider, 'switch_model'):
                try:
                    provider.switch_model(model_key)
                except Exception as e:
                    logger.warning(f"Provider {new_provider_name} switch_model failed: {e}")

        # Get the new config
        current_config = self.config.get_current_config()
        logger.info(f"Switched to model: {model_key} ({current_config.name} via {new_provider_name})")

        # Build response dict with only attributes that exist on the config
        response_model = {
            "key": model_key,
            "name": current_config.name,
            "steps": current_config.steps,
            "guidance_scale": current_config.guidance_scale,
            "supports_negative_prompt": current_config.supports_negative_prompt,
            "provider": new_provider_name
        }

        # Add optional attributes only if they exist
        if hasattr(current_config, 'checkpoint_name'):
            response_model["checkpoint_name"] = current_config.checkpoint_name
        if hasattr(current_config, 'pipeline_type'):
            response_model["pipeline_type"] = current_config.pipeline_type
        if hasattr(current_config, 'model_id'):
            response_model["model_id"] = current_config.model_id

        return {
            "success": True,
            "model": response_model
        }

    def _get_runware_pool(self):
        """Get or create the Runware client pool for parallel generation."""
        if self._runware_pool is None:
            from gaia.infra.image.providers.runware_pool import get_runware_client_pool
            self._runware_pool = get_runware_client_pool()
        return self._runware_pool

    async def generate_images_parallel(
        self,
        requests: List[Dict[str, Any]],
        use_pool: bool = True,
    ) -> List[Dict[str, Any]]:
        """Generate multiple images in parallel.

        Uses the Runware client pool for true parallel generation when available,
        otherwise falls back to concurrent calls through the standard provider.

        Args:
            requests: List of dicts, each containing kwargs for generate_image()
                     Example: [
                         {"prompt": "A forest", "width": 1024, "height": 1024},
                         {"prompt": "A castle"},
                         {"prompt": "A dragon", "model": "hidream_fast"},
                     ]
            use_pool: If True, use the Runware pool for parallel WebSocket
                     connections. If False, use standard sequential generation.

        Returns:
            List of results in the same order as requests. Each result dict has:
            - success: bool
            - images: list of generated images
            - provider: str
            - error: str (if success=False)
        """
        if not requests:
            return []

        logger.info(f"🎨 Generating {len(requests)} images in parallel")

        # Check if we can use the Runware pool for true parallelism
        pool = self._get_runware_pool() if use_pool else None

        if pool and pool.is_available():
            # Use the pool for parallel generation
            logger.debug("Using Runware pool for parallel generation")
            return await pool.generate_images_parallel(requests)

        # Fallback: use asyncio.gather with the standard provider
        # Note: This may still be serialized if the provider has a semaphore
        logger.debug("Using standard provider (may be serialized)")

        async def generate_single(request: Dict[str, Any]) -> Dict[str, Any]:
            try:
                return await self.generate_image(**request)
            except Exception as e:
                logger.error(f"Error generating image: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "images": [],
                    "provider": "unknown"
                }

        results = await asyncio.gather(
            *[generate_single(req) for req in requests],
            return_exceptions=False
        )

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"✅ Parallel generation complete: {success_count}/{len(requests)} succeeded")

        return results

    async def disconnect_pools(self) -> None:
        """Disconnect any active client pools.

        Call this during application shutdown.
        """
        if self._runware_pool:
            await self._runware_pool.disconnect_all()
            self._runware_pool = None


# Singleton instance
_image_service_manager = None


def get_image_service_manager() -> ImageServiceManager:
    """Get the singleton image service manager instance."""
    global _image_service_manager
    if _image_service_manager is None:
        _image_service_manager = ImageServiceManager()
    return _image_service_manager
