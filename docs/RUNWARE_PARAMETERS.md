# Runware API Parameters Guide

## Overview

This document explains how Runware API parameters are handled in the Gaia integration and what the optimal configuration is for each model.

## Runware API Parameters

### Required Parameters
- `positivePrompt` - The text description of the image to generate
- `model` - The Runware model ID (e.g., "rundiffusion:130@100")
- `width` - Image width in pixels
- `height` - Image height in pixels

### Important Optional Parameters
- `outputType` - Output format: "base64Data", "dataURI", or "URL" (recommended to set explicitly)
- `numberResults` - Number of images to generate (default: 1)
- `negativePrompt` - What to avoid in the image
- `seed` - Random seed for reproducibility
- `CFGScale` - How closely to follow the prompt (0-30, default: 7)
- `steps` - Number of denoising steps (1-100, default: 20)
- `scheduler` - Scheduler/sampler to use (e.g., "DPM++ 2M Karras", "Euler", "Euler a", "DDIM")
- `clipSkip` - CLIP skip value (typically 1-2, controls how many layers to skip in CLIP model)
- `outputQuality` - Output quality (0-100, higher is better, affects JPEG/PNG compression)

## Model-Specific Configurations

### Juggernaut Pro (`rundiffusion:130@100`)
- **Steps**: 20 (uses Runware default)
- **Guidance Scale**: 7.5 (slightly higher for better prompt adherence)
- **Negative Prompt**: Not configured by default (can be passed as parameter)
- **Use Case**: High-quality, detailed images
- **Speed**: Medium

### Flux Schnell (`runware:100@1`)
- **Steps**: 4 (optimized for speed)
- **Guidance Scale**: 3.5 (lower for more creativity)
- **Negative Prompt**: Not configured by default (can be passed as parameter)
- **Use Case**: Fast generation with good quality
- **Speed**: Fast

### Flux Pro Ultra (`bfl:2@2`)
- **Steps**: 20 (high quality)
- **Guidance Scale**: 3.5 (balanced for Flux models)
- **Negative Prompt**: Not configured by default (can be passed as parameter)
- **Max Resolution**: 2048x2048 (ultra high resolution support)
- **Use Case**: Ultra high-quality generation, maximum detail and resolution
- **Speed**: Medium

### Juggernaut Lightning (`rundiffusion:110@101`)
- **Steps**: 4 (optimized for speed)
- **Guidance Scale**: 1.0 (very low for maximum speed)
- **Negative Prompt**: Not configured by default (can be passed as parameter)
- **Use Case**: Ultra-fast generation
- **Speed**: Very Fast

### Hidream Fast (`runware:97@3`)
- **Steps**: 16 (balanced speed/quality)
- **Guidance Scale**: 1.0 (low for speed)
- **Scheduler**: "DPM++ 2M Karras"
- **Negative Prompt**: "cartoon, anime, drawing, painting, illustration, 3d render, render, cgi, deformed, disfigured, malformed hands, extra limbs, blurry, out of focus, low quality, bad anatomy, watermark, text, signature, simplistic"
- **CLIP Skip**: 1 (standard skip for better prompt understanding)
- **Output Quality**: 85 (high quality output with reasonable file size)
- **Use Case**: Balanced speed and quality, good for realistic images
- **Speed**: Fast

## Parameter Mapping

### From Config to Runware API
```python
# Our config uses:
model_config.steps          # Maps to steps
model_config.guidance_scale # Maps to CFGScale
model_config.negative_prompt # Maps to negativePrompt
model_config.scheduler      # Maps to scheduler
model_config.clip_skip      # Maps to clipSkip
model_config.output_quality # Maps to outputQuality

# Runware API expects:
IImageInference(
    positivePrompt=prompt,
    model=model,
    width=width,
    height=height,
    numberResults=n,                  # Number of images (default: 1)
    outputType="base64Data",          # "base64Data", "dataURI", or "URL"
    negativePrompt=negative_prompt,   # Optional
    seed=seed,                        # Optional
    CFGScale=guidance_scale,          # Optional
    steps=num_inference_steps,        # Optional
    scheduler=scheduler,              # Optional (e.g., "DPM++ 2M Karras")
    clipSkip=clip_skip,               # Optional (typically 1-2)
    outputQuality=output_quality      # Optional (0-100)
)
```

