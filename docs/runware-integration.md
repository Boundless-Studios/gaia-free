# Runware AI Image Generation Integration

## Overview

This document outlines the integration of [Runware's Python SDK](https://runware.ai/docs/en/libraries/python) into the Gaia D&D Campaign Manager for AI-powered image generation. Runware provides a WebSocket-based API with access to multiple AI models for text-to-image, image-to-image, inpainting, and other image processing tasks.

## Table of Contents

1. [Integration Goals](#integration-goals)
2. [Runware API Analysis](#runware-api-analysis)
3. [Current System Architecture](#current-system-architecture)
4. [Integration Plan](#integration-plan)
5. [Implementation Details](#implementation-details)
6. [Configuration](#configuration)
7. [API Endpoints](#api-endpoints)
8. [Error Handling](#error-handling)
9. [Testing Strategy](#testing-strategy)
10. [Deployment Considerations](#deployment-considerations)

## Integration Goals

### Primary Objectives
- **Seamless Integration**: Add Runware as a new image generation provider alongside existing Flux and Gemini services
- **Model Diversity**: Access to multiple AI models through Runware's unified API
- **Performance**: Leverage WebSocket connections for better performance and concurrent operations
- **Reliability**: Robust error handling and automatic retry mechanisms
- **Scalability**: Support for batch processing and concurrent image generation

### Secondary Objectives
- **Cost Optimization**: Intelligent model selection based on requirements
- **Quality Enhancement**: Access to specialized models for different use cases
- **Fallback Support**: Graceful degradation when Runware is unavailable
- **Monitoring**: Comprehensive logging and metrics for usage tracking

## Runware API Analysis

### Key Features
Based on the [Runware Python SDK documentation](https://runware.ai/docs/en/libraries/python):

#### 1. **WebSocket-Based Architecture**
- Persistent connections for better performance
- Automatic connection management and reconnection
- Built-in retry logic and error recovery

#### 2. **Comprehensive Model Support**
- **Text-to-Image**: Multiple models including Runware's own models
- **Image-to-Image**: Style transfer and image modification
- **Inpainting**: Object removal and background editing
- **Outpainting**: Image extension and expansion
- **Upscaling**: Image resolution enhancement
- **Background Removal**: Automatic background isolation

#### 3. **Advanced Features**
- **Concurrent Operations**: Multiple simultaneous requests
- **Batch Processing**: Efficient handling of multiple images
- **Async/Await Support**: Native Python async patterns
- **Type Safety**: Comprehensive type hints for better IDE support

#### 4. **Model Providers**
- **Runware**: Native models (runware:101@1, etc.)
- **Black Forest Labs**: FLUX models
- **OpenAI**: DALL-E models
- **ByteDance**: CapCut models
- **Google**: Imagen models
- **Ideogram**: Specialized text-in-image models
- **KlingAI**: Video generation models
- **MiniMax**: Chinese AI models
- **PixVerse**: Video generation
- **Vidu**: Video generation

### SDK Capabilities
```python
# Basic usage pattern
from runware import Runware, IImageInference

async def generate_image():
    runware = Runware()
    await runware.connect()
    
    request = IImageInference(
        positivePrompt="A serene mountain landscape at sunset",
        model="runware:101@1",
        width=1024,
        height=1024
    )
    
    images = await runware.imageInference(requestImage=request)
    return images[0].imageURL
```

## Current System Architecture

### Existing Image Services
The Gaia system currently supports three image generation providers:

1. **FluxLocalImageService** (`backend/src/core/image/flux_local_image_service.py`)
   - Local Stable Diffusion models
   - GPU-accelerated generation
   - Configurable model switching
   - Memory optimization features

2. **GeminiImageService** (`backend/src/core/image/gemini_image_service.py`)
   - Google's Gemini 2.0 Flash API
   - Cloud-based generation
   - Prompt enhancement capabilities
   - Image analysis features

3. **ParasailImageService** (`backend/src/core/image/parasail_image_service.py`)
   - Parasail API integration
   - Batch processing support
   - Multiple model options

### Current API Structure
```python
# Main image generation endpoint
@app.post("/api/images/generate")
async def generate_image(request: ImageGenerationRequest):
    # Try Flux first, then Gemini
    image_service = get_flux_local_image_service()
    if not image_service:
        image_service = get_gemini_image_service()
    
    result = await image_service.generate_image(
        prompt=enhanced_prompt,
        width=width,
        height=height,
        response_format="url"
    )
```

### Service Interface Pattern
All image services follow a consistent interface:
```python
async def generate_image(
    self,
    prompt: str,
    model: str = "default",
    width: Optional[int] = None,
    height: Optional[int] = None,
    n: int = 1,
    response_format: str = "b64_json",
    **kwargs
) -> Dict[str, Any]:
    """Generate images with consistent return format"""
```

## Integration Plan

### Phase 1: Core Service Implementation
1. **Install Runware SDK**
   ```bash
   pip install runware
   ```

2. **Create RunwareImageService**
   - Implement the standard image service interface
   - Handle WebSocket connection management
   - Support multiple model types and providers
   - Implement error handling and retry logic

3. **Configuration Management**
   - Environment variable setup
   - Model selection configuration
   - Connection timeout and retry settings

### Phase 2: API Integration
1. **Update Main Endpoint**
   - Add Runware as a priority option
   - Implement intelligent service selection
   - Maintain backward compatibility

2. **New Specialized Endpoints**
   - Inpainting endpoint
   - Image upscaling endpoint
   - Background removal endpoint
   - Batch processing endpoint

### Phase 3: Advanced Features
1. **Model Management**
   - Dynamic model selection based on requirements
   - Cost optimization algorithms
   - Quality vs. speed trade-offs

2. **Batch Processing**
   - Concurrent image generation
   - Progress tracking
   - Error handling for partial failures

3. **Caching and Optimization**
   - Result caching for repeated requests
   - Connection pooling
   - Request deduplication

## Implementation Details

### 1. RunwareImageService Class

```python
"""
Runware Image Generation Service
Handles image generation using Runware's WebSocket API
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

from runware import Runware, IImageInference, IImageUpscale, IImageBackgroundRemoval

logger = logging.getLogger(__name__)

class RunwareImageService:
    """Service for handling image generation using Runware API"""
    
    def __init__(self):
        self.api_key = os.environ.get('RUNWARE_API_KEY')
        self.client = None
        self.configured = bool(self.api_key)
        
        if not self.configured:
            logger.warning("RUNWARE_API_KEY not found in environment variables")
        else:
            logger.info("Runware image service initialized")
    
    async def connect(self):
        """Establish WebSocket connection to Runware"""
        if not self.configured:
            raise RuntimeError("Runware API key not configured")
        
        if self.client is None:
            self.client = Runware(
                api_key=self.api_key,
                timeout=120,  # 2 minutes timeout
                max_retries=3,
                retry_delay=2.0
            )
        
        if not hasattr(self.client, '_connected') or not self.client._connected:
            await self.client.connect()
            logger.info("Connected to Runware WebSocket API")
    
    async def disconnect(self):
        """Close WebSocket connection"""
        if self.client and hasattr(self.client, '_connected') and self.client._connected:
            await self.client.disconnect()
            logger.info("Disconnected from Runware API")
    
    async def generate_image(
        self,
        prompt: str,
        model: str = "runware:101@1",
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
        Generate images using Runware API
        
        Args:
            prompt: Text description of the image
            model: Model to use (default: runware:101@1)
            width: Image width (default: 1024)
            height: Image height (default: 1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            negative_prompt: What to avoid in the image
            seed: Random seed for reproducibility
            guidance_scale: How closely to follow the prompt
            num_inference_steps: Number of denoising steps
            
        Returns:
            Dict containing image generation results
        """
        if not self.configured:
            return {
                "error": "Runware API key not configured",
                "images": []
            }
        
        try:
            await self.connect()
            
            logger.info(f"Generating image with Runware model: {model}")
            logger.info(f"Prompt: {prompt[:100]}...")
            logger.info(f"Size: {width}x{height}, Count: {n}")
            
            # Prepare request
            request = IImageInference(
                positivePrompt=prompt,
                model=model,
                width=width,
                height=height,
                negativePrompt=negative_prompt,
                seed=seed,
                guidanceScale=guidance_scale,
                numInferenceSteps=num_inference_steps
            )
            
            # Generate images
            start_time = time.time()
            images = await self.client.imageInference(requestImage=request)
            generation_time = time.time() - start_time
            
            # Process results
            processed_images = []
            for i, image in enumerate(images[:n]):
                if response_format == "b64_json":
                    # Convert URL to base64
                    b64_data = await self._url_to_base64(image.imageURL)
                    processed_images.append({
                        "b64_json": b64_data,
                        "seed": seed,
                        "generation_time": generation_time / len(images)
                    })
                else:
                    # Save to file and return path
                    filepath = await self._save_image_from_url(image.imageURL)
                    processed_images.append({
                        "url": f"file://{filepath}",
                        "path": filepath,
                        "seed": seed,
                        "generation_time": generation_time / len(images)
                    })
            
            logger.info(f"✅ Generated {len(processed_images)} images in {generation_time:.2f}s")
            
            return {
                "success": True,
                "images": processed_images,
                "model": model,
                "prompt": prompt,
                "provider": "runware"
            }
            
        except Exception as e:
            logger.error(f"Error in Runware image generation: {e}")
            return {
                "error": str(e),
                "images": []
            }
    
    async def upscale_image(
        self,
        image_url: str,
        upscale_factor: int = 4,
        response_format: str = "b64_json"
    ) -> Dict[str, Any]:
        """Upscale an image using Runware's upscaling models"""
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
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                image_data = await response.read()
                return base64.b64encode(image_data).decode('utf-8')
    
    async def _save_image_from_url(self, url: str) -> str:
        """Save image from URL to local storage"""
        import aiohttp
        
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
        
        logger.info(f"Saved Runware image to: {filepath}")
        return str(filepath)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models"""
        return [
            {
                "id": "runware:101@1",
                "name": "Runware 101",
                "provider": "runware",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True
            },
            {
                "id": "blackforestlabs:flux-dev@1",
                "name": "FLUX Dev",
                "provider": "blackforestlabs",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True
            },
            {
                "id": "openai:dall-e-3@1",
                "name": "DALL-E 3",
                "provider": "openai",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": False
            },
            {
                "id": "ideogram:ideogram-v1@1",
                "name": "Ideogram V1",
                "provider": "ideogram",
                "type": "text-to-image",
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True
            }
        ]
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the service"""
        return {
            "provider": "runware",
            "configured": self.configured,
            "connected": self.client is not None and hasattr(self.client, '_connected') and self.client._connected,
            "available_models": len(self.get_available_models()),
            "features": [
                "text-to-image",
                "image-upscaling",
                "background-removal",
                "concurrent-generation",
                "batch-processing"
            ]
        }

# Singleton instance
_runware_service = None

def get_runware_image_service() -> Optional[RunwareImageService]:
    """Get the singleton Runware image service instance."""
    global _runware_service
    
    if _runware_service is None:
        _runware_service = RunwareImageService()
        
    return _runware_service if _runware_service.configured else None
```

### 2. Updated Main API Endpoint

```python
@app.post("/api/images/generate")
async def generate_image(
    request: ImageGenerationRequest,
    current_user = require_auth_if_available()
):
    """Generate an image using selected generation method - requires authentication if available."""
    logger.info(f"Received image generation request: model={request.model}, type={request.image_type}")
    
    try:
        # Service priority: Runware -> Flux -> Gemini
        image_service = None
        service_name = None
        
        # Try Runware first (new priority)
        runware_service = get_runware_image_service()
        if runware_service:
            image_service = runware_service
            service_name = "Runware"
            logger.info("Using Runware service for image generation")
        
        # Fallback to Flux
        if not image_service:
            image_service = get_flux_local_image_service()
            service_name = "Flux"
            logger.info("Using Flux service for image generation")
        
        # Fallback to Gemini
        if not image_service:
            image_service = get_gemini_image_service()
            service_name = "Gemini"
            logger.info("Using Gemini service for image generation")
        
        if not image_service:
            raise HTTPException(status_code=503, detail="No image service configured")
        
        # Enhance prompt with style
        enhanced_prompt = f"{request.prompt}, {request.style} style"
        
        # Generate image with service-specific parameters
        if service_name == "Runware":
            result = await image_service.generate_image(
                prompt=enhanced_prompt,
                model=request.model or "runware:101@1",
                width=int(request.size.split('x')[0]),
                height=int(request.size.split('x')[1]),
                response_format="url"
            )
        elif service_name == "Flux":
            result = await image_service.generate_image(
                prompt=enhanced_prompt,
                width=int(request.size.split('x')[0]),
                height=int(request.size.split('x')[1]),
                response_format="url"
            )
        elif service_name == "Gemini":
            result = await image_service.generate_image(
                prompt=enhanced_prompt,
                model="gemini-2.0-flash-preview-image-generation",
                size=request.size,
                n=1,
                response_format="url"
            )
        
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        
        images = result.get("images", [])
        if images:
            image_data = images[0]
            return {
                "success": True,
                "image_url": image_data.get("url", ""),
                "image_path": image_data.get("path", ""),
                "service": service_name,
                "model": result.get("model", ""),
                "generation_time": image_data.get("generation_time", 0)
            }
        else:
            raise HTTPException(status_code=500, detail="No images generated")
            
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. New Specialized Endpoints

```python
@app.post("/api/images/upscale")
async def upscale_image(
    request: ImageUpscaleRequest,
    current_user = require_auth_if_available()
):
    """Upscale an image using Runware's upscaling models"""
    runware_service = get_runware_image_service()
    if not runware_service:
        raise HTTPException(status_code=503, detail="Runware service not available")
    
    result = await runware_service.upscale_image(
        image_url=request.image_url,
        upscale_factor=request.upscale_factor,
        response_format=request.response_format
    )
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@app.post("/api/images/remove-background")
async def remove_background(
    request: BackgroundRemovalRequest,
    current_user = require_auth_if_available()
):
    """Remove background from an image using Runware"""
    runware_service = get_runware_image_service()
    if not runware_service:
        raise HTTPException(status_code=503, detail="Runware service not available")
    
    result = await runware_service.remove_background(
        image_path=request.image_path,
        response_format=request.response_format
    )
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@app.get("/api/images/models")
async def get_available_models():
    """Get list of available image generation models"""
    models = []
    
    # Get Runware models
    runware_service = get_runware_image_service()
    if runware_service:
        models.extend(runware_service.get_available_models())
    
    # Get Flux models
    flux_service = get_flux_local_image_service()
    if flux_service:
        flux_info = flux_service.get_model_info()
        models.append({
            "id": flux_info["model_key"],
            "name": flux_info["model"],
            "provider": "flux",
            "type": "text-to-image",
            "max_resolution": "1024x1024",
            "supports_negative_prompt": flux_info["supports_negative_prompt"]
        })
    
    # Get Gemini models
    gemini_service = get_gemini_image_service()
    if gemini_service:
        models.append({
            "id": "gemini-2.0-flash-preview-image-generation",
            "name": "Gemini 2.0 Flash",
            "provider": "gemini",
            "type": "text-to-image",
            "max_resolution": "1024x1024",
            "supports_negative_prompt": False
        })
    
    return {"models": models}
```

## Configuration

### Environment Variables

```bash
# Required
RUNWARE_API_KEY="your-runware-api-key-here"

# Optional
RUNWARE_TIMEOUT=120
RUNWARE_MAX_RETRIES=3
RUNWARE_RETRY_DELAY=2.0
RUNWARE_BASE_URL="wss://api.runware.ai/v1"  # Default endpoint
```

### Docker Configuration

Update `backend/requirements.txt`:
```txt
# Add Runware SDK
runware>=1.0.0
```

Update `backend/Dockerfile`:
```dockerfile
# Install Runware SDK
RUN pip install runware
```

### Configuration File

Create `backend/src/core/image/runware_config.py`:
```python
"""
Runware Configuration
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class RunwareConfig:
    """Configuration for Runware service"""
    
    api_key: Optional[str] = None
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0
    base_url: str = "wss://api.runware.ai/v1"
    
    # Model preferences
    default_model: str = "runware:101@1"
    fallback_models: list = None
    
    # Performance settings
    max_concurrent_requests: int = 5
    connection_pool_size: int = 3
    
    def __post_init__(self):
        if self.fallback_models is None:
            self.fallback_models = [
                "blackforestlabs:flux-dev@1",
                "openai:dall-e-3@1",
                "ideogram:ideogram-v1@1"
            ]
    
    @classmethod
    def from_env(cls) -> 'RunwareConfig':
        """Load configuration from environment variables"""
        return cls(
            api_key=os.getenv('RUNWARE_API_KEY'),
            timeout=int(os.getenv('RUNWARE_TIMEOUT', '120')),
            max_retries=int(os.getenv('RUNWARE_MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('RUNWARE_RETRY_DELAY', '2.0')),
            base_url=os.getenv('RUNWARE_BASE_URL', 'wss://api.runware.ai/v1'),
            default_model=os.getenv('RUNWARE_DEFAULT_MODEL', 'runware:101@1'),
            max_concurrent_requests=int(os.getenv('RUNWARE_MAX_CONCURRENT', '5')),
            connection_pool_size=int(os.getenv('RUNWARE_POOL_SIZE', '3'))
        )
    
    def is_configured(self) -> bool:
        """Check if configuration is valid"""
        return bool(self.api_key)
    
    def get_model_config(self, model_id: str) -> Dict[str, Any]:
        """Get configuration for a specific model"""
        model_configs = {
            "runware:101@1": {
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True,
                "estimated_cost": 0.01,
                "quality": "high"
            },
            "blackforestlabs:flux-dev@1": {
                "max_resolution": "1024x1024",
                "supports_negative_prompt": True,
                "estimated_cost": 0.02,
                "quality": "very_high"
            },
            "openai:dall-e-3@1": {
                "max_resolution": "1024x1024",
                "supports_negative_prompt": False,
                "estimated_cost": 0.04,
                "quality": "very_high"
            }
        }
        
        return model_configs.get(model_id, {
            "max_resolution": "1024x1024",
            "supports_negative_prompt": True,
            "estimated_cost": 0.01,
            "quality": "medium"
        })
```

## API Endpoints

### Request/Response Models

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Text description of the image to generate")
    model: Optional[str] = Field(None, description="Model to use for generation")
    size: str = Field("1024x1024", description="Image size (e.g., '1024x1024')")
    style: str = Field("fantasy art", description="Art style for the image")
    n: int = Field(1, description="Number of images to generate")
    response_format: str = Field("url", description="Response format: 'url' or 'b64_json'")
    negative_prompt: Optional[str] = Field(None, description="What to avoid in the image")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    guidance_scale: Optional[float] = Field(None, description="How closely to follow the prompt")
    num_inference_steps: Optional[int] = Field(None, description="Number of denoising steps")
    campaign_id: Optional[str] = Field(None, description="Associated campaign ID")

class ImageUpscaleRequest(BaseModel):
    image_url: str = Field(..., description="URL of the image to upscale")
    upscale_factor: int = Field(4, description="Upscaling factor (2, 4, or 8)")
    response_format: str = Field("url", description="Response format: 'url' or 'b64_json'")

class BackgroundRemovalRequest(BaseModel):
    image_path: str = Field(..., description="Path to the image file")
    response_format: str = Field("url", description="Response format: 'url' or 'b64_json'")

class BatchImageRequest(BaseModel):
    requests: List[ImageGenerationRequest] = Field(..., description="List of image generation requests")
    max_concurrent: int = Field(3, description="Maximum concurrent generations")

class ImageGenerationResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    service: str
    model: str
    generation_time: float
    error: Optional[str] = None

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    type: str
    max_resolution: str
    supports_negative_prompt: bool
    estimated_cost: Optional[float] = None
    quality: Optional[str] = None

class ModelsResponse(BaseModel):
    models: List[ModelInfo]
```

### Endpoint Documentation

#### 1. Generate Image
- **POST** `/api/images/generate`
- **Description**: Generate images using the best available service
- **Priority**: Runware → Flux → Gemini
- **Authentication**: Optional (if available)

#### 2. Upscale Image
- **POST** `/api/images/upscale`
- **Description**: Upscale images using Runware's upscaling models
- **Service**: Runware only
- **Authentication**: Optional (if available)

#### 3. Remove Background
- **POST** `/api/images/remove-background`
- **Description**: Remove background from images
- **Service**: Runware only
- **Authentication**: Optional (if available)

#### 4. Batch Generation
- **POST** `/api/images/batch`
- **Description**: Generate multiple images concurrently
- **Service**: Runware (with fallback to other services)
- **Authentication**: Optional (if available)

#### 5. Available Models
- **GET** `/api/images/models`
- **Description**: Get list of available models from all services
- **Authentication**: None required

## Error Handling

### Error Types and Responses

```python
class RunwareError(Exception):
    """Base exception for Runware-related errors"""
    pass

class RunwareConnectionError(RunwareError):
    """Connection-related errors"""
    pass

class RunwareAPIError(RunwareError):
    """API-related errors"""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code

class RunwareModelError(RunwareError):
    """Model-related errors"""
    pass

class RunwareQuotaError(RunwareError):
    """Quota/rate limit errors"""
    pass
```

### Error Handling Strategy

1. **Connection Errors**: Automatic retry with exponential backoff
2. **API Errors**: Log error details and return user-friendly message
3. **Model Errors**: Fallback to alternative models
4. **Quota Errors**: Queue requests or return appropriate error
5. **Timeout Errors**: Retry with longer timeout or fallback service

### Error Response Format

```python
{
    "error": "Error message",
    "error_type": "connection_error|api_error|model_error|quota_error",
    "error_code": "specific_error_code",
    "retry_after": 30,  # seconds (for rate limits)
    "fallback_available": true,
    "suggested_action": "retry|use_fallback|contact_support"
}
```

## Testing Strategy

### Unit Tests

```python
import pytest
import asyncio
from unittest.mock import Mock, patch
from src.core.image.runware_image_service import RunwareImageService

class TestRunwareImageService:
    
    @pytest.fixture
    def service(self):
        with patch.dict(os.environ, {'RUNWARE_API_KEY': 'test-key'}):
            return RunwareImageService()
    
    @pytest.mark.asyncio
    async def test_generate_image_success(self, service):
        # Mock the Runware client
        mock_client = Mock()
        mock_image = Mock()
        mock_image.imageURL = "https://example.com/image.png"
        mock_client.imageInference.return_value = [mock_image]
        
        service.client = mock_client
        service._connected = True
        
        result = await service.generate_image("test prompt")
        
        assert result["success"] is True
        assert len(result["images"]) == 1
        assert result["provider"] == "runware"
    
    @pytest.mark.asyncio
    async def test_generate_image_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            service = RunwareImageService()
            result = await service.generate_image("test prompt")
            
            assert result["error"] == "Runware API key not configured"
            assert result["images"] == []
    
    @pytest.mark.asyncio
    async def test_upscale_image(self, service):
        mock_client = Mock()
        mock_result = Mock()
        mock_result.imageURL = "https://example.com/upscaled.png"
        mock_client.imageUpscale.return_value = [mock_result]
        
        service.client = mock_client
        service._connected = True
        
        result = await service.upscale_image("https://example.com/image.png")
        
        assert result["success"] is True
        assert result["upscale_factor"] == 4
```

### Integration Tests

```python
@pytest.mark.integration
class TestRunwareIntegration:
    
    @pytest.mark.asyncio
    async def test_end_to_end_generation(self):
        """Test complete image generation flow"""
        # This would require actual API key and network access
        # Should be run in CI/CD with test credentials
        pass
    
    @pytest.mark.asyncio
    async def test_service_fallback(self):
        """Test fallback to other services when Runware fails"""
        pass
```

### Performance Tests

```python
@pytest.mark.performance
class TestRunwarePerformance:
    
    @pytest.mark.asyncio
    async def test_concurrent_generation(self):
        """Test concurrent image generation"""
        service = RunwareImageService()
        
        tasks = [
            service.generate_image(f"test prompt {i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert all(result["success"] for result in results)
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing performance"""
        pass
```

## Deployment Considerations

### Environment Setup

1. **API Key Management**
   - Store `RUNWARE_API_KEY` in secure environment variables
   - Use secrets management in production (e.g., AWS Secrets Manager)
   - Never commit API keys to version control

2. **Network Configuration**
   - Ensure WebSocket connections are allowed
   - Configure appropriate timeouts for production
   - Set up monitoring for connection health

3. **Resource Management**
   - Monitor API usage and costs
   - Implement rate limiting to prevent quota exhaustion
   - Set up alerts for service degradation

### Monitoring and Logging

```python
import logging
from datetime import datetime

class RunwareMetrics:
    """Metrics collection for Runware service"""
    
    def __init__(self):
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_generation_time = 0.0
        self.model_usage = {}
    
    def record_request(self, model: str, success: bool, generation_time: float):
        """Record a request metric"""
        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.total_generation_time += generation_time
        self.model_usage[model] = self.model_usage.get(model, 0) + 1
    
    def get_stats(self) -> dict:
        """Get current statistics"""
        avg_time = self.total_generation_time / max(self.request_count, 1)
        success_rate = self.success_count / max(self.request_count, 1)
        
        return {
            "total_requests": self.request_count,
            "success_rate": success_rate,
            "average_generation_time": avg_time,
            "model_usage": self.model_usage,
            "timestamp": datetime.utcnow().isoformat()
        }
```

### Health Checks

```python
@app.get("/api/health/runware")
async def runware_health_check():
    """Health check for Runware service"""
    runware_service = get_runware_image_service()
    
    if not runware_service:
        return {
            "status": "unavailable",
            "reason": "service_not_configured",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    try:
        # Test connection
        await runware_service.connect()
        await runware_service.disconnect()
        
        return {
            "status": "healthy",
            "configured": True,
            "connected": True,
            "available_models": len(runware_service.get_available_models()),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "reason": str(e),
            "configured": True,
            "connected": False,
            "timestamp": datetime.utcnow().isoformat()
        }
```

### Cost Management

1. **Usage Tracking**
   - Monitor API calls and costs
   - Implement usage limits per user/campaign
   - Set up billing alerts

2. **Model Selection**
   - Choose cost-effective models for different use cases
   - Implement intelligent model selection based on requirements
   - Cache results to avoid duplicate generations

3. **Rate Limiting**
   - Implement per-user rate limits
   - Queue requests during high usage periods
   - Provide clear feedback on usage limits

## Conclusion

The integration of Runware's Python SDK into the Gaia D&D Campaign Manager will provide:

1. **Enhanced Image Generation**: Access to multiple high-quality AI models
2. **Improved Performance**: WebSocket-based connections and concurrent processing
3. **Advanced Features**: Upscaling, background removal, and specialized models
4. **Reliability**: Robust error handling and fallback mechanisms
5. **Scalability**: Support for batch processing and high-volume usage

The implementation follows the existing service architecture patterns while adding new capabilities that enhance the overall user experience. The modular design allows for easy maintenance and future enhancements.

## Next Steps

1. **Install Dependencies**: Add `runware` to requirements.txt
2. **Implement Service**: Create `RunwareImageService` class
3. **Update Endpoints**: Modify existing endpoints and add new ones
4. **Add Configuration**: Set up environment variables and config files
5. **Write Tests**: Create comprehensive test suite
6. **Deploy**: Update Docker configuration and deploy to staging
7. **Monitor**: Set up monitoring and alerting for production use

This integration will significantly enhance the image generation capabilities of the Gaia system while maintaining compatibility with existing services and providing a smooth upgrade path.


