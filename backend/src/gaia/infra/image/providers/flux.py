"""
Local Image Generation Service

DEPRECATED: This module is deprecated as we've moved to remote image generation only.
Local image generation (using PyTorch, diffusers, etc.) is no longer supported.
This module is kept for backward compatibility but all functionality is disabled.

Use Runware or other remote image generation services instead.
"""

import os
import logging
import base64
import json
import time
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
import warnings
from PIL import Image
import io
from dataclasses import dataclass, field
from gaia.infra.image.image_provider import ImageProvider, ProviderCapabilities

logger = logging.getLogger(__name__)

# Emit deprecation warning when module is imported
warnings.warn(
    "flux_local_image_service is deprecated. The system now uses remote image generation only. "
    "Local PyTorch-based image generation is no longer supported.",
    DeprecationWarning,
    stacklevel=2
)

# =============================================================================
# Provider Configuration
# =============================================================================

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
    """Provider-level configuration"""
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
        scheduler_config={
            "timestep_spacing": "trailing",
            "prediction_type": "epsilon"
        }
    ),
    "lightning_8step": FluxModelConfig(
        name="SDXL Lightning 8-Step",
        huggingface_repo="ByteDance/SDXL-Lightning",
        checkpoint_name="sdxl_lightning_8step.safetensors",
        pipeline_type="sdxl",
        steps=8,
        guidance_scale=0.0,
        scheduler_config={
            "timestep_spacing": "trailing",
            "prediction_type": "epsilon"
        }
    ),
    "juggernaut_xi": FluxModelConfig(
        name="Juggernaut XI v11",
        huggingface_repo="RunDiffusion/Juggernaut-XI-v11",
        checkpoint_name="Juggernaut-XI-byRunDiffusion.safetensors",
        pipeline_type="sdxl",
        steps=30,
        guidance_scale=4.5,
        negative_prompt="fake eyes, bad hands, deformed eyes, cgi, 3D, digital, airbrushed",
        scheduler_config={
            "algorithm_type": "sde-dpmsolver++",
            "solver_type": "midpoint",
            "use_karras_sigmas": True,
            "solver_order": 2,
            "prediction_type": "epsilon"
        }
    ),
}

FLUX_LOCAL_PROVIDER = FluxProviderInfo(
    default_model="lightning_4step",
    models=FLUX_LOCAL_MODELS
)