## Best Practices

### 1. Use Model Defaults
- Each model is configured with optimal defaults
- Parameters are only passed if explicitly set
- Runware API defaults are used when parameters are omitted

### 2. Parameter Optimization
- **High Quality**: Use Juggernaut Pro with default settings
- **Speed**: Use Juggernaut Lightning or Flux Schnell
- **Balance**: Use Hidream Fast

### 3. Custom Parameters
You can override defaults by passing parameters to the API:

```python
# Use custom parameters
result = await runware_service.generate_image(
    prompt="A dragon",
    model="rundiffusion:130@100",
    guidance_scale=10.0,  # Override default
    num_inference_steps=30,  # Override default
    scheduler="DPM++ 2M Karras",  # Specify scheduler
    clip_skip=2,  # Override CLIP skip
    output_quality=90  # Higher quality output
)
```

### 4. Scheduler Configuration
Schedulers control the denoising process and can significantly impact generation quality and speed:

```python
# Example with different schedulers
result = await runware_service.generate_image(
    prompt="A fantasy landscape",
    model="rundiffusion:130@100",
    scheduler="Euler a"  # Fast and creative
)

# Or configure at model level
RUNWARE_MODELS = {
    "custom_model": RunwareModelConfig(
        name="Custom Model",
        model_id="rundiffusion:130@100",
        steps=20,
        guidance_scale=7.5,
        scheduler="DPM++ 2M Karras"  # Default scheduler for this model
    )
}
```

Common scheduler options:
- **"DPM++ 2M Karras"** - High quality, good balance
- **"Euler"** - Fast, deterministic
- **"Euler a"** - Fast, more creative/random
- **"DDIM"** - Deterministic, good for consistency
- **"PNDM"** - Good quality, slower

### 5. Negative Prompt Configuration
Negative prompts tell the model what to avoid in the generated image. Only models that support negative prompts have them configured:

```python
# Use model's default negative prompt (only hidream_fast has one configured)
result = await runware_service.generate_image(
    prompt="A fantasy castle",
    model="hidream_fast"
    # Will automatically use the model's configured negative prompt
)

# Override with custom negative prompt
result = await runware_service.generate_image(
    prompt="A fantasy castle",
    model="juggernaut_pro",
    negative_prompt="cartoon, anime, illustration"  # Custom negative prompt
)

# Disable negative prompt completely
result = await runware_service.generate_image(
    prompt="A fantasy castle",
    model="juggernaut_pro",
    negative_prompt=""  # Empty string disables negative prompt
)

# Configure at model level
RUNWARE_MODELS = {
    "custom_model": RunwareModelConfig(
        name="Custom Model",
        model_id="rundiffusion:130@100",
        steps=20,
        guidance_scale=7.5,
        scheduler="DPM++ 2M Karras",
        negative_prompt="low quality, blurry, distorted"  # Model-specific default
    )
}
```

**Resolution Priority:**
1. **Explicit parameter** - If you pass `negative_prompt="..."`, it uses that (even empty string)
2. **Model config** - If not provided, uses model's default negative prompt (if configured)
3. **None** - If model has no default and no parameter provided, no negative prompt is sent to API

**Note:** Currently, only `hidream_fast` has a default negative prompt configured. Other models require explicit negative prompt parameters if you want to use them.

### 6. CLIP Skip Configuration
CLIP Skip controls how many layers are skipped in the CLIP text encoder. Lower values (1) follow prompts more literally, while higher values (2+) allow more creative interpretation:

```python
# Standard CLIP skip (most accurate to prompt)
result = await runware_service.generate_image(
    prompt="A knight in armor",
    model="hidream_fast",
    clip_skip=1  # Default for hidream_fast
)

# Higher CLIP skip (more artistic freedom)
result = await runware_service.generate_image(
    prompt="A knight in armor",
    model="juggernaut_pro",
    clip_skip=2  # More creative interpretation
)
```

**Typical values:**
- **1** - Most accurate to prompt (recommended for hidream_fast)
- **2** - More artistic freedom (common for Stable Diffusion models)

