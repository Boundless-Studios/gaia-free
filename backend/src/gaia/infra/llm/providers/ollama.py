"""
Ollama service manager for Genesis framework.

DEPRECATED: This module is deprecated as we've moved to remote generation.
Local Ollama installation is no longer required or used.
This module is kept for backward compatibility but all functionality is disabled.
"""

import subprocess
import time
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import warnings

logger = logging.getLogger(__name__)

# Emit deprecation warning when module is imported
warnings.warn(
    "ollama_manager is deprecated. The system now uses remote generation only. "
    "Local Ollama installation is no longer required.",
    DeprecationWarning,
    stacklevel=2
)

class OllamaManager:
    """Manages Ollama service and model availability."""
    
    def __init__(self):
        self.available_models: List[str] = []
        self.service_running = False
        self.service_pid: Optional[int] = None
        self._initialized = False
        self._selected_model: Optional[str] = None
        self._models_cache_valid = False
    
    def check_ollama_installed(self) -> bool:
        """Check if Ollama is installed."""
        try:
            result = subprocess.run(["ollama", "--version"], 
                                  capture_output=True, text=True, check=True)
            # logger.info(f"Ollama version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # logger.warning("Ollama not found or not accessible")
            return False
    
    def start_ollama_service(self) -> bool:
        """Start the Ollama service."""
        if self.service_running:
            # logger.info("Ollama service already running")
            return True
        
        try:
            # Check if service is already running
            result = subprocess.run(["ollama", "list"], 
                                  capture_output=True, text=True, check=True)
            # logger.info("Ollama service is already running")
            self.service_running = True
            return True
        except subprocess.CalledProcessError:
            # logger.info("Starting Ollama service...")
            
            # Try to start Ollama service
            try:
                # Start Ollama in background
                process = subprocess.Popen(["ollama", "serve"], 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE)
                self.service_pid = process.pid
                
                # Wait a moment for service to start
                time.sleep(3)
                
                # Verify service is running
                result = subprocess.run(["ollama", "list"], 
                                      capture_output=True, text=True, check=True)
                self.service_running = True
                # logger.info(f"Ollama service started successfully (PID: {self.service_pid})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start Ollama service: {e}")
                return False
    
    def stop_ollama_service(self) -> bool:
        """Stop the Ollama service."""
        if not self.service_running:
            # logger.info("Ollama service not running")
            return True
        
        try:
            if self.service_pid:
                # Try to terminate the process
                subprocess.run(["kill", str(self.service_pid)], 
                             capture_output=True, check=False)
                # logger.info(f"Terminated Ollama service (PID: {self.service_pid})")
            
            # Also try to stop via brew services if on macOS
            try:
                subprocess.run(["brew", "services", "stop", "ollama"], 
                             capture_output=True, check=False)
                # logger.info("Stopped Ollama via brew services")
            except FileNotFoundError:
                pass  # brew not available
            
            self.service_running = False
            self.service_pid = None
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop Ollama service: {e}")
            return False
    
    def get_available_models(self, force_refresh: bool = False) -> List[str]:
        """Get list of available Ollama models."""
        # Return cached models if available and not forcing refresh
        if not force_refresh and self._models_cache_valid and self.available_models:
            return self.available_models
        
        if not self.service_running:
            # logger.warning("Ollama service not running")
            return []
        
        try:
            result = subprocess.run(["ollama", "list"], 
                                  capture_output=True, text=True, check=True)
            
            models = []
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            
            self.available_models = models
            self._models_cache_valid = True
            
            return models
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific model."""
        if not self.service_running:
            return None
        
        try:
            result = subprocess.run(["ollama", "show", model_name], 
                                  capture_output=True, text=True, check=True)
            
            # Parse model info from output
            info = {}
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            
            return info
            
        except subprocess.CalledProcessError:
            return None
    
    def select_best_available_model(self, preferred_models: Optional[List[str]] = None, force_refresh: bool = False) -> Optional[str]:
        """Select the best available model based on preferences."""
        # Return cached selection if available and not forcing refresh
        if not force_refresh and self._selected_model and self._models_cache_valid:
            return self._selected_model
        
        available = self.get_available_models(force_refresh=force_refresh)
        
        if not available:
            # logger.warning("No Ollama models available")
            return None
        
        # For now, simply select the first available model
        # TODO: Implement more sophisticated model selection logic with:
        # - Model size preferences (smaller for speed, larger for quality)
        # - Model type preferences (coding, chat, instruction-tuned)
        # - Performance characteristics
        # - Fallback chains
        if "llama3.1:8b" in available:
            selected_model = "llama3.1:8b"
        else:
            selected_model = available[0]
        
        self._selected_model = selected_model
        return selected_model
    
    def download_model_if_needed(self, model_name: str) -> bool:
        """Download a model if it's not available."""
        available = self.get_available_models()
        
        if model_name in available:
            # logger.info(f"Model {model_name} already available")
            return True
        
        # logger.info(f"Downloading model: {model_name}")
        try:
            subprocess.run(["ollama", "pull", model_name], 
                         check=True, capture_output=True)
            # logger.info(f"Successfully downloaded model: {model_name}")
            # Invalidate cache since we added a new model
            self._models_cache_valid = False
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to download model {model_name}: {e}")
            return False
    
    def initialize(self) -> Optional[str]:
        """Initialize Ollama service and return the best available model."""
        # Return cached result if already initialized
        if self._initialized and self._selected_model:
            return self._selected_model
        
        # logger.info("Initializing Ollama manager...")
        
        # Check if Ollama is installed
        if not self.check_ollama_installed():
            logger.error("Ollama not installed")
            return None
        
        # Start Ollama service
        if not self.start_ollama_service():
            logger.error("Failed to start Ollama service")
            return None
        
        # Get available models (this will log once)
        available = self.get_available_models()
        if not available:
            # logger.warning("No models available")
            return None
        
        # Get detailed summary (only log once during initialization)
        summary = self.get_models_summary()
        # logger.info(f"Model summary: {summary['total_models']} models available")
        
        # Select best available model (this will log once)
        best_model = self.select_best_available_model()
        
        if best_model:
            # logger.info(f"Ollama initialized successfully with model: {best_model}")
            self._initialized = True
        else:
            logger.error("Failed to initialize Ollama - no models available")
        
        return best_model
    
    def get_models_summary(self) -> Dict[str, Any]:
        """Get a summary of all available models and their details."""
        available = self.get_available_models()
        summary = {
            "total_models": len(available),
            "models": []
        }
        
        for model in available:
            model_info = self.get_model_info(model)
            summary["models"].append({
                "name": model,
                "info": model_info
            })
        
        return summary
    
    def cleanup(self):
        """Cleanup resources."""
        # logger.info("Cleaning up Ollama manager...")
        self.stop_ollama_service()
        self._initialized = False
        self._models_cache_valid = False
        self._selected_model = None


# Global Ollama manager instance
ollama_manager = OllamaManager() 