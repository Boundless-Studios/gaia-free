# Image Provider Architecture Refactoring Plan

## Overview
This document outlines comprehensive enhancements to the image provider system to eliminate unclear fallback logic, reduce complexity, improve type safety, and establish better architectural patterns.

## Current Problems

### 1. **Over-Engineering at Startup**
- `validate_image_providers()` in [main.py:89-134](../backend/src/api/main.py#L89-L134) creates complex initialization order dependencies
- Bypasses singleton pattern by directly manipulating `_runware_service`
- Sends test image generation requests during startup (wasteful, slow)
- Tight coupling between startup and provider initialization

### 2. **Duplicate State Tracking**
Multiple overlapping flags track essentially the same thing:
- `configured` - Has SDK and API key
- `connected` - Has active connection
- `is_available()` - Can generate images

**Result:** Multiple sources of truth, inconsistent state

### 3. **Surprising Auto-Switching Behavior**
- `_validate_current_model()` silently changes user's model selection at startup
- `_get_provider_preferences()` has hardcoded fallback chain disconnected from config
- Users don't know which model will be active until server starts
- Frontend can't predict fallback behavior

### 4. **Centralized Config Mixing Concerns**
`image_config.py` has a single `ModelConfig` class trying to handle all providers:
```python
@dataclass
class ModelConfig:
    huggingface_repo: str          # Only for Flux Local
    checkpoint_name: Optional[str] # Only for Flux Local
    scheduler_config: Optional[Dict] # Only for Flux Local
    runware_model_id: Optional[str] # Only for Runware
```

**Problems:**
- No type safety (optional fields can be None/empty)
- Runware models have `huggingface_repo=""` (code smell)
- Adding new providers requires modifying shared dataclass
- IDE can't provide provider-specific autocomplete

### 5. **Complex Provider Health Checking**
`get_image_models` endpoint in [main.py:1244-1308](../backend/src/api/main.py#L1244-L1308) contains business logic:
- Manual pipeline type to provider mapping
- Filtering models based on provider health
- This logic belongs in the provider/config layer, not API layer

---

## Enhancement Plan

### **Enhancement 1: Remove Startup Validation**
**Goal:** Eliminate complex startup validation, let providers fail gracefully

**Actions:**
1. Delete `validate_image_providers()` function from [main.py:89-134](../backend/src/api/main.py#L89-L134)
2. Remove call to `await validate_image_providers()` from lifespan
3. Let providers validate lazily on first use

**Benefits:**
- Faster startup
- No initialization order dependencies
- Simpler code flow
- Failures are localized to actual usage

**Before:**
```python
async def validate_image_providers():
    # Force instantiation
    if runware_image_service._runware_service is None:
        runware_image_service._runware_service = RunwareImageService()
    service = runware_image_service._runware_service
    await service.validate()
    # ... more complex logic
```

**After:**
```python
# Just remove this entire function
# Providers validate themselves on first generate_image() call
```

---

### **Enhancement 2: Simplify Provider State Tracking**
**Goal:** Single source of truth for provider availability

**Actions:**
1. Remove `configured` flag from all providers
2. Remove `connected` flag from all providers
3. Keep only `is_available() -> bool` method
4. Simplify `RunwareImageService.validate()` to just establish connection

**Benefits:**
- Single source of truth
- No state synchronization issues
- Clearer semantics

**Before (3 overlapping flags):**
```python
class RunwareImageService:
    def __init__(self):
        self.configured = bool(self.api_key) and RUNWARE_AVAILABLE
        self._connected = False

    async def validate(self):
        # ... complex logic with test request
        self.configured = True
        self._connected = True

    def is_available(self):
        return RUNWARE_AVAILABLE and bool(self.api_key) and self.configured
```

**After (single source of truth):**
```python
class RunwareImageService:
    def __init__(self):
        self.client = None

    def is_available(self) -> bool:
        """Single source of truth for availability"""
        return RUNWARE_AVAILABLE and bool(self.api_key)

    async def connect(self):
        """Lazy connection - called on first use"""
        if not self.is_available():
            raise RuntimeError("Runware not available (missing SDK or API key)")

        if self.client:
            return  # Already connected

        self.client = Runware(api_key=self.api_key)
        await self.client.connect()
```

---

### **Enhancement 3: Provider-Owned Configuration**
**Goal:** Each provider owns its models with provider-specific typed config

**Actions:**
1. Create `RunwareModelConfig` and `RunwareProviderInfo` in `runware_image_service.py`
2. Create `FluxModelConfig` and `FluxProviderInfo` in `flux_local_image_service.py`
3. Create `GeminiModelConfig` and `GeminiProviderInfo` in `gemini_image_service.py`
4. Refactor `image_config.py` to be thin aggregation layer

**Benefits:**
- Type safety (no optional fields that don't apply)
- Locality of behavior (provider changes don't affect others)
- Provider-specific validation
- Clear per-provider defaults
- Scales infinitely (adding providers doesn't modify existing code)

**File Structure:**
```
backend/src/core/image/
├── image_config.py              # Thin aggregation layer
├── runware_image_service.py     # Owns RunwareModelConfig + RUNWARE_MODELS
├── flux_local_image_service.py  # Owns FluxModelConfig + FLUX_LOCAL_MODELS
└── gemini_image_service.py      # Owns GeminiModelConfig + GEMINI_MODELS
```

**New Structure:**

#### `runware_image_service.py`
```python
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class RunwareModelConfig:
    """Configuration for a Runware cloud model"""
    name: str
    model_id: str  # Required! (e.g., "rundiffusion:130@100")
    steps: int = 20
    guidance_scale: float = 7.5
    negative_prompt: str = "worst quality, low quality, blurry"
    supports_negative_prompt: bool = True
    max_resolution: int = 1024

@dataclass
class RunwareProviderInfo:
    """Provider-level configuration"""
    name: str = "runware"
    display_name: str = "Runware Cloud"
    description: str = "Fast cloud-based image generation"
    default_model: str = "juggernaut_pro"
    priority: int = 1  # Lower = higher priority
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
        steps=8,
        guidance_scale=7.0
    ),
}

# Provider info singleton
RUNWARE_PROVIDER = RunwareProviderInfo(
    default_model="juggernaut_pro",
    models=RUNWARE_MODELS
)

class RunwareImageService(ImageProvider):
    def __init__(self):
        self.provider_info = RUNWARE_PROVIDER
        self.models = RUNWARE_MODELS
        # ...

    def get_default_model(self) -> str:
        return self.provider_info.default_model
```

#### `flux_local_image_service.py`
```python
@dataclass
class FluxModelConfig:
    """Configuration for a local Flux model"""
    name: str
    huggingface_repo: str  # Required!
    checkpoint_name: str   # Required!
    pipeline_type: str     # Required! ("sdxl" or "sd")
    steps: int
    guidance_scale: float
    negative_prompt: str = ""
    scheduler_config: Optional[Dict] = None
    supports_negative_prompt: bool = True

@dataclass
class FluxProviderInfo:
    name: str = "flux_local"
    display_name: str = "Flux Local (GPU)"
    description: str = "Local GPU image generation using SDXL models"
    default_model: str = "lightning_4step"
    priority: int = 2  # Fallback after cloud
    models: Dict[str, FluxModelConfig] = field(default_factory=dict)

FLUX_LOCAL_MODELS = {
    "lightning_4step": FluxModelConfig(
        name="SDXL Lightning 4-Step",
        huggingface_repo="ByteDance/SDXL-Lightning",
        checkpoint_name="sdxl_lightning_4step.safetensors",
        pipeline_type="sdxl",
        steps=4,
        guidance_scale=0.0,
        scheduler_config={"timestep_spacing": "trailing", "prediction_type": "epsilon"}
    ),
    "lightning_8step": FluxModelConfig(
        name="SDXL Lightning 8-Step",
        huggingface_repo="ByteDance/SDXL-Lightning",
        checkpoint_name="sdxl_lightning_8step.safetensors",
        pipeline_type="sdxl",
        steps=8,
        guidance_scale=0.0,
        scheduler_config={"timestep_spacing": "trailing", "prediction_type": "epsilon"}
    ),
    "juggernaut_xi": FluxModelConfig(
        name="Juggernaut XI v11",
        huggingface_repo="RunDiffusion/Juggernaut-XI-v11",
        checkpoint_name="Juggernaut-XI-byRunDiffusion.safetensors",
        pipeline_type="sdxl",
        steps=30,
        guidance_scale=4.5,
        negative_prompt="fake eyes, bad hands, deformed eyes",
        scheduler_config={"algorithm_type": "sde-dpmsolver++", "solver_type": "midpoint"}
    ),
}

FLUX_LOCAL_PROVIDER = FluxProviderInfo(
    default_model="lightning_4step",
    models=FLUX_LOCAL_MODELS
)
```

#### `image_config.py` (Thin Aggregation Layer)
```python
"""
Central image generation configuration.
Aggregates providers and manages global settings.
"""
from typing import Dict, Optional, Any, Tuple

# Import provider configurations
from src.core.image.runware_image_service import RUNWARE_PROVIDER
from src.core.image.flux_local_image_service import FLUX_LOCAL_PROVIDER
from src.core.image.gemini_image_service import GEMINI_PROVIDER

# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================

# Which provider to prefer by default
DEFAULT_PROVIDER = "runware"

# Provider registry (auto-sorted by priority)
PROVIDERS = {
    "runware": RUNWARE_PROVIDER,
    "flux_local": FLUX_LOCAL_PROVIDER,
    "gemini": GEMINI_PROVIDER,
}

def get_default_model() -> str:
    """Get the default model for the default provider"""
    provider = PROVIDERS.get(DEFAULT_PROVIDER)
    if provider:
        return provider.default_model
    # Fallback to highest priority provider
    sorted_providers = sorted(PROVIDERS.values(), key=lambda p: p.priority)
    return sorted_providers[0].default_model if sorted_providers else "lightning_4step"

# Current model (can be changed at runtime)
CURRENT_MODEL = get_default_model()

class ImageGenerationConfig:
    """Aggregates configuration from all providers"""

    def __init__(self):
        self.current_model = CURRENT_MODEL
        self.providers = PROVIDERS

    def get_all_models(self) -> Dict[str, Tuple[str, Any]]:
        """Get all models from all providers.

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
        raise ValueError(f"Unknown model: {self.current_model}")

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
        return False

# Singleton
_config = ImageGenerationConfig()

def get_image_config() -> ImageGenerationConfig:
    return _config
```

---

### **Enhancement 4: Deterministic Provider Fallback**
**Goal:** Predictable, explicit fallback logic without surprises

**Actions:**
1. Delete `_validate_current_model()` and `_get_provider_preferences()` from `image_service_manager.py`
2. Implement `get_available_provider_with_fallback()` that uses provider priorities
3. Log clear messages about fallback decisions
4. Don't auto-switch at startup - fail gracefully with clear errors

**Benefits:**
- Deterministic behavior (same config = same result)
- No runtime surprises
- Clear error messages guide users to solutions
- Testable without runtime state

**Before (Surprising auto-switch at startup):**
```python
def _validate_current_model(self):
    """Silently changes user's model at startup"""
    # ... complex logic
    logger.info(f"🔄 Auto-switching to {provider_name}")
    self.config.set_model(default_model_key)  # User has no idea this happened!
```

**After (Explicit, deterministic):**
```python
def get_available_provider_with_fallback(self) -> Tuple[str, str]:
    """
    Get the best available provider and its default model.

    Returns: (provider_name, model_key)

    Raises: RuntimeError if no providers available

    This is DETERMINISTIC - same inputs = same outputs.
    """
    from src.core.image.image_config import PROVIDERS, DEFAULT_PROVIDER

    # Try default provider first
    if DEFAULT_PROVIDER in PROVIDERS:
        provider_config = PROVIDERS[DEFAULT_PROVIDER]
        if DEFAULT_PROVIDER in self.providers and \
           self.providers[DEFAULT_PROVIDER].is_available():
            logger.info(f"✅ Using preferred provider: {DEFAULT_PROVIDER} "
                       f"with model: {provider_config.default_model}")
            return (DEFAULT_PROVIDER, provider_config.default_model)
        else:
            logger.warning(f"⚠️  Preferred provider '{DEFAULT_PROVIDER}' is not available")

    # Fallback: try providers in priority order
    sorted_providers = sorted(
        [(name, info) for name, info in PROVIDERS.items()],
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
```

---

### **Enhancement 5: Simplify API Endpoints**
**Goal:** Move business logic out of API layer into provider/config layer

**Actions:**
1. Simplify `get_image_models` endpoint to use provider-grouped data
2. Remove manual pipeline type mapping from API
3. Let providers and config handle model organization

**Benefits:**
- API layer is thin and focused on HTTP concerns
- Business logic is testable without HTTP
- Single source of truth for provider/model relationships

**Before (Complex filtering in API layer):**
```python
@app.get("/api/image-models")
async def get_image_models():
    config = get_image_config()
    manager = get_image_service_manager()
    provider_health = manager.get_service_health()

    models = []
    for key, model_config in config.models.items():
        pipeline_type = model_config.pipeline_type

        # Manual mapping (duplicated knowledge!)
        pipeline_provider_map = {
            "sdxl": "flux_local",
            "sd": "flux_local",
            "runware": "runware",
            "gemini": "gemini",
        }

        provider_name = pipeline_provider_map.get(pipeline_type)

        # Complex filtering logic
        if provider_name and provider_name in provider_health:
            provider_status = provider_health[provider_name]
            if provider_status.get("available", False):
                models.append({...})

    return {"models": models, ...}
```

**After (Clean, provider-driven):**
```python
@app.get("/api/image-models")
async def get_image_models():
    """Get available models grouped by provider"""
    from src.core.image.image_config import get_image_config, PROVIDERS
    from src.core.image.image_service_manager import get_image_service_manager

    config = get_image_config()
    manager = get_image_service_manager()

    # Build provider status
    providers_status = {}
    for provider_name, provider_config in PROVIDERS.items():
        # Check if provider is registered and available
        is_available = (
            provider_name in manager.providers and
            manager.providers[provider_name].is_available()
        )

        providers_status[provider_name] = {
            "name": provider_name,
            "display_name": provider_config.display_name,
            "description": provider_config.description,
            "available": is_available,
            "default_model": provider_config.default_model,
            "priority": provider_config.priority,
            "models": []
        }

        # Add models if provider is available
        if is_available:
            for model_key, model_config in provider_config.models.items():
                providers_status[provider_name]["models"].append({
                    "key": model_key,
                    "name": model_config.name,
                    "is_default": model_key == provider_config.default_model
                })

    # Get active provider and model
    try:
        active_provider, active_model = manager.get_available_provider_with_fallback()
    except RuntimeError as e:
        return {
            "providers": providers_status,
            "current_provider": None,
            "current_model": None,
            "error": str(e)
        }

    return {
        "providers": providers_status,
        "current_provider": active_provider,
        "current_model": active_model
    }
```

---

### **Enhancement 6: Clear Error Messages**
**Goal:** Guide users to solutions instead of silent failures

**Actions:**
1. When provider unavailable, return explicit error with remediation steps
2. Remove silent auto-switching
3. Add context to error messages

**Benefits:**
- Users understand what went wrong
- Clear path to resolution
- Easier debugging

**Examples:**

```python
# Provider not available during generation
if not provider.is_available():
    raise RuntimeError(
        f"Provider '{provider_name}' is not available. "
        f"Reason: {provider.get_unavailability_reason()}\n"
        f"Solution: {provider.get_setup_instructions()}"
    )

# No providers at all
raise RuntimeError(
    "No image providers available! Please configure at least one provider:\n"
    "- Runware: Set RUNWARE_API_KEY environment variable\n"
    "- Flux Local: Ensure CUDA GPU is available\n"
    "- Gemini: Set GEMINI_API_KEY environment variable"
)

# Model not found
raise ValueError(
    f"Model '{model_key}' not found. Available models:\n" +
    "\n".join(f"  - {key}: {config.name}" for key, config in all_models.items())
)
```

---

## Implementation Order

1. ✅ **Review Plan** (Current step)
2. **Phase 1: Simplification** (Remove complexity)
   - Remove `validate_image_providers()` from main.py
   - Delete `_validate_current_model()` and `_get_provider_preferences()`
   - Simplify state tracking (single `is_available()`)
3. **Phase 2: Provider-Owned Config** (Architectural improvement)
   - Create provider-specific config classes
   - Move model definitions into provider files
   - Refactor `image_config.py` to aggregation layer
4. **Phase 3: Better Fallback** (Deterministic behavior)
   - Implement `get_available_provider_with_fallback()`
   - Update `get_provider_for_model()` to use new pattern
   - Add clear error messages
5. **Phase 4: API Cleanup** (Simplify endpoints)
   - Simplify `get_image_models` endpoint
   - Remove business logic from API layer
6. **Phase 5: Testing** (Verify correctness)
   - Test with all providers available
   - Test with each provider individually
   - Test with no providers (error handling)
   - Verify UI displays correctly

---

## Migration Notes

### Breaking Changes
**None!** This refactoring preserves all external APIs:
- `/api/image-models` returns same structure (enhanced with provider info)
- `/api/generate-image` works exactly the same
- Environment variables unchanged
- Model keys unchanged

### Backward Compatibility
- Existing model keys continue to work
- `CURRENT_MODEL` can still be set in config
- Provider registration unchanged
- All existing functionality preserved

---

## Success Criteria

✅ **Reduced Complexity**
- ~150 lines of code removed
- No initialization order dependencies
- Single source of truth for availability

✅ **Better Architecture**
- Providers own their config
- Type-safe per-provider models
- Scales infinitely (new providers don't modify existing code)

✅ **Predictable Behavior**
- Deterministic fallback (same config = same result)
- Clear error messages
- No silent auto-switching

✅ **Maintainability**
- Provider changes are localized
- Easy to add new providers
- Clear separation of concerns

✅ **User Experience**
- UI knows exactly what's available
- Clear error messages guide users
- Fast startup (no validation delays)

---

## Files Modified

### Deleted Code
- `backend/src/api/main.py:89-134` - `validate_image_providers()`
- `backend/src/core/image/image_service_manager.py:66-126` - Auto-switching logic

### Major Refactors
- `backend/src/core/image/image_config.py` - Thin aggregation layer
- `backend/src/core/image/runware_image_service.py` - Add provider config
- `backend/src/core/image/flux_local_image_service.py` - Add provider config
- `backend/src/core/image/gemini_image_service.py` - Add provider config
- `backend/src/core/image/image_service_manager.py` - Deterministic fallback

### Minor Updates
- `backend/src/api/main.py` - Simplify `get_image_models` endpoint
- All provider files - Remove duplicate state flags

---

## Risk Assessment

**Low Risk** because:
- No external API changes
- All functionality preserved
- Can be implemented incrementally
- Easy to rollback (git revert)
- No database changes
- No dependency changes

**Testing Strategy:**
- Unit tests for new provider config classes
- Integration tests for fallback logic
- Manual testing with Docker containers
- Verify each provider works independently

---

## Questions for Review

1. Should we keep the centralized `ModelConfig` compatibility layer temporarily?
2. Should provider priorities be configurable via environment variables?
3. Should we add provider health check endpoint (`/api/image-providers/health`)?
4. Should fallback be configurable (strict mode vs auto-fallback)?

---

## Next Steps

After approval:
1. Create feature branch: `feature/image-provider-refactor`
2. Implement Phase 1 (simplification)
3. Test Phase 1 changes
4. Implement Phase 2 (provider-owned config)
5. Test Phase 2 changes
6. Continue through phases 3-5
7. Create PR with comprehensive testing
