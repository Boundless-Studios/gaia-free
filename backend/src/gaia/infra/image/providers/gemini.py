"""
Gemini Image Generation Service
Handles image generation using Google's Gemini API
"""

import os
import logging
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
import time
import aiohttp
from dataclasses import dataclass, field
try:
    # Try new API first
    from google import genai
    from google.genai import types
    NEW_API = True
except ImportError:
    # Fall back to old API
    import google.generativeai as genai
    from google.generativeai import types
    NEW_API = False

import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
from PIL import Image
from io import BytesIO
from gaia.infra.image.image_provider import ImageProvider, ProviderCapabilities

logger = logging.getLogger(__name__)

# =============================================================================
# Provider Configuration
# =============================================================================

@dataclass
class GeminiModelConfig:
    """Configuration for a Gemini model"""
    name: str
    model_id: str  # Required! (e.g., "gemini-2.0-flash-preview-image-generation")
    supports_negative_prompt: bool = False
    supports_seed: bool = False
    supports_guidance: bool = False
    max_resolution: int = 2048

@dataclass
class GeminiProviderInfo:
    """Provider-level configuration"""
    name: str = "gemini"
    display_name: str = "Google Gemini"
    description: str = "Google's Gemini AI image generation"
    default_model: str = "gemini_imagen_3"
    priority: int = 3  # Last priority (experimental)
    models: Dict[str, GeminiModelConfig] = field(default_factory=dict)

GEMINI_MODELS = {
    "gemini_imagen_3": GeminiModelConfig(
        name="Gemini Imagen 3 (Flash)",
        model_id="gemini-2.0-flash-preview-image-generation",
        supports_negative_prompt=False,
        supports_seed=False,
        supports_guidance=False
    ),
}

GEMINI_PROVIDER = GeminiProviderInfo(
    default_model="gemini_imagen_3",
    models=GEMINI_MODELS
)


class GeminiImageService(ImageProvider):
    """Service for handling image generation using Gemini API"""
    
    def __init__(self):
        self.provider_info = GEMINI_PROVIDER
        self.models = GEMINI_MODELS
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            logger.info("ℹ️  Gemini image provider not available - API key not configured")
        elif not NEW_API:
            logger.info("ℹ️  Gemini image provider not available - requires new google-genai package")
        else:
            # New API uses client initialization
            self.client = genai.Client(api_key=self.api_key)
            self.executor = ThreadPoolExecutor(max_workers=5)
            logger.info(f"✅ Gemini image service initialized successfully")

    def get_default_model(self) -> str:
        """Get the default model for this provider"""
        return self.provider_info.default_model

    def is_available(self) -> bool:
        """
        Check if this provider is available and ready to use.

        Single source of truth for availability.
        For Gemini cloud service, we check if:
        1. API key is configured
        2. New API is available (old API doesn't support image generation)

        Returns:
            True if provider can generate images
        """
        return bool(self.api_key) and NEW_API
    
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
        Generate an image using Gemini 2.0 Flash API.

        This service handles Google Gemini cloud models.

        Args:
            prompt: Text description of the image
            width: Image width (used to construct size string)
            height: Image height (used to construct size string)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            negative_prompt: Not supported by Gemini (ignored)
            seed: Not supported by Gemini (ignored)
            guidance_scale: Not supported by Gemini (ignored)
            num_inference_steps: Not supported by Gemini (ignored)
            model: Gemini model ID (default: gemini-2.0-flash-preview-image-generation)
            **kwargs: Additional provider-specific parameters (ignored)

        Returns:
            Dict containing image generation results
        """
        if not self.is_available():
            error_msg = "Gemini not available. "
            if not self.api_key:
                error_msg += "API key not configured. "
            if not NEW_API:
                error_msg += "Requires new google-genai package (pip install google-genai)."
            return {
                "success": False,
                "error": error_msg,
                "images": [],
                "provider": "gemini"
            }

        # Use default model if not specified
        if model is None:
            model = "gemini-2.0-flash-preview-image-generation"

        # Construct size string from width/height
        size = f"{width}x{height}"
        
        try:
            logger.info(f"Image generation requested with Gemini 2.0 Flash")
            logger.info(f"Prompt: {prompt[:100]}...")
            
            loop = asyncio.get_event_loop()
            
            if NEW_API:
                # Use new API
                logger.info(f"Using new Gemini API with model: {model}")
                response = await loop.run_in_executor(
                    self.executor,
                    lambda: self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=['TEXT', 'IMAGE']
                        )
                    )
                )
                logger.info("Gemini API call completed")
            else:
                # Use old API - it doesn't support image generation directly
                logger.warning("Old Gemini API doesn't support direct image generation")
                return {
                    "success": False,
                    "error": "Image generation requires the new google-genai package. Please install: pip install google-genai",
                    "images": [],
                    "provider": "gemini"
                }
            
            # Extract images from response
            images = []
            if response.candidates:
                logger.info(f"Found {len(response.candidates)} candidates in response")
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        logger.info(f"Found {len(candidate.content.parts)} parts in candidate")
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                logger.info(f"Found inline data with mime type: {part.inline_data.mime_type}")
                                if part.inline_data.mime_type.startswith('image/'):
                                    # Convert to base64
                                    image_data = part.inline_data.data
                                    logger.info(f"Found image data, size: {len(image_data)} bytes")
                                    if response_format == "b64_json":
                                        images.append({
                                            "b64_json": base64.b64encode(image_data).decode('utf-8'),
                                            "mime_type": part.inline_data.mime_type
                                        })
                                    else:
                                        # Save and return URL
                                        path = await self.save_image_from_bytes(
                                            image_data,
                                            mime_type=part.inline_data.mime_type,
                                            output_dir=kwargs.get('output_dir')
                                        )
                                        images.append({
                                            "url": f"file://{path}",
                                            "path": path
                                        })
                                        logger.info(f"Saved image to: {path}")
            
            # Extract any text from response
            text_content = ""
            if response.text:
                text_content = response.text
            
            if images:
                logger.info(f"✅ Generated {len(images)} images")
                return {
                    "success": True,
                    "images": images[:n],  # Return requested number of images
                    "provider": "gemini",
                    "model": model,
                    "text": text_content,
                    "prompt": prompt
                }
            else:
                logger.warning("No images generated in response")
                return {
                    "success": False,
                    "error": "No images generated. The model may have chosen to only provide text.",
                    "images": [],
                    "provider": "gemini",
                    "text": text_content,
                    "prompt": prompt
                }
            
        except Exception as e:
            logger.error(f"Error in Gemini image generation: {e}")
            return {
                "success": False,
                "error": str(e),
                "images": [],
                "provider": "gemini"
            }
    
    async def _enhance_prompt(self, prompt: str) -> str:
        """Enhance the image generation prompt using Gemini"""
        try:
            enhancement_prompt = f"""You are an expert at creating detailed image generation prompts.
Take this prompt and enhance it with more visual details, artistic style, lighting, and composition:

Original prompt: {prompt}

Enhanced prompt (be specific and visual):"""
            
            # Run in thread pool since genai is sync
            loop = asyncio.get_event_loop()
            
            if NEW_API:
                response = await loop.run_in_executor(
                    self.executor,
                    lambda: self.client.models.generate_content(
                        model='gemini-1.5-flash-8b',
                        contents=enhancement_prompt
                    )
                )
            else:
                model = genai.GenerativeModel('gemini-1.5-flash-8b')
                response = await loop.run_in_executor(
                    self.executor,
                    model.generate_content,
                    enhancement_prompt
                )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error enhancing prompt: {e}")
            return prompt
    
    async def analyze_image(self, image_path: str, question: str = "Describe this image") -> Optional[str]:
        """
        Analyze an image using Gemini's vision capabilities

        Args:
            image_path: Path to the image file
            question: Question to ask about the image

        Returns:
            Analysis text or None if failed
        """
        if not self.is_available():
            return None
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash-8b')
            
            # Upload the image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Create the request
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: model.generate_content([question, image_data])
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return None
    
    async def batch_enhance_prompts(self, prompts: List[str]) -> List[str]:
        """
        Enhance multiple prompts in parallel
        
        Args:
            prompts: List of prompts to enhance
            
        Returns:
            List of enhanced prompts
        """
        tasks = [self._enhance_prompt(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)
    
    async def save_image_from_bytes(self, image_data: bytes, mime_type: str = "image/png", output_dir: str = None) -> Optional[str]:
        """
        Save image bytes to disk
        
        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            output_dir: Directory to save the image
            
        Returns:
            Path to saved image or None if failed
        """
        try:
            # Use environment variable if output_dir not specified
            if output_dir is None:
                output_dir = os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images')
            
            # Expand ~ in path
            output_dir = os.path.expanduser(output_dir)
            
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Determine extension from mime type
            ext = mime_type.split('/')[-1] if '/' in mime_type else 'png'
            
            # Generate filename
            filename = f"gemini_image_{int(time.time() * 1000)}.{ext}"
            filepath = Path(output_dir) / filename
            
            # Save image
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"Saved image to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return None
    
    async def save_image_from_base64(self, b64_data: str, output_dir: str = None) -> Optional[str]:
        """
        Save a base64-encoded image to disk
        
        Args:
            b64_data: Base64-encoded image data
            output_dir: Directory to save the image
            
        Returns:
            Path to saved image or None if failed
        """
        try:
            # Use environment variable if output_dir not specified
            if output_dir is None:
                output_dir = os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images')
            
            # Expand ~ in path
            output_dir = os.path.expanduser(output_dir)
            
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            filename = f"gemini_image_{int(time.time() * 1000)}.png"
            filepath = Path(output_dir) / filename
            
            # Decode and save
            image_data = base64.b64decode(b64_data)
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"Saved base64 image to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving base64 image: {e}")
            return None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this Gemini provider."""
        return ProviderCapabilities(
            supports_negative_prompt=False,  # Gemini doesn't support negative prompts
            supports_seed=False,  # Gemini doesn't support seeds
            supports_guidance_scale=False,  # Gemini doesn't support guidance scale
            supports_inference_steps=False,  # Gemini doesn't support inference steps
            supports_variable_size=True,  # Can generate various sizes
            max_width=2048,
            max_height=2048,
            supported_formats=["url", "b64_json"]
        )

    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the given model.

        Supports Gemini cloud models (gemini pipeline_type or gemini-* model IDs).

        Args:
            model: Model identifier (pipeline_type, model name, etc.)

        Returns:
            True if this is a Gemini model
        """
        model_lower = model.lower()
        # Check if it's the gemini pipeline type
        if model_lower == "gemini":
            return True
        # Check if it's a Gemini model ID (starts with gemini-)
        if model_lower.startswith("gemini-"):
            return True
        return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the Gemini service."""
        return {
            "provider": "gemini",
            "model": self.provider_info.default_model,
            "model_key": "gemini",
            "available": self.is_available(),
            "api_version": "new" if NEW_API else "old",
            "api_key_configured": bool(self.api_key),
            "supports_image_generation": NEW_API,
            "features": [
                "text-to-image",
                "prompt-enhancement",
                "image-analysis"
            ]
        }


# Singleton instance
_gemini_service = None

def get_gemini_image_service() -> Optional[GeminiImageService]:
    """Get the singleton Gemini image service instance."""
    global _gemini_service

    if _gemini_service is None:
        _gemini_service = GeminiImageService()

    return _gemini_service if _gemini_service.is_available() else None