class FluxLocalImageService(ImageProvider):
    """Service for handling local image generation using configurable models"""
    
    def __init__(self):
        # Check if CUDA is available first - fail fast if not
        if not torch.cuda.is_available():
            raise RuntimeError("GPU/CUDA not available - Flux Local service requires GPU")

        self.provider_info = FLUX_LOCAL_PROVIDER
        self.models = FLUX_LOCAL_MODELS
        self.model = None
        self.device = torch.device("cuda")

        # Lazy import to avoid circular dependency
        from gaia.infra.image.image_config import get_image_config
        self.config = get_image_config()
        self.active_model_config = self.config.get_current_config()
        self.current_model_key = self.config.current_model  # Track which model is loaded

        logger.info(f"✅ Flux Local image service initialized successfully - GPU: {torch.cuda.get_device_name()}")

        # Don't load model immediately - wait for first generation

    def get_default_model(self) -> str:
        """Get the default model for this provider"""
        return self.provider_info.default_model
    
    def _init_model(self):
        """Initialize the model based on current configuration"""
        try:
            model_config = self.active_model_config
            logger.info(f"Initializing: {model_config.name}")

            # Import required libraries
            from diffusers import DiffusionPipeline, StableDiffusionXLPipeline, DPMSolverMultistepScheduler, EulerDiscreteScheduler
            from huggingface_hub import hf_hub_download, login

            # Set up HuggingFace authentication
            huggingface_key = os.getenv('HUGGING_FACE_KEY')
            if huggingface_key:
                try:
                    login(token=huggingface_key)
                    logger.info("Successfully authenticated with HuggingFace")
                except Exception as e:
                    logger.warning(f"Failed to authenticate with HuggingFace: {e}")
            else:
                logger.info("No HUGGING_FACE_KEY provided, using anonymous access")
            
            # Set memory efficient loading options
            load_kwargs = {
                "torch_dtype": torch.float16 if self.device.type == "cuda" else torch.float32,
                "use_safetensors": True,
                "variant": "fp16" if self.device.type == "cuda" else None,
                "low_cpu_mem_usage": True,
                "token": huggingface_key if huggingface_key else None,
            }
            
            # Set CUDA optimizations
            if self.device.type == "cuda":
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                torch.backends.cudnn.benchmark = True
                logger.info("Enabled CUDA optimizations (TF32, cuDNN benchmark)")
            
            # Intelligent model loading with checkpoint support
            if model_config.checkpoint_name:
                logger.info(f"Loading model from checkpoint: {model_config.checkpoint_name}")

                try:
                    # Load from specific checkpoint file
                    checkpoint_path = hf_hub_download(
                        model_config.huggingface_repo,
                        model_config.checkpoint_name,
                        cache_dir=os.getenv('HF_HOME', '/home/gaia/.cache/huggingface'),
                        token=huggingface_key
                    )
                    logger.info(f"Checkpoint downloaded to: {checkpoint_path}")

                    # Load the pipeline from the checkpoint
                    self.pipeline = StableDiffusionXLPipeline.from_single_file(
                        checkpoint_path,
                        torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                        use_safetensors=True,
                        use_fast=True
                    ).to(self.device)

                    logger.info(f"Loaded model from checkpoint: {model_config.name}")

                except Exception as e:
                    logger.error(f"Failed to load checkpoint: {e}")
                    logger.info("Falling back to standard model loading...")
                    # Fallback to repository loading
                    if model_config.pipeline_type == "sdxl":
                        self.pipeline = StableDiffusionXLPipeline.from_pretrained(
                            model_config.huggingface_repo, **load_kwargs
                        ).to(self.device)
                    else:
                        self.pipeline = DiffusionPipeline.from_pretrained(
                            model_config.huggingface_repo, **load_kwargs
                        ).to(self.device)
                    raise e

            else:
                # Standard repository loading
                if model_config.pipeline_type == "sdxl":
                    self.pipeline = StableDiffusionXLPipeline.from_pretrained(
                        model_config.huggingface_repo, **load_kwargs
                    ).to(self.device)
                else:
                    self.pipeline = DiffusionPipeline.from_pretrained(
                        model_config.huggingface_repo, **load_kwargs
                    ).to(self.device)

                logger.info(f"Loaded standard model: {model_config.name}")

            # Apply scheduler configuration after model loading
            self._apply_scheduler_config(model_config)
            
            # Enable various memory optimizations
            if hasattr(self.pipeline, 'enable_attention_slicing'):
                self.pipeline.enable_attention_slicing()
                logger.info("Enabled attention slicing for memory efficiency")
            
            # Enable VAE slicing for large images
            if hasattr(self.pipeline, 'enable_vae_slicing'):
                self.pipeline.enable_vae_slicing()
                logger.info("Enabled VAE slicing for large image support")
            
