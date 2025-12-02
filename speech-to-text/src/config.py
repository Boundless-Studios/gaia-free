"""Configuration management for the STT service"""

import os
from typing import Optional
from pydantic import BaseModel
from pydantic import Field
import logging

logger = logging.getLogger(__name__)


class Settings(BaseModel):
    """Application settings"""
    
    # Service configuration
    service_name: str = "Speech-to-Text Service"
    service_version: str = "1.0.0"
    service_host: str = "0.0.0.0"
    service_port: int = 8001
    
    # API Keys
    elevenlabs_api_key: Optional[str] = None
    
    # Voice detection settings (must match backend exactly)
    voice_activity_duration_ms: int = 1000  # How long voice is considered active
    silence_threshold_ms: int = 2000  # Silence duration to end segment
    max_buffer_chunks: int = 750  # 5 minutes of audio buffering

    # Conversational mode settings
    enable_conversational_mode: bool = True  # Enable automatic turn-based conversation
    conversational_silence_threshold_ms: int = 2000  # Silence threshold for natural pauses
    max_conversation_turn_duration_ms: int = 30000  # Max duration of single conversation turn (30s)
    
    # Audio settings
    default_sample_rate: int = 48000
    chunk_size: int = 16384  # 16KB chunks for processing
    
    # Storage
    recording_storage_path: str = Field(default="/tmp/gaia_stt/transcriptions")
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = "STT_"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Override with environment variables if present
        self.elevenlabs_api_key = os.environ.get(
            'ELEVENLABS_API_KEY',
            self.elevenlabs_api_key
        )
        
        # Use AUDIO_STORAGE_PATH if set
        audio_storage = os.environ.get('AUDIO_STORAGE_PATH')
        if audio_storage:
            self.recording_storage_path = os.path.join(audio_storage, 'transcriptions')
        
        # Ensure storage directory exists
        os.makedirs(self.recording_storage_path, exist_ok=True)
        
        # Configure logging
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=self.log_file if self.log_file else None
        )
        
        # Log configuration
        logger.info(f"Initialized {self.service_name} v{self.service_version}")
        logger.info(f"Service will run on {self.service_host}:{self.service_port}")
        if self.elevenlabs_api_key:
            logger.info("ElevenLabs API key configured")
        else:
            logger.warning("ElevenLabs API key not configured - STT functionality limited")


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings