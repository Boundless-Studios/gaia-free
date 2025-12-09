"""
Runware Image Generation Service
Handles image generation using Runware's WebSocket API

Features:
- Automatic retry logic for transient errors (authentication, network, timeouts)
- Exponential backoff for retries
- Forced reconnection on authentication failures
- Configurable via environment variables:
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
import time
import base64
from io import BytesIO
from PIL import Image
import aiohttp
from dataclasses import dataclass, field
from gaia.infra.image.image_provider import ImageProvider, ProviderCapabilities

logger = logging.getLogger(__name__)

# =============================================================================
# Provider Configuration
# =============================================================================

@dataclass
class RunwareModelConfig:
    """Configuration for a Runware cloud model"""
    name: str
    model_id: str  # Required! (e.g., "rundiffusion:130@100")
    steps: int = 20
    guidance_scale: float = 7.5
    negative_prompt: Optional[str] = None  # Optional negative prompt (only for models that support it)
    supports_negative_prompt: bool = True
    max_resolution: int = 1024
    scheduler: Optional[str] = None  # Optional scheduler (e.g., "DPM++ 2M Karras", "Euler", "Euler a")
    clip_skip: Optional[int] = None  # Optional CLIP skip value (typically 1-2)
    output_quality: Optional[int] = None  # Optional output quality (0-100, higher is better)

@dataclass
class RunwareProviderInfo:
    """Provider-level configuration"""
    name: str = "runware"
    display_name: str = "Runware Cloud"
    description: str = "Fast cloud-based image generation"
    default_model: str = "hidream_fast"
    priority: int = 1  # Lower = higher priority (preferred provider)
    models: Dict[str, RunwareModelConfig] = field(default_factory=dict)

# Provider's model registry
RUNWARE_MODELS = {
    "juggernaut_pro": RunwareModelConfig(
        name="Juggernaut Pro",
        model_id="rundiffusion:130@100",
        steps=20,
        guidance_scale=7.5
    ),
    "juggernaut_lightning": RunwareModelConfig(
        name="Juggernaut Lightning",
        model_id="rundiffusion:110@101",
        steps=4,
        guidance_scale=1.0
    ),
    "flux_schnell": RunwareModelConfig(
        name="Flux Schnell",
        model_id="runware:100@1",
        steps=4,
        guidance_scale=3.5
    ),
    "hidream_fast": RunwareModelConfig(
        name="Hidream Fast",
        model_id="runware:97@3",
        steps=16,
        guidance_scale=1.0,
        scheduler="DPM++ 2M Karras",
        negative_prompt="cartoon, anime, drawing, painting, illustration, 3d render, render, cgi, deformed, disfigured, malformed hands, extra limbs, blurry, out of focus, low quality, bad anatomy, watermark, text, signature, simplistic",
        clip_skip=1,
        output_quality=85
    ),
}

# Provider info singleton
RUNWARE_PROVIDER = RunwareProviderInfo(
    models=RUNWARE_MODELS
)

# Import Runware SDK
try:
    from runware import Runware, IImageInference, IImageUpscale, IImageBackgroundRemoval
    RUNWARE_AVAILABLE = True
except ImportError:
    logger.warning("Runware SDK not available. Install with: pip install runware")
    RUNWARE_AVAILABLE = False
    # Create dummy classes for type hints
    class Runware:
        pass
    class IImageInference:
        pass
    class IImageUpscale:
        pass
    class IImageBackgroundRemoval:
        pass


class RunwareImageService(ImageProvider):
    """Service for handling image generation using Runware API"""

    # Default configuration (can be overridden by environment variables)
    DEFAULT_TIMEOUT = 120
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 2.0

    def __init__(self):
        self.provider_info = RUNWARE_PROVIDER
        self.models = RUNWARE_MODELS
        self.api_key = os.environ.get('RUNWARE_API_KEY')
        self.client = None
        self._connect_lock = asyncio.Lock()  # Prevent concurrent connection attempts
        # Semaphore to serialize requests - Runware WebSocket doesn't handle concurrent requests well
        self._request_semaphore = asyncio.Semaphore(1)

        # Configuration from environment with fallbacks to defaults
        self.timeout = int(os.getenv('RUNWARE_TIMEOUT', self.DEFAULT_TIMEOUT))
        self.max_retries = int(os.getenv('RUNWARE_MAX_RETRIES', self.DEFAULT_MAX_RETRIES))
        self.retry_delay = float(os.getenv('RUNWARE_RETRY_DELAY', self.DEFAULT_RETRY_DELAY))

        if not RUNWARE_AVAILABLE:
            logger.info("ℹ️  Runware image provider not available - SDK not installed (pip install runware)")
        elif not self.api_key:
            logger.info("ℹ️  Runware image provider not available - API key not configured")
        else:
            logger.debug(f"✅ Runware image service initialized (timeout={self.timeout}s, retries={self.max_retries})")

    def get_default_model(self) -> str:
        """Get the default model for this provider"""
        return self.provider_info.default_model
    
    def is_available(self) -> bool:
        """
        Check if this provider is available and ready to use.

        Single source of truth for availability.
        For Runware cloud service, we check if:
        1. SDK is available
        2. API key is configured

        Returns:
            True if provider can generate images
        """
        return RUNWARE_AVAILABLE and bool(self.api_key)
    
    async def connect(self):
        """
        Establish WebSocket connection to Runware.

        Lazy connection - called on first use.
        Reuses existing connection if available. The SDK handles reconnection
        automatically if the connection drops.

        Uses a lock to prevent race conditions when multiple requests try to
        connect simultaneously (one request could disconnect another's in-progress
        connection if it sees an unauthenticated client).
        """
        # Use lock to prevent concurrent connection attempts
        async with self._connect_lock:
            # Check if API key was loaded after initialization (common with env var loading)
            if not self.api_key:
                self.api_key = os.environ.get('RUNWARE_API_KEY')
                if self.api_key:
                    logger.debug("🔄 Runware API key loaded from environment after initialization")

            if not self.is_available():
                raise RuntimeError(
                    "Runware not available. "
                    f"SDK available: {RUNWARE_AVAILABLE}, "
                    f"API key configured: {bool(self.api_key)}"
                )

            # Check if we have an existing client and if it's authenticated
            if self.client:
                try:
                    # The SDK's isAuthenticated() is the reliable check
                    if self.client.isAuthenticated():
                        logger.debug("Reusing existing authenticated Runware WebSocket connection")
                        # Ensure connection is still active before returning
                        await self.client.ensureConnection()
                        return
                    else:
                        # Connection exists but not authenticated - need to reconnect
                        logger.warning("Existing connection not authenticated, creating new connection...")
                        try:
                            await self.client.disconnect()
                        except Exception:
                            pass  # Ignore disconnect errors
                        self.client = None
                except Exception as e:
                    # If we can't check authentication status, assume connection is bad
                    logger.warning(f"Error checking connection status: {e}, creating new connection")
                    self.client = None

            # Create new client and connect
            logger.debug("Establishing new Runware WebSocket connection...")
            self.client = Runware(api_key=self.api_key)
            await self.client.connect()

            # Verify authentication succeeded
            if not self.client.isAuthenticated():
                self.client = None  # Clear invalid client
                error_msg = "Runware authentication failed - invalid API key"
                logger.error(f"❌ {error_msg}")
                raise RuntimeError(error_msg)

            # Mark authentication as validated
            logger.debug("✅ Connected to Runware WebSocket API (authentication verified)")
    
    async def disconnect(self):
        """
        Close WebSocket connection (only called on shutdown).

        During normal operation, connections are kept alive.
        """
        if self.client:
            try:
                await self.client.disconnect()
                logger.info("Disconnected from Runware API")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.client = None
    
    async def _force_reconnect(self):
        """Force a fresh connection by disconnecting and clearing the client."""
        logger.info("Forcing fresh Runware connection...")
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.client = None
        await self.connect()

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
        scheduler: Optional[str] = None,
        clip_skip: Optional[int] = None,
        output_quality: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate images using Runware cloud API.

        This service handles Runware cloud models via WebSocket API.

        Args:
            prompt: Text description of the image
            model: Model to use (default: rundiffusion:130@100 - Juggernaut Pro)
            width: Image width (default: 1024)
            height: Image height (default: 1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            negative_prompt: What to avoid in the image
            seed: Random seed for reproducibility
            guidance_scale: How closely to follow the prompt (mapped to CFGScale)
            num_inference_steps: Number of denoising steps (mapped to steps)
            scheduler: Scheduler/sampler to use (e.g., "DPM++ 2M Karras", "Euler", "Euler a")
            clip_skip: CLIP skip value (typically 1-2)
            output_quality: Output quality (0-100, higher is better)
            **kwargs: Additional provider-specific parameters (ignored)

        Returns:
            Dict containing image generation results
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "Runware not available (missing SDK or API key)",
                "images": [],
                "provider": "runware"
            }

        # Use semaphore to serialize requests - WebSocket doesn't handle concurrent requests well
        logger.debug(f"🎨 Runware: Waiting for semaphore (prompt: {prompt[:50]}...)")
        async with self._request_semaphore:
            logger.debug(f"🎨 Runware: Acquired semaphore, starting generation")
            return await self._generate_image_impl(
                prompt=prompt,
                width=width,
                height=height,
                n=n,
                response_format=response_format,
                negative_prompt=negative_prompt,
                seed=seed,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                model=model,
                scheduler=scheduler,
                clip_skip=clip_skip,
                output_quality=output_quality,
                **kwargs
            )

    async def _generate_image_impl(
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
        scheduler: Optional[str] = None,
        clip_skip: Optional[int] = None,
        output_quality: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Internal implementation of generate_image, called within semaphore."""
        # Resolve model_key to model_id if needed
        #  If model is None, use provider's default
        if model is None:
            model_key = self.provider_info.default_model
            model_config = self.models[model_key]
            model_id = model_config.model_id
            logger.debug(f"No model specified, using default: {model_key} → {model_id}")
        elif model in self.models:
            # Model is a model_key, resolve to model_id
            model_key = model
            model_config = self.models[model_key]
            model_id = model_config.model_id
            logger.debug(f"Resolved model_key to model_id: {model_key} → {model_id}")
        else:
            # Assume it's already a model_id (e.g., "runware:97@3")
            model_key = model  # Use as-is for logging
            model_id = model
            model_config = None  # No config available for direct model IDs
            logger.debug(f"Using model_id directly: {model_id}")
        
        # Resolve scheduler: parameter > model config > None
        # If scheduler parameter is provided, use it
        # Otherwise, use model config's scheduler if available
        resolved_scheduler = scheduler
        if resolved_scheduler is None and model_config is not None:
            resolved_scheduler = model_config.scheduler
        
        if resolved_scheduler:
            logger.debug(f"Using scheduler: {resolved_scheduler}")
        
        # Resolve negative prompt: parameter > model config > None
        # If negative_prompt parameter is provided (even if empty string), use it
        # Otherwise, use model config's negative_prompt if available
        resolved_negative_prompt = negative_prompt
        if resolved_negative_prompt is None and model_config is not None:
            resolved_negative_prompt = model_config.negative_prompt
        
        if resolved_negative_prompt:
            logger.debug(f"Using negative prompt: {resolved_negative_prompt[:50]}...")
        
        # Resolve clip_skip: parameter > model config > None
        resolved_clip_skip = clip_skip
        if resolved_clip_skip is None and model_config is not None:
            resolved_clip_skip = model_config.clip_skip
        
        if resolved_clip_skip:
            logger.debug(f"Using clip_skip: {resolved_clip_skip}")
        
        # Resolve output_quality: parameter > model config > None
        resolved_output_quality = output_quality
        if resolved_output_quality is None and model_config is not None:
            resolved_output_quality = model_config.output_quality
        
        if resolved_output_quality:
            logger.debug(f"Using output_quality: {resolved_output_quality}")

        # Retry loop for handling transient errors
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Connect to Runware (ensures authenticated connection)
                await self.connect()

                logger.debug(f"Generating image with Runware model: {model_id} (attempt {attempt + 1}/{self.max_retries})")
                logger.debug(f"Prompt: {prompt[:100]}...")
                logger.debug(f"Size: {width}x{height}, Count: {n}")

                # Prepare request with only non-None parameters
                request_params = {
                    "positivePrompt": prompt,
                    "model": model_id,
                    "width": width,
                    "height": height,
                    "numberResults": n
                }

                # Set output type based on response format
                if response_format == "b64_json":
                    request_params["outputType"] = "base64Data"
                else:
                    request_params["outputType"] = "URL"

                # Only add optional parameters if they're provided
                if resolved_negative_prompt is not None and resolved_negative_prompt != "":
                    request_params["negativePrompt"] = resolved_negative_prompt
                if seed is not None:
                    request_params["seed"] = seed
                if guidance_scale is not None:
                    request_params["CFGScale"] = guidance_scale
                if num_inference_steps is not None:
                    request_params["steps"] = num_inference_steps
                if resolved_scheduler is not None:
                    request_params["scheduler"] = resolved_scheduler
                if resolved_clip_skip is not None:
                    request_params["clipSkip"] = resolved_clip_skip
                if resolved_output_quality is not None:
                    request_params["outputQuality"] = resolved_output_quality

                logger.info(f"Request params: {request_params}")
                request = IImageInference(**request_params)

                # Generate images
                start_time = time.time()
                logger.debug("Sending image inference request to Runware...")
                images = await self.client.imageInference(requestImage=request)
                generation_time = time.time() - start_time
                logger.debug(f"Received {len(images)} images from Runware")
                
                # Resolve output directory (global images path unless explicitly overridden)
                output_dir = kwargs.get('output_dir') or os.path.expanduser(os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images'))

                # Process results
                processed_images = []
                for i, image in enumerate(images[:n]):
                    if response_format == "b64_json":
                        # Get base64 data directly from response
                        b64_data = image.imageBase64Data
                        if not b64_data:
                            # Fallback to URL if base64 not available
                            logger.warning("No base64Data in response, falling back to URL")
                            b64_data = await self._url_to_base64(image.imageURL)
                        processed_images.append({
                            "b64_json": b64_data,
                            "seed": image.seed if hasattr(image, 'seed') else seed,
                            "generation_time": generation_time / len(images)
                        })
                    else:
                        # Use URL directly or save from base64
                        if image.imageURL:
                            filepath = await self._save_image_from_url(image.imageURL, output_dir=output_dir)
                        else:
                            # If we got base64 instead, convert it
                            filepath = await self.save_image_from_base64(image.imageBase64Data, output_dir=output_dir)
                        processed_images.append({
                            "url": f"file://{filepath}",
                            "path": filepath,
                            "seed": image.seed if hasattr(image, 'seed') else seed,
                            "generation_time": generation_time / len(images)
                        })
                
                logger.debug(f"✅ Generated {len(processed_images)} images in {generation_time:.2f}s")

                # Success! Return the result
                return {
                    "success": True,
                    "images": processed_images,
                    "model": model_id,
                    "prompt": prompt,
                    "provider": "runware"
                }

            except Exception as e:
                last_error = e
                error_str = str(e)
                logger.error(f"Error in Runware image generation (attempt {attempt + 1}/{self.max_retries}): {e}")

                # Check if this is an authentication error that we should retry
                is_auth_error = (
                    "missingApiKey" in error_str or
                    "Missing API Key" in error_str or
                    "authentication failed" in error_str.lower() or
                    "not authenticated" in error_str.lower()
                )

                if is_auth_error:
                    logger.warning(f"⚠️ Authentication error detected, forcing reconnection...")
                    # Force reconnection for authentication errors
                    await self._force_reconnect()

                    # If this is not the last attempt, wait and retry
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (attempt + 1)  # Exponential backoff
                        logger.info(f"Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                else:
                    # For non-auth errors, check if it's retryable
                    is_retryable_error = (
                        "timeout" in error_str.lower() or
                        "connection" in error_str.lower() or
                        "network" in error_str.lower() or
                        "503" in error_str or
                        "502" in error_str or
                        "504" in error_str
                    )

                    if is_retryable_error and attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (attempt + 1)
                        logger.warning(f"⚠️ Transient error detected, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Non-retryable error, break out of retry loop
                        logger.error(f"Non-retryable error or max retries reached")
                        break

        # All retries exhausted
        import traceback
        logger.error(f"❌ Failed after {self.max_retries} attempts")
        logger.error(f"Last error: {last_error}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        return {
            "success": False,
            "error": f"Failed after {self.max_retries} attempts: {str(last_error)}",
            "images": [],
            "provider": "runware"
        }
    
    async def upscale_image(
        self,
        image_url: str,
        upscale_factor: int = 4,
        response_format: str = "b64_json"
    ) -> Dict[str, Any]:
        """Upscale an image using Runware's upscaling models"""
        if not self.is_available():
            return {"error": "Runware not available"}
        
        try:
            await self.connect()
            
            request = IImageUpscale(
                inputImage=image_url,
                upscaleFactor=upscale_factor
            )
            
            result = await self.client.imageUpscale(upscaleGanPayload=request)
            
            if response_format == "b64_json":
                b64_data = await self._url_to_base64(result[0].imageURL)
                return {
                    "success": True,
                    "image": {"b64_json": b64_data},
                    "upscale_factor": upscale_factor
                }
            else:
                filepath = await self._save_image_from_url(result[0].imageURL)
                return {
                    "success": True,
                    "image": {
                        "url": f"file://{filepath}",
                        "path": filepath
                    },
                    "upscale_factor": upscale_factor
                }
                
        except Exception as e:
            logger.error(f"Error upscaling image: {e}")
            return {"error": str(e)}
    
    async def remove_background(
        self,
        image_path: str,
        response_format: str = "b64_json"
    ) -> Dict[str, Any]:
        """Remove background from an image"""
        if not self.is_available():
            return {"error": "Runware not available"}
        
        try:
            await self.connect()
            
            request = IImageBackgroundRemoval(
                image_initiator=image_path
            )
            
            result = await self.client.imageBackgroundRemoval(removeImageBackgroundPayload=request)
            
            if response_format == "b64_json":
                b64_data = await self._url_to_base64(result[0].imageURL)
                return {
                    "success": True,
                    "image": {"b64_json": b64_data}
                }
            else:
                filepath = await self._save_image_from_url(result[0].imageURL)
                return {
                    "success": True,
                    "image": {
                        "url": f"file://{filepath}",
                        "path": filepath
                    }
                }
                
        except Exception as e:
            logger.error(f"Error removing background: {e}")
            return {"error": str(e)}
    
    async def _url_to_base64(self, url: str) -> str:
        """Convert image URL to base64"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                image_data = await response.read()
                return base64.b64encode(image_data).decode('utf-8')
    
    async def _save_image_from_url(self, url: str, output_dir: Optional[str] = None) -> str:
        """Save image from URL to local storage"""
        if not output_dir:
            output_dir = os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images')
        output_dir = os.path.expanduser(output_dir)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        filename = f"runware_image_{int(time.time() * 1000)}.png"
        filepath = Path(output_dir) / filename
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                image_data = await response.read()
                with open(filepath, 'wb') as f:
                    f.write(image_data)
        
        logger.debug(f"Saved Runware image to: {filepath}")
        return str(filepath)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Runware models"""
        return [
            {
                "id": "rundiffusion:130@100",
                "name": "Juggernaut Pro",
                "provider": "rundiffusion",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True,
                "quality": "very_high",
                "speed": "medium"
            },
            {
                "id": "runware:100@1",
                "name": "Flux Schnell",
                "provider": "runware",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True,
                "quality": "high",
                "speed": "fast"
            },
            {
                "id": "bfl:2@2",
                "name": "Flux Pro Ultra",
                "provider": "bfl",
                "type": "text-to-image",
                "max_resolution": "2048x2048",
                "supports_negative_prompt": False,
                "quality": "ultra_high",
                "speed": "medium"
            },
            {
                "id": "rundiffusion:110@101",
                "name": "Juggernaut Lightning",
                "provider": "rundiffusion",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True,
                "quality": "high",
                "speed": "very_fast"
            },
            {
                "id": "runware:97@3",
                "name": "Hidream Fast",
                "provider": "runware",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True,
                "quality": "medium",
                "speed": "very_fast"
            }
        ]

    def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this Runware provider."""
        return ProviderCapabilities(
            supports_negative_prompt=True,
            supports_seed=True,
            supports_guidance_scale=True,
            supports_inference_steps=True,
            supports_variable_size=True,
            max_width=2048,
            max_height=2048,
            supported_formats=["url", "b64_json"]
        )

    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the given model.

        Supports Runware cloud models (runware pipeline_type or runware:* model IDs).

        Args:
            model: Model identifier (pipeline_type, model ID, etc.)

        Returns:
            True if this is a Runware model
        """
        model_lower = model.lower()
        # Check if it's the runware pipeline type
        if model_lower == "runware":
            return True
        # Check if it's a Runware model ID (starts with runware:, rundiffusion:, or bfl:)
        if model_lower.startswith(("runware:", "rundiffusion:", "bfl:")):
            return True
        # Check if it matches any of our known models
        available_models = self.get_available_models()
        for available_model in available_models:
            if model_lower == available_model["id"].lower():
                return True
            if model_lower in available_model["name"].lower():
                return True
        return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the service"""
        return {
            "provider": "runware",
            "model": self.provider_info.default_model,
            "model_key": "runware",
            "available": self.is_available(),
            "available_models": len(self.get_available_models()),
            "features": [
                "text-to-image",
                "image-upscaling",
                "background-removal",
                "concurrent-generation",
                "batch-processing"
            ],
            "sdk_available": RUNWARE_AVAILABLE,
            "api_key_configured": bool(self.api_key)
        }
    
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
            
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Decode base64 to image
            image_bytes = base64.b64decode(b64_data)
            image = Image.open(BytesIO(image_bytes))
            
            # Generate filename
            filename = f"runware_image_{int(time.time() * 1000)}.png"
            filepath = Path(output_dir) / filename
            
            # Save image
            image.save(filepath, format='PNG')
            
            logger.info(f"Saved image to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving base64 image: {e}")
            return None


# Singleton instance
_runware_service = None

def get_runware_image_service() -> Optional[RunwareImageService]:
    """Get the singleton Runware image service instance."""
    global _runware_service

    if _runware_service is None:
        _runware_service = RunwareImageService()

    return _runware_service if _runware_service.is_available() else None
