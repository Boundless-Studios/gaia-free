"""F5-TTS Configuration

This module contains all F5-TTS related configuration including speaker definitions,
server settings, and voice mappings. This replaces the speakers_config.toml file.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import os

# ==============================================================================
# F5-TTS SERVER CONFIGURATION
# ==============================================================================

# Gradio server URL and port
# Updated to point to external TTS service
GRADIO_URL = os.getenv("TTS_SERVICE_URL", "http://tts-service:7860")

# F5-TTS model settings
F5_TTS_SETTINGS = {
    "output_dir": "generated_audio",
    "sample_rate": 24000,
    "model_name": "F5-TTS",
    "device": "auto",  # auto, cpu, cuda
    "speed": 1.0,
    "remove_silence": True,
    "gradio_url": GRADIO_URL,
}

# ==============================================================================
# AUDIO PATHS
# ==============================================================================

# Get the base directory for audio files
# In Docker: /home/gaia/audio_samples
# In local: ./audio_samples (relative to backend directory)
def get_audio_base_path() -> Path:
    """Get the base path for audio files."""
    # Check if we're in Docker (audio_samples mounted at /home/gaia/audio_samples)
    docker_path = Path("/home/gaia/audio_samples")
    if docker_path.exists():
        return docker_path
    
    # Check if we're in the backend directory
    backend_audio_path = Path("audio_samples")
    if backend_audio_path.exists():
        return backend_audio_path
    
    # Fallback: try to find audio_samples relative to current directory
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        audio_path = parent / "audio_samples"
        if audio_path.exists():
            return audio_path
    
    # Last resort: use current directory
    return Path("audio_samples")

AUDIO_BASE_PATH = get_audio_base_path()

# ==============================================================================
# SPEAKER DEFINITIONS
# ==============================================================================

@dataclass
class SpeakerConfig:
    """Configuration for a single speaker/voice."""
    name: str
    description: str
    reference_audio: str
    reference_text: str
    style: str
    gender: str

# Define all available speakers with absolute paths
SPEAKERS = {
    "dm": SpeakerConfig(
        name="DM Narrator",
        description="Calm and authoritative dungeon master voice",
        reference_audio=str(AUDIO_BASE_PATH / "dm-narrator-nathaniel-calm.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="narrator",
        gender="male"
    ),
    "adventurer": SpeakerConfig(
        name="Adventurer",
        description="Gentle and soft adventurer voice",
        reference_audio=str(AUDIO_BASE_PATH / "adventurer-jen-soft.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="friendly",
        gender="female"
    ),
    "innkeeper": SpeakerConfig(
        name="Innkeeper",
        description="Warm and welcoming innkeeper voice",
        reference_audio=str(AUDIO_BASE_PATH / "innkeeper-priyanka-warm.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="warm",
        gender="female"
    ),
    "merchant": SpeakerConfig(
        name="Merchant",
        description="Clear and articulate merchant voice",
        reference_audio=str(AUDIO_BASE_PATH / "merchant-alice-clear.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="professional",
        gender="female"
    ),
    "sage": SpeakerConfig(
        name="Wise Sage",
        description="Wise and moderate sage voice",
        reference_audio=str(AUDIO_BASE_PATH / "wise-sage-moderate.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="wise",
        gender="neutral"
    ),
    "mysterious": SpeakerConfig(
        name="Mysterious Figure",
        description="Mysterious and whispering voice",
        reference_audio=str(AUDIO_BASE_PATH / "mysterious-almee-whisper.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="mysterious",
        gender="female"
    ),
    "warrior": SpeakerConfig(
        name="Warrior",
        description="Confident and strong warrior voice",
        reference_audio=str(AUDIO_BASE_PATH / "warrior-caleb-confident.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="confident",
        gender="male"
    ),
    "noble": SpeakerConfig(
        name="Noble",
        description="Distinguished and authoritative noble voice",
        reference_audio=str(AUDIO_BASE_PATH / "noble-cornelius-distinguished.mp3"),
        reference_text="The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic.",
        style="authoritative",
        gender="male"
    ),
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_gradio_url() -> str:
    """Get the Gradio server URL."""
    return GRADIO_URL

def get_speaker_config(speaker_id: str) -> Optional[SpeakerConfig]:
    """Get configuration for a specific speaker."""
    return SPEAKERS.get(speaker_id)

def get_all_speakers() -> Dict[str, SpeakerConfig]:
    """Get all speaker configurations."""
    return SPEAKERS.copy()

def get_speaker_names() -> Dict[str, str]:
    """Get a mapping of speaker IDs to display names."""
    return {speaker_id: speaker.name for speaker_id, speaker in SPEAKERS.items()}

def get_f5_tts_settings() -> Dict[str, Any]:
    """Get all F5-TTS settings."""
    return F5_TTS_SETTINGS.copy()

def validate_audio_files() -> Dict[str, bool]:
    """Validate that all reference audio files exist."""
    results = {}
    for speaker_id, speaker in SPEAKERS.items():
        audio_path = Path(speaker.reference_audio)
        results[speaker_id] = audio_path.exists()
    return results

def get_config_as_dict() -> Dict[str, Any]:
    """Get the entire configuration as a dictionary (for backward compatibility)."""
    config = {
        "settings": F5_TTS_SETTINGS.copy(),
        "speakers": {}
    }
    
    for speaker_id, speaker in SPEAKERS.items():
        config["speakers"][speaker_id] = {
            "name": speaker.name,
            "description": speaker.description,
            "reference_audio": speaker.reference_audio,
            "reference_text": speaker.reference_text,
            "style": speaker.style,
            "gender": speaker.gender,
        }
    
    return config

def log_audio_paths():
    """Log the audio paths for debugging."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Audio base path: {AUDIO_BASE_PATH}")
    logger.info(f"Audio base path exists: {AUDIO_BASE_PATH.exists()}")
    
    for speaker_id, speaker in SPEAKERS.items():
        audio_path = Path(speaker.reference_audio)
        logger.info(f"Speaker {speaker_id}: {audio_path} (exists: {audio_path.exists()})")
