# Image Service Manager Architecture Plan

## Overview

This document outlines the plan to restructure the image generation services to create a cleaner, more maintainable architecture with proper separation of concerns.

## Current Problem

The current architecture has several issues:

1. **Misleading Naming**: `FluxLocalImageService` suggests local-only but handles both local and cloud models
2. **Mixed Responsibilities**: Single service handles multiple model types through delegation
3. **Architectural Confusion**: Delegation pattern creates indirection and unclear service boundaries
4. **Maintenance Issues**: Hard to understand which service handles what

## Proposed Architecture

### 1. ImageServiceManager (Central Router)

**File**: `backend/src/core/image/image_service_manager.py`

**Purpose**: Central manager that routes image generation requests to appropriate services based on model type.

**Responsibilities**:
- Route requests to correct service based on `pipeline_type`
- Provide unified interface for all image generation
- Aggregate model information from all services
- Centralized health checking
- Service discovery and management

**Key Methods**:
```python
class ImageServiceManager:
    async def generate_image(...) -> Dict[str, Any]
    def get_available_models() -> Dict[str, Any]
    def get_service_health() -> Dict[str, Any]
```

**Service Routing Logic**:
```python
if pipeline_type == "runware":
    service = runware_service
elif pipeline_type in ["sdxl", "sd"]:
    service = flux_local_service
elif pipeline_type == "gemini":
    service = gemini_service
elif pipeline_type == "parasail":
    service = parasail_service
else:
    service = flux_local_service  # fallback
```

### 2. FluxLocalImageService (Local Only)

**File**: `backend/src/core/image/flux_local_image_service.py` (refactored)

**Purpose**: Handle ONLY local HuggingFace models (SDXL, Flux, etc.)

**Responsibilities**:
- Load and manage HuggingFace models locally
- Handle GPU/CPU optimization
- Manage model caching and memory
- Generate images using diffusers pipelines

**Removed Responsibilities**:
- ~~Delegation to cloud services~~
- ~~Runware model handling~~
- ~~Service routing logic~~

**Validation**:
```python
if current_model_config.pipeline_type not in ["sdxl", "sd"]:
    return {"error": "FluxLocalImageService only handles local models"}
```

### 3. Service-Specific Responsibilities

| Service | Pipeline Types | Responsibilities |
|---------|----------------|------------------|
| **FluxLocalImageService** | `sdxl`, `sd` | Local HuggingFace models, GPU optimization |
| **RunwareImageService** | `runware` | Runware cloud API, WebSocket connections |
| **GeminiImageService** | `gemini` | Google Gemini API, prompt enhancement |
| **ParasailImageService** | `parasail` | Parasail API, batch processing |

### 4. Updated API Endpoints

**File**: `backend/src/api/main.py`

**Changes**:
- Replace direct service calls with ImageServiceManager
- Unified error handling
- Centralized service health checks
- Consistent response format

**New Endpoints**:
```python
@app.get("/api/health/images")
async def image_services_health():
    """Health check for all image services"""

@app.get("/api/images/models")
async def get_available_models():
    """Get all available models from all services"""
```

### 5. Enhanced Configuration

**File**: `backend/src/core/image/image_config.py`

**Additions**:
```python
@dataclass
class ModelConfig:
    # ... existing fields ...
    gemini_model_id: Optional[str] = None
    parasail_model_id: Optional[str] = None
```

**Pipeline Type Mapping**:
```python
PIPELINE_TYPE_SERVICE_MAP = {
    "sdxl": "flux_local",
    "sd": "flux_local", 
    "runware": "runware",
    "gemini": "gemini",
    "parasail": "parasail"
}
```

## Implementation Plan

### Phase 1: Create ImageServiceManager
1. Create `image_service_manager.py`
2. Implement service discovery and routing
3. Add unified interface methods
4. Create singleton pattern

### Phase 2: Refactor FluxLocalImageService
1. Remove delegation logic (`_delegate_to_runware`)
2. Add pipeline type validation
3. Clean up service boundaries
4. Update method documentation

### Phase 3: Update API Integration
1. Replace direct service calls in `main.py`
2. Update image generation endpoint
3. Add new health check endpoints
4. Update model listing endpoint

### Phase 4: Configuration Updates
1. Add new pipeline types to config
2. Update model configurations
3. Add service-specific model IDs
4. Update configuration validation

### Phase 5: Testing and Validation
1. Test all service integrations
2. Verify service routing works correctly
3. Test fallback mechanisms
4. Validate health checks

## Code Examples

### ImageServiceManager Implementation

```python
"""
Central Image Service Manager
Routes requests to appropriate service based on model type
"""

import logging
from typing import Optional, Dict, Any
from src.core.image.flux_local_image_service import get_flux_local_image_service
from src.core.image.runware_image_service import get_runware_image_service
from src.core.image.gemini_image_service import get_gemini_image_service
from src.core.image.parasail_image_service import get_parasail_image_service
from src.core.image.image_config import get_image_config

logger = logging.getLogger(__name__)

class ImageServiceManager:
    """Central manager that routes image generation requests to appropriate services"""
    
    def __init__(self):
        self.config = get_image_config()
        self.services = {
            "flux_local": get_flux_local_image_service(),
            "runware": get_runware_image_service(),
            "gemini": get_gemini_image_service(),
            "parasail": get_parasail_image_service()
        }
    
    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
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
        """Route image generation to appropriate service"""
        
        # Get current model config
        current_config = self.config.get_current_config()
        
        # Determine which service to use based on pipeline type
        if current_config.pipeline_type == "runware":
            service = self.services["runware"]
            service_name = "Runware"
        elif current_config.pipeline_type in ["sdxl", "sd"]:
            service = self.services["flux_local"]
            service_name = "Flux Local"
        elif current_config.pipeline_type == "gemini":
            service = self.services["gemini"]
            service_name = "Gemini"
        elif current_config.pipeline_type == "parasail":
            service = self.services["parasail"]
            service_name = "Parasail"
        else:
            # Fallback to flux_local for unknown types
            service = self.services["flux_local"]
            service_name = "Flux Local (fallback)"
        
        if not service:
            return {
                "error": f"{service_name} service not available",
                "images": []
            }
        
        logger.info(f"Routing to {service_name} service for model: {current_config.name}")
        
        # Route to appropriate service
        return await service.generate_image(
            prompt=prompt,
            model=model,
            width=width,
            height=height,
            n=n,
            response_format=response_format,
            negative_prompt=negative_prompt,
            seed=seed,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            **kwargs
        )
    
    def get_available_models(self) -> Dict[str, Any]:
        """Get all available models from all services"""
        all_models = []
        
        for service_name, service in self.services.items():
            if service:
                if hasattr(service, 'get_available_models'):
                    models = service.get_available_models()
                    all_models.extend(models)
                elif hasattr(service, 'get_model_info'):
                    info = service.get_model_info()
                    all_models.append({
                        "id": info.get("model_key", service_name),
                        "name": info.get("model", service_name),
                        "provider": service_name,
                        "type": "text-to-image"
                    })
        
        return {"models": all_models}
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get health status of all services"""
        health = {}
        
        for service_name, service in self.services.items():
            if service:
                if hasattr(service, 'get_model_info'):
                    info = service.get_model_info()
                    health[service_name] = {
                        "available": True,
                        "configured": info.get("configured", False),
                        "connected": info.get("connected", False)
                    }
                else:
                    health[service_name] = {"available": True, "configured": True}
            else:
                health[service_name] = {"available": False, "configured": False}
        
        return health

# Singleton instance
_image_service_manager = None

def get_image_service_manager() -> Optional[ImageServiceManager]:
    """Get the singleton image service manager"""
    global _image_service_manager
    if _image_service_manager is None:
        _image_service_manager = ImageServiceManager()
    return _image_service_manager
```

### Refactored FluxLocalImageService

```python
"""
Local Image Generation Service
Handles ONLY local HuggingFace models (SDXL, Flux, etc.)
"""

class FluxLocalImageService:
    """Service for handling LOCAL image generation using HuggingFace models"""
    
    def __init__(self):
        self.model = None
        self.device = None
        self.config = get_image_config()
        self.active_model_config = self.config.get_current_config()
        self.current_model_key = self.config.current_model
        
        # Only handle local models
        if self.active_model_config.pipeline_type not in ["sdxl", "sd"]:
            logger.warning(f"FluxLocalImageService initialized with non-local model: {self.active_model_config.pipeline_type}")
    
    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        n: int = 1,
        response_format: str = "b64_json",
        seed: Optional[int] = None,
        size: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate images using LOCAL HuggingFace models only
        
        This service ONLY handles local models with pipeline_type "sdxl" or "sd"
        """
        # Validate that we're handling a local model
        current_model_config = self.active_model_config
        if current_model_config.pipeline_type not in ["sdxl", "sd"]:
            return {
                "error": f"FluxLocalImageService only handles local models, got: {current_model_config.pipeline_type}",
                "images": []
            }
        
        # Load model if not already loaded
        if not hasattr(self, 'pipeline') or self.pipeline is None:
            logger.info(f"Loading local model {self.current_model_key} for image generation...")
            self._init_model()
            if not hasattr(self, 'pipeline') or self.pipeline is None:
                return {
                    "error": "Failed to load local model. Check logs for details.",
                    "images": []
                }
        
        # Continue with existing local generation logic...
        # (All the existing _init_model, pipeline generation code stays here)
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the local model service"""
        return {
            "provider": "flux_local",
            "model": self.active_model_config.name,
            "model_key": self.config.current_model,
            "pipeline_type": self.active_model_config.pipeline_type,
            "configured": True,
            "connected": hasattr(self, 'pipeline') and self.pipeline is not None,
            "supports_negative_prompt": self.active_model_config.supports_negative_prompt,
            "device": str(self.device) if self.device else "not initialized"
        }
```