#            # Enable xformers if available for memory efficiency
#            try:
#                self.pipeline.enable_xformers_memory_efficient_attention()
#                logger.info("Enabled xformers memory efficient attention")
#            except Exception as e:
#                logger.info(f"xformers not available ({e}), using default attention")
            
            # Try to set up Compel for better prompt handling (optional)
            self.compel = None
            try:
                from compel import Compel, ReturnedEmbeddingsType
                # Only use Compel for SDXL models
                if hasattr(self.pipeline, 'tokenizer_2'):
                    self.compel = Compel(
                        tokenizer=[self.pipeline.tokenizer, self.pipeline.tokenizer_2],
                        text_encoder=[self.pipeline.text_encoder, self.pipeline.text_encoder_2],
                        returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,
                        requires_pooled=[False, True]
                    )
                    logger.info("Enabled Compel for better long prompt handling")
                else:
                    self.compel = Compel(tokenizer=self.pipeline.tokenizer, text_encoder=self.pipeline.text_encoder)
                    logger.info("Enabled Compel for standard SD models")
            except Exception as e:
                logger.info(f"Compel not available ({e}), using standard prompt encoding")
            
            # Check GPU memory and optimize accordingly
            if self.device.type == "cuda":
                # Get VRAM info first
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                
                # Only enable CPU offload for very low VRAM
                if vram_gb < 6:
                    if hasattr(self.pipeline, 'enable_model_cpu_offload'):
                        self.pipeline.enable_model_cpu_offload()
                        logger.info("Enabled model CPU offload for low VRAM GPU")
                else:
                    # For GPUs with decent VRAM, keep everything on GPU
                    logger.info("Keeping full model on GPU for better performance")
   
                used_vram_gb = torch.cuda.memory_reserved(0) / (1024**3)
                free_vram_gb = vram_gb - used_vram_gb
                logger.info(f"Local image generation model loaded successfully (VRAM: {used_vram_gb:.1f} GB used, {free_vram_gb:.1f} GB free)")
            else:
                logger.info("Local image generation model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.error("Make sure you have diffusers and transformers installed:")
            logger.error("pip install diffusers transformers accelerate")

    def _apply_scheduler_config(self, model_config):
        """Apply the scheduler configuration faithfully without hardcoded defaults"""
        if not model_config.scheduler_config:
            logger.warning(f"No scheduler configuration provided for {model_config.name}")
            return

        logger.info(f"🔧 Applying scheduler configuration for {model_config.name}:")
        for key, value in model_config.scheduler_config.items():
            logger.info(f"   {key}: {value}")

        # Get base config and apply model-specific overrides
        base_config = dict(self.pipeline.scheduler.config)
        base_config.update(model_config.scheduler_config)

        # Determine scheduler type based on algorithm_type
        algorithm_type = model_config.scheduler_config.get("algorithm_type")

        if algorithm_type == "dpmsolver++":
            from diffusers import DPMSolverMultistepScheduler
            self.pipeline.scheduler = DPMSolverMultistepScheduler.from_config(base_config)
            logger.info("Applied DPMSolverMultistepScheduler")
        elif algorithm_type == "sde-dpmsolver++":
            from diffusers import DPMSolverMultistepScheduler
            self.pipeline.scheduler = DPMSolverMultistepScheduler.from_config(base_config)
            logger.info("Applied DPMSolverMultistepScheduler with SDE algorithm")
        elif algorithm_type == "euler":
            from diffusers import EulerDiscreteScheduler
            self.pipeline.scheduler = EulerDiscreteScheduler.from_config(base_config)
            logger.info("Applied EulerDiscreteScheduler")
        else:
            # Auto-detect based on configuration structure
            if "solver_type" in base_config or "solver_order" in base_config:
                from diffusers import DPMSolverMultistepScheduler
                self.pipeline.scheduler = DPMSolverMultistepScheduler.from_config(base_config)
                logger.info("Auto-detected DPMSolverMultistepScheduler")
            else:
                from diffusers import EulerDiscreteScheduler
                self.pipeline.scheduler = EulerDiscreteScheduler.from_config(base_config)
                logger.info("Auto-detected EulerDiscreteScheduler")

        # Log final scheduler verification
        config = self.pipeline.scheduler.config
        scheduler_type = type(self.pipeline.scheduler).__name__
        logger.info(f"📋 Final scheduler: {scheduler_type}")
        logger.info(f"📋 Scheduler parameters:")
        logger.info(f"   algorithm_type: {getattr(config, 'algorithm_type', 'N/A')}")
        logger.info(f"   timestep_spacing: {getattr(config, 'timestep_spacing', 'N/A')}")
        if hasattr(config, 'use_karras_sigmas'):
            logger.info(f"   use_karras_sigmas: {config.use_karras_sigmas}")
        if hasattr(config, 'prediction_type'):
            logger.info(f"   prediction_type: {config.prediction_type}")
    
    def switch_model(self, model_key: str) -> bool:
        """Switch to a different model (config only, no loading)"""
        # Check if we're already using this model
        if self.current_model_key == model_key and hasattr(self, 'pipeline') and self.pipeline is not None:
            logger.debug(f"Model {model_key} already loaded, skipping reload")
            return True

        if self.config.set_model(model_key):
            self.active_model_config = self.config.get_current_config()
            self.current_model_key = model_key

            # Clear GPU cache when switching models to free memory
            if self.device.type == "cuda":
                if hasattr(self, 'pipeline') and self.pipeline is not None:
                    # Delete the old pipeline to free memory
                    del self.pipeline
                    self.pipeline = None

                # Clear CUDA cache
                torch.cuda.empty_cache()
                free_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) - torch.cuda.memory_reserved(0) / (1024**3)
                logger.info(f"Cleared GPU cache (free VRAM: {free_vram_gb:.1f} GB)")

            # Don't load the model yet - wait for actual generation
            return True
        return False
    
    def _compress_prompt(self, prompt: str, max_chars: int = 400) -> str:
        """
        Compress a long prompt to fit within token limits.
        """
        # Check if prompt is already short enough
        if len(prompt) <= max_chars:
            return prompt
        
        logger.info(f"Compressing prompt from {len(prompt)} chars")
        
        # Use simple truncation method
        return self._truncate_prompt(prompt)
    
    def _truncate_prompt(self, prompt: str, max_tokens: int = 75) -> str:
        """
        Intelligently truncate prompt to fit within token limit.
        Preserves the most important descriptive elements.
        """
        # CLIP has a hard limit of 77 tokens, we use 70 to be very safe
        max_tokens = 70
        
        # More conservative estimate (roughly 1.5 tokens per word to be safe)
        words = prompt.split()
        max_words = int(max_tokens / 1.5)
        
        if len(words) <= max_words:
            return prompt
        
        # Smart truncation - try to preserve key elements
        # Priority: style descriptors, main subject, setting
        important_keywords = ['style', 'detailed', 'fantasy', 'd&d', 'medieval', 'epic', 
                            'dramatic', 'cinematic', 'art', 'painting', 'digital']
        
        # Extract important parts
        important_words = []
        other_words = []
        
        for word in words:
            if any(keyword in word.lower() for keyword in important_keywords):
                important_words.append(word)
            else:
                other_words.append(word)
        
        # Build truncated prompt preserving important words
        if len(important_words) < max_words:
            # Add other words until we hit the limit
            remaining = max_words - len(important_words) - 1
            truncated_parts = important_words + other_words[:remaining]
            truncated = ' '.join(truncated_parts) + '...'
        else:
            # Even important words exceed limit
            truncated = ' '.join(important_words[:max_words-1]) + '...'
        
        logger.warning(f"Prompt truncated from {len(words)} words to {max_words} words")
        logger.info(f"Original: {prompt[:100]}...")
        logger.info(f"Truncated: {truncated}")
        return truncated

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
        Generate an image using LOCAL HuggingFace models only.

        This service ONLY handles local models with pipeline_type "sdxl" or "sd".
        For cloud models (runware, gemini, etc.), use the appropriate service.

        Args:
            prompt: Text description of the image
            negative_prompt: What to avoid in the image (uses model default if None)
            width: Image width (uses model default if None)
            height: Image height (uses model default if None)
            num_inference_steps: Number of denoising steps (uses model default if None)
            guidance_scale: How closely to follow the prompt (uses model default if None)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            seed: Random seed for reproducibility
            size: Size as string like "1024x1024" (overrides width/height)
            model: Specific model to use (if None, uses current model)
            **kwargs: Additional provider-specific parameters (ignored)

        Returns:
            Dict containing image generation results
        """
        # Refresh active model config in case it was updated by ImageServiceManager
        self.active_model_config = self.config.get_current_config()
        self.current_model_key = self.config.current_model
        
        # Validate that we're handling a local model ONLY
        current_model_config = self.active_model_config
        if current_model_config.pipeline_type not in ["sdxl", "sd"]:
            error_msg = (
                f"FluxLocalImageService only handles LOCAL models (sdxl, sd), "
                f"got: {current_model_config.pipeline_type}. "
                f"Use ImageServiceManager for automatic routing to the correct provider."
            )
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "images": [],
                "provider": "flux_local"
            }

        # Load model if not already loaded
        if not hasattr(self, 'pipeline') or self.pipeline is None:
            logger.info(f"Loading model {self.current_model_key} for image generation...")
            self._init_model()
            if not hasattr(self, 'pipeline') or self.pipeline is None:
                return {
                    "error": "Failed to load model. Check logs for details.",
                    "images": []
                }
        
        try:
            # Get current model config
            model_config = self.active_model_config
            
            # Use model defaults if not specified
            if negative_prompt is None:
                negative_prompt = model_config.negative_prompt
            
            # Handle size parameter
            if size:
                width, height = self.config.parse_size_string(size)
            # Note: width/height will be None if not provided - let the model use its defaults
            
            # Use model-specific defaults
            if num_inference_steps is None:
                num_inference_steps = model_config.steps
            if guidance_scale is None:
                guidance_scale = model_config.guidance_scale
            
            logger.info(f"Generating image with {model_config.name}")
            logger.info(f"Prompt: {prompt[:100]}...")
            logger.info(f"Size: {width}x{height}, Steps: {num_inference_steps}, Guidance: {guidance_scale}")
            logger.info(f"Response format: {response_format}")
            
            # Parse size if provided as string
            if isinstance(width, str) and 'x' in width:
                width, height = map(int, width.split('x'))
            
            # Set random seed if provided
            if seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)
            else:
                generator = None
            
            # Generate images - use batch generation if possible
            images = []
            start_time = time.time()
            
            # Check if we can do batch generation (more efficient)
            batch_size = min(n, 4)  # Limit batch size based on typical GPU memory
            if self.device.type == "cuda":
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram_gb >= 12:
                    batch_size = min(n, 4)
                elif vram_gb >= 8:
                    batch_size = min(n, 2)
                else:
                    batch_size = 1
            
            logger.info(f"Using batch size: {batch_size} for {n} images")
            
            # Generate in batches
            num_batches = (n + batch_size - 1) // batch_size
            
            for batch_idx in range(num_batches):
                current_batch_size = min(batch_size, n - batch_idx * batch_size)
                logger.info(f"Generating batch {batch_idx+1}/{num_batches} ({current_batch_size} images)...")
                
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.pipeline(
                        prompt=prompt,
                        negative_prompt=negative_prompt,
                        width=width,
                        height=height,
                        num_inference_steps=num_inference_steps,
                        guidance_scale=guidance_scale,
                        generator=generator,
                        num_images_per_prompt=current_batch_size
                    )
                )
                
                batch_time = time.time() - start_time
                logger.info(f"Batch generated in {batch_time:.2f} seconds")
                
                # Process all images in the batch
                for img_idx, pil_image in enumerate(result.images):
                    if response_format == "b64_json":
                        # Convert to base64
                        buffered = io.BytesIO()
                        pil_image.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        
                        images.append({
                            "b64_json": img_base64,
                            "seed": seed,
                            "generation_time": batch_time / current_batch_size  # Per-image time
                        })
                    else:
                        # Save to file and return path (global images path)
                        output_dir = kwargs.get('output_dir') or os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images')
                        output_dir = os.path.expanduser(output_dir)
                        Path(output_dir).mkdir(parents=True, exist_ok=True)
                        
                        total_img_idx = batch_idx * batch_size + img_idx
                        filename = f"flux_image_{int(time.time() * 1000)}_{total_img_idx}.png"
                        filepath = Path(output_dir) / filename
                        pil_image.save(filepath, format="PNG")
                        
                        image_dict = {
                            "url": f"file://{filepath}",
                            "path": str(filepath),
                            "seed": seed,
                            "generation_time": batch_time / current_batch_size  # Per-image time
                        }
                        images.append(image_dict)
                        logger.info(f"Saved Flux image to: {filepath}")
                        
                    # Stop if we have enough images
                    if len(images) >= n:
                        break
            
            logger.info(f"✅ Successfully generated {len(images)} images")
            return {
                "success": True,
                "images": images,
                "provider": "flux_local",
                "model": model_config.name,
                "prompt": prompt,
                "device": str(self.device)
            }
            
        except Exception as e:
            logger.error(f"Error in Flux image generation: {e}")
            return {
                "success": False,
                "error": str(e),
                "images": [],
                "provider": "flux_local"
            }

    def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this local image provider."""
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

        Supports LOCAL models with pipeline types: sdxl, sd

        Args:
            model: Model identifier (pipeline_type, model name, etc.)

        Returns:
            True if this is a local model we can handle
        """
        model_lower = model.lower()
        # Check if it's a supported pipeline type
        if model_lower in ["sdxl", "sd"]:
            return True
        # Check if it's in our provider's models
        if model in self.models:
            return True
        return False

    def is_available(self) -> bool:
        """
        Check if this provider is available and ready to use.

        For local models, we check if:
        1. We have at least one model defined
        2. GPU is available (required)

        Returns:
            True if provider can generate images
        """
        # Check if we have ANY local models defined
        if not self.models or len(self.models) == 0:
            return False

        # GPU is required for local models
        return torch.cuda.is_available()

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        model_config = self.active_model_config
        is_loaded = hasattr(self, 'pipeline') and self.pipeline is not None
        return {
            "provider": "flux_local",
            "model": model_config.name,
            "model_key": self.config.current_model,
            "available": self.is_available(),
            "loaded": is_loaded,
            "device": str(self.device) if self.device else "not initialized",
            "cuda_available": torch.cuda.is_available(),
            "gpu_name": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
            "huggingface_repo": model_config.huggingface_repo,
            "default_steps": model_config.steps,
            "default_guidance": model_config.guidance_scale,
            "checkpoint_name": model_config.checkpoint_name,
            "pipeline_type": model_config.pipeline_type,
            "supports_negative_prompt": model_config.supports_negative_prompt
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
            filename = f"flux_image_{int(time.time() * 1000)}.png"
            filepath = Path(output_dir) / filename
            
            # Save image
            image.save(filepath, format='PNG')
            
            logger.info(f"Saved image to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving base64 image: {e}")
            return None


# Singleton instance
_flux_service = None

def get_flux_local_image_service() -> Optional[FluxLocalImageService]:
    """
    Get the singleton Flux local image service instance.

    DEPRECATED: Always returns None. Local image generation is no longer supported.
    Use remote image generation services (Runware, Gemini) instead.
    """
    return None