### 7. Output Quality Configuration
Output Quality controls the compression and final image quality (0-100). Higher values produce better quality but larger file sizes:

```python
# High quality output
result = await runware_service.generate_image(
    prompt="A detailed landscape",
    model="hidream_fast",
    output_quality=90  # Higher quality, larger files
)

# Balanced quality (default for hidream_fast)
result = await runware_service.generate_image(
    prompt="A detailed landscape",
    model="hidream_fast",
    output_quality=85  # Good balance of quality and size
)

# Lower quality for faster delivery
result = await runware_service.generate_image(
    prompt="A detailed landscape",
    model="hidream_fast",
    output_quality=70  # Smaller files, faster downloads
)
```

**Recommended values:**
- **90-100** - Maximum quality for final renders
- **80-85** - Balanced quality/size (recommended)
- **60-70** - Lower quality for previews or bandwidth savings

## Default Values

### Runware API Defaults
- `CFGScale`: 7
- `steps`: 20
- `negativePrompt`: None
- `seed`: Random

### Our Model Defaults
- **Juggernaut Pro**: steps=20, guidance_scale=7.5
- **Flux Schnell**: steps=4, guidance_scale=3.5
- **Juggernaut Lightning**: steps=4, guidance_scale=1.0
- **Hidream Fast**: steps=8, guidance_scale=7.0

## Implementation Details

### Parameter Passing
```python
# Only pass parameters if they're provided
request_params = {
    "positivePrompt": prompt,
    "model": model,
    "width": width,
    "height": height,
    "numberResults": n,
    "outputType": "base64Data"  # or "URL" or "dataURI"
}

# Add optional parameters only if set
if negative_prompt is not None:
    request_params["negativePrompt"] = negative_prompt
if guidance_scale is not None:
    request_params["CFGScale"] = guidance_scale
if num_inference_steps is not None:
    request_params["steps"] = num_inference_steps
if scheduler is not None:
    request_params["scheduler"] = scheduler
if clip_skip is not None:
    request_params["clipSkip"] = clip_skip
if output_quality is not None:
    request_params["outputQuality"] = output_quality

request = IImageInference(**request_params)

# Process the response
images = await client.imageInference(requestImage=request)
for image in images:
    # Access the result based on outputType:
    if outputType == "base64Data":
        data = image.imageBase64Data
    elif outputType == "URL":
        data = image.imageURL
    # Also available: image.seed, image.cost, image.NSFWContent
```

### Configuration Structure
```python
@dataclass
class RunwareModelConfig:
    name: str
    model_id: str                        # The actual Runware model ID
    steps: int                           # Default for steps parameter
    guidance_scale: float                # Default for CFGScale parameter
    negative_prompt: Optional[str] = None # Default negative prompt
    supports_negative_prompt: bool
    max_resolution: int                  # Maximum resolution supported
    scheduler: Optional[str] = None      # Default scheduler (e.g., "DPM++ 2M Karras")
    clip_skip: Optional[int] = None      # CLIP skip value (typically 1-2)
    output_quality: Optional[int] = None # Output quality (0-100)
```

## Recommendations

1. **Start with defaults**: Use the configured defaults for each model
2. **Adjust for quality**: Increase steps and guidance_scale for better quality
3. **Adjust for speed**: Decrease steps and guidance_scale for faster generation
4. **Test different models**: Each model has different strengths
5. **Use negative prompts**: They help improve image quality

## Troubleshooting

### Common Issues
- **Too slow**: Reduce `steps`, use faster models, or try different schedulers (e.g., "Euler a")
- **Poor quality**: Increase `steps` or `CFGScale`, or try "DPM++ 2M Karras" scheduler
- **Not following prompt**: Increase `CFGScale`
- **Too creative**: Decrease `CFGScale` or use a more deterministic scheduler like "DDIM"
- **Inconsistent results**: Set a `seed` value and use deterministic schedulers like "Euler" or "DDIM"

### Parameter Ranges
- `CFGScale`: 0-30 (7 is default)
- `steps`: 1-100 (20 is default)
- `width/height`: Must be multiples of 8, typically 512, 768, 1024

