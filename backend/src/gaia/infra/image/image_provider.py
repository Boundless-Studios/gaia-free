"""
Abstract Base Class for Image Generation Providers

This module defines the interface that all image generation providers must implement,
ensuring consistent behavior and making the system extensible.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    """Describes what an image provider can do"""
    supports_negative_prompt: bool = False
    supports_seed: bool = False
    supports_guidance_scale: bool = False
    supports_inference_steps: bool = False
    supports_variable_size: bool = True
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    supported_formats: List[str] = None

    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = ["url", "b64_json"]


class ImageProvider(ABC):
    """
    Abstract base class for all image generation providers.

    All providers (local, cloud, etc.) must implement this interface to ensure
    consistent behavior and enable seamless switching between providers.
    """

    @abstractmethod
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
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate image(s) from a text prompt.

        Args:
            prompt: Text description of the image to generate
            width: Image width in pixels (default: 1024)
            height: Image height in pixels (default: 1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" for file path, "b64_json" for base64)
            negative_prompt: What to avoid in the image (optional)
            seed: Random seed for reproducibility (optional)
            guidance_scale: How closely to follow the prompt (optional)
            num_inference_steps: Number of denoising steps (optional)
            **kwargs: Provider-specific additional parameters

        Returns:
            Dict with structure:
            {
                "success": bool,
                "images": [
                    {
                        "url": str (if response_format="url"),
                        "b64_json": str (if response_format="b64_json"),
                        "path": str (local file path),
                        ...additional metadata
                    }
                ],
                "error": str (if success=False),
                "provider": str (provider name),
                "model": str (model used)
            }
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """
        Get the capabilities of this provider.

        Returns:
            ProviderCapabilities describing what this provider supports
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the provider and current model.

        Returns:
            Dict with structure:
            {
                "provider": str,
                "model": str,
                "model_key": str,
                "configured": bool,
                "connected": bool,
                ...additional provider-specific info
            }
        """
        pass

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the given model.

        Args:
            model: Model identifier (could be pipeline_type, model name, etc.)

        Returns:
            True if this provider can handle the model, False otherwise
        """
        pass

    def is_available(self) -> bool:
        """
        Check if this provider is currently available and ready to use.

        Default implementation checks if provider is configured.
        Override for more complex availability checks.

        Returns:
            True if provider is ready to generate images, False otherwise
        """
        try:
            info = self.get_model_info()
            return info.get("configured", False)
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider name (e.g., "flux_local", "runware", "gemini")
        """
        info = self.get_model_info()
        return info.get("provider", self.__class__.__name__)
