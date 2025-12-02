"""
Parasail Batch Image Generation Service
Handles image generation using Parasail Batch API with OmniGen model
"""

import os
import logging
import base64
import json
import time
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
from openai import AsyncOpenAI
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ParasailBatchImageService:
    """Service for handling batch image generation using Parasail API"""
    
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
            logger.info("Parasail batch image service initialized")
    
    async def generate_image(
        self, 
        prompt: str, 
        model: str = "Shitao/OmniGen-v1",
        size: str = "1024x1024",
        n: int = 1,
        response_format: str = "b64_json",
        input_images: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate an image using Parasail Batch API with OmniGen model
        
        Args:
            prompt: Text description of the image
            model: Model to use (default: Shitao/OmniGen-v1)
            size: Size of the image (default: 1024x1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            input_images: Optional list of base64-encoded input images for style transfer
            
        Returns:
            Dict containing image generation results
        """
        if not self.client:
            return {
                "error": "Parasail API key not configured",
                "images": []
            }
        
        try:
            logger.info(f"Starting batch image generation with model: {model}")
            logger.info(f"Prompt: {prompt[:100]}...")
            
            # Create temporary batch input file
            batch_input_path = f"/tmp/parasail_batch_input_{int(time.time() * 1000)}.jsonl"
            
            # Prepare batch requests
            batch_requests = []
            for i in range(n):
                # For OmniGen, we need to use chat completions endpoint with special formatting
                messages = [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
                
                request_body = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1,  # Minimal tokens since we're generating images
                    "temperature": 0.7,
                    "response_format": {
                        "type": "image",
                        "size": size,
                        "format": "b64_json"
                    }
                }
                
                # Add input images if provided
                if input_images and i < len(input_images):
                    # For OmniGen style transfer, include image in the message
                    messages[0]["content"] = f"{prompt}\n<img><|image_1|></img>"
                    request_body["images"] = input_images[:1]  # Only use first image
                
                batch_request = {
                    "custom_id": f"image-{i+1}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": request_body
                }
                batch_requests.append(batch_request)
            
            # Write batch input file
            with open(batch_input_path, "w") as f:
                for request in batch_requests:
                    f.write(json.dumps(request) + "\n")
            
            logger.info(f"Created batch input file with {n} requests")
            
            # Upload input file
            with open(batch_input_path, "rb") as f:
                input_file = await self.client.files.create(
                    file=f,
                    purpose="batch"
                )
            
            logger.info(f"Uploaded batch input file: {input_file.id}")
            
            # Create batch
            batch = await self.client.batches.create(
                input_file_id=input_file.id,
                completion_window="24h",
                endpoint="/v1/chat/completions"
            )
            
            logger.info(f"Created batch: {batch.id}")
            
            # Poll for completion (with timeout)
            max_wait_time = 7200  # 2 hours max wait
            poll_interval = 30    # Check every 30 seconds
            start_time = time.time()
            
            logger.info(f"Batch submitted. This may take several minutes to hours to complete...")
            
            while batch.status not in ["completed", "failed", "expired", "cancelled"]:
                if time.time() - start_time > max_wait_time:
                    logger.error(f"Batch timed out after {max_wait_time} seconds")
                    return {
                        "error": f"Batch generation timed out after {max_wait_time} seconds",
                        "images": [],
                        "batch_id": batch.id
                    }
                
                await asyncio.sleep(poll_interval)
                batch = await self.client.batches.retrieve(batch.id)
                logger.info(f"Batch status: {batch.status}")
            
            # Check final status
            if batch.status != "completed":
                logger.error(f"Batch failed with status: {batch.status}")
                
                # Try to get error details
                try:
                    if hasattr(batch, 'errors') and batch.errors:
                        logger.error(f"Batch errors: {batch.errors}")
                    
                    # Check if there's an error file
                    if hasattr(batch, 'error_file_id') and batch.error_file_id:
                        error_content = await self.client.files.content(batch.error_file_id)
                        error_path = f"/tmp/parasail_batch_errors_{batch.id}.jsonl"
                        with open(error_path, "wb") as f:
                            f.write(error_content.content)
                        logger.error(f"Error details saved to: {error_path}")
                        
                        # Read and log first few error lines
                        with open(error_path, "r") as f:
                            for i, line in enumerate(f):
                                if i < 5:  # Show first 5 errors
                                    logger.error(f"Error {i+1}: {line.strip()}")
                except Exception as e:
                    logger.error(f"Could not retrieve error details: {e}")
                
                return {
                    "error": f"Batch failed with status: {batch.status}",
                    "images": [],
                    "batch_id": batch.id
                }
            
            # Download output file
            output_content = await self.client.files.content(batch.output_file_id)
            
            # Save output temporarily
            output_path = f"/tmp/parasail_batch_output_{int(time.time() * 1000)}.jsonl"
            with open(output_path, "wb") as f:
                f.write(output_content.content)
            
            logger.info(f"Downloaded batch output to: {output_path}")
            
            # Determine output directory if explicitly provided
            output_dir = kwargs.get('output_dir')

            # Parse results and extract images
            images = []
            with open(output_path, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("response", {}).get("status") == 200:
                            # Extract base64 image data
                            b64_data = data["response"]["body"]["data"][0]["b64_json"]
                            
                            if response_format == "b64_json":
                                images.append({
                                    "b64_json": b64_data,
                                    "custom_id": data.get("custom_id")
                                })
                            else:
                                # Save and return URL
                                path = await self.save_image_from_base64(b64_data, output_dir=output_dir)
                                if path:
                                    images.append({
                                        "url": f"file://{path}",
                                        "path": path,
                                        "custom_id": data.get("custom_id")
                                    })
                        else:
                            logger.error(f"Request {data.get('custom_id')} failed: {data.get('response')}")
                    except Exception as e:
                        logger.error(f"Error parsing batch output line: {e}")
            
            # Clean up temporary files
            for path in [batch_input_path, output_path]:
                try:
                    os.remove(path)
                except:
                    pass
            
            if images:
                logger.info(f"✅ Successfully generated {len(images)} images")
                return {
                    "success": True,
                    "images": images,
                    "batch_id": batch.id,
                    "prompt": prompt,
                    "model": model
                }
            else:
                return {
                    "error": "No images were successfully generated",
                    "images": [],
                    "batch_id": batch.id
                }
            
        except Exception as e:
            logger.error(f"Error in Parasail batch image generation: {e}")
            return {
                "error": str(e),
                "images": []
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
            image = Image.open(io.BytesIO(image_bytes))
            
            # Generate filename
            filename = f"parasail_batch_image_{int(time.time() * 1000)}.jpg"
            filepath = Path(output_dir) / filename
            
            # Convert to RGB if necessary and save as JPEG
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(filepath, format='JPEG', quality=95)
            
            logger.info(f"Saved image to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving base64 image: {e}")
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
_parasail_batch_service = None

def get_parasail_batch_image_service() -> Optional[ParasailBatchImageService]:
    """Get the singleton Parasail batch image service instance."""
    global _parasail_batch_service
    
    if _parasail_batch_service is None:
        _parasail_batch_service = ParasailBatchImageService()
        
    return _parasail_batch_service if _parasail_batch_service.api_key else None
