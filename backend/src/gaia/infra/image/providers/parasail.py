"""
Parasail Image Generation Service
Handles image generation using Parasail API via OpenAI Batch
"""

import os
import logging
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
import time
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ParasailImageService:
    """Service for handling image generation using Parasail API"""
    
    def __init__(self):
        self.api_key = os.environ.get('PARASAIL_API_KEY')
        if not self.api_key:
            logger.warning("PARASAIL_API_KEY not found in environment variables")
            self.client = None
        else:
            # Initialize OpenAI client pointing to Parasail
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.parasail.io/v1"
            )
    
    async def generate_image(
        self, 
        prompt: str, 
        model: str = "Shitao/OmniGen-v1",
        size: str = "1024x1024",
        n: int = 1,
        response_format: str = "b64_json"
    ) -> Dict[str, Any]:
        """
        Generate an image using Parasail API via Batch processing
        
        Args:
            prompt: Text description of the image
            model: Model to use (default: Shitao/OmniGen-v1)
            size: Size of the image (default: 1024x1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            
        Returns:
            Dict containing image generation results
        """
        if not self.client:
            return {
                "error": "Parasail API key not configured",
                "images": []
            }
        
        # Use the batch image service for actual generation
        from gaia.infra.image.providers.parasail_batch import get_parasail_batch_image_service
        
        batch_service = get_parasail_batch_image_service()
        if not batch_service:
            return {
                "error": "Parasail batch service not available",
                "images": []
            }
        
        # Delegate to batch service
        logger.info(f"Delegating image generation to batch service")
        return await batch_service.generate_image(
            prompt=prompt,
            model=model,
            size=size,
            n=n,
            response_format=response_format
        )
    
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
            
            # Generate filename
            filename = f"parasail_image_{int(time.time() * 1000)}.png"
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
    
    async def save_image_from_url(self, image_url: str, output_dir: str = None) -> Optional[str]:
        """
        Download and save an image from URL
        
        Args:
            image_url: URL of the image
            output_dir: Directory to save the image
            
        Returns:
            Path to saved image or None if failed
        """
        try:
            import aiohttp
            
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Generate filename from URL
            filename = f"parasail_image_{hash(image_url)}.png"
            filepath = Path(output_dir) / filename
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        
                        logger.info(f"Saved image to: {filepath}")
                        return str(filepath)
                    else:
                        logger.error(f"Failed to download image: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    def get_available_models(self) -> List[Dict[str, str]]:
        """Get list of available image generation models"""
        return [
            {
                "id": "Shitao/OmniGen-v1",
                "name": "OmniGen v1",
                "description": "Advanced image generation model with style transfer capabilities"
            }
        ]
    
    def get_supported_sizes(self, model: str) -> List[str]:
        """Get supported image sizes for a model"""
        # OmniGen supports various sizes
        return [
            "512x512",
            "768x768",
            "1024x1024",
            "1024x768",
            "768x1024"
        ]


# Singleton instance
_parasail_service = None

def get_parasail_image_service() -> Optional[ParasailImageService]:
    """Get the singleton Parasail image service instance."""
    global _parasail_service
    
    if _parasail_service is None:
        _parasail_service = ParasailImageService()
        
    return _parasail_service if _parasail_service.api_key else None