### Updated API Endpoints

```python
@app.post("/api/images/generate")
async def generate_image(
    request: ImageGenerationRequest,
    current_user = require_auth_if_available()
):
    """Generate an image using the image service manager"""
    logger.info(f"Received image generation request: model={request.model}, type={request.image_type}")
    
    try:
        from src.core.image.image_service_manager import get_image_service_manager
        
        # Get the central image service manager
        image_manager = get_image_service_manager()
        if not image_manager:
            raise HTTPException(status_code=503, detail="Image service manager not available")
        
        # Enhance prompt with style
        enhanced_prompt = f"{request.prompt}, {request.style} style"
        
        # Generate image through the manager
        result = await image_manager.generate_image(
            prompt=enhanced_prompt,
            model=request.model,
            width=int(request.size.split('x')[0]),
            height=int(request.size.split('x')[1]),
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
                "service": result.get("provider", "unknown"),
                "model": result.get("model", ""),
                "generation_time": image_data.get("generation_time", 0)
            }
        else:
            raise HTTPException(status_code=500, detail="No images generated")
            
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/images/models")
async def get_available_models():
    """Get list of available image generation models from all services"""
    from src.core.image.image_service_manager import get_image_service_manager
    
    manager = get_image_service_manager()
    if not manager:
        return {"models": []}
    
    return manager.get_available_models()

@app.get("/api/health/images")
async def image_services_health():
    """Health check for all image services"""
    from src.core.image.image_service_manager import get_image_service_manager
    
    manager = get_image_service_manager()
    if not manager:
        return {"error": "Image service manager not available"}
    
    return manager.get_service_health()
```

## Benefits

### ✅ Clear Separation of Concerns
- **ImageServiceManager**: Routing and orchestration
- **FluxLocalImageService**: Only local HuggingFace models
- **RunwareImageService**: Only Runware cloud models
- **GeminiImageService**: Only Gemini cloud models
- **ParasailImageService**: Only Parasail cloud models

### ✅ Better Maintainability
- Each service has a single responsibility
- Easy to add new services
- Clear service boundaries
- No more delegation confusion

### ✅ Improved API
- Single entry point through ImageServiceManager
- Consistent interface across all services
- Better error handling and logging
- Centralized health checks

### ✅ Future-Proof
- Easy to add new model providers
- Service-specific optimizations
- Independent scaling of services
- Better testing isolation

## Migration Checklist

- [ ] Create `image_service_manager.py`
- [ ] Remove delegation logic from `FluxLocalImageService`
- [ ] Add pipeline type validation to `FluxLocalImageService`
- [ ] Update API endpoints in `main.py`
- [ ] Add new health check endpoints
- [ ] Update model listing endpoint
- [ ] Add new pipeline types to `image_config.py`
- [ ] Update model configurations
- [ ] Test all service integrations
- [ ] Verify service routing works correctly
- [ ] Test fallback mechanisms
- [ ] Validate health checks
- [ ] Update documentation
- [ ] Update tests

## Testing Strategy

1. **Unit Tests**: Test each service independently
2. **Integration Tests**: Test service routing through ImageServiceManager
3. **API Tests**: Test all endpoints with different model types
4. **Health Check Tests**: Verify health endpoints work correctly
5. **Fallback Tests**: Test fallback mechanisms when services are unavailable

## Rollback Plan

If issues arise during migration:

1. Keep current `FluxLocalImageService` as backup
2. Implement feature flags to switch between old and new architecture
3. Gradual rollout by service type
4. Monitor performance and error rates
5. Quick rollback to current implementation if needed

## Future Enhancements

1. **Service Discovery**: Automatic detection of available services
2. **Load Balancing**: Distribute requests across multiple service instances
3. **Caching Layer**: Add caching for frequently requested models
4. **Metrics Collection**: Add detailed metrics for each service
5. **Circuit Breaker**: Add circuit breaker pattern for service failures
6. **Service Mesh**: Consider service mesh for advanced routing


