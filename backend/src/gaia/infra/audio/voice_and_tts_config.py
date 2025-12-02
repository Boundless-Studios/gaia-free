"""Centralized configuration for voice and TTS settings.

All configuration values are defined here as code constants.
Only API keys use environment variables for security.
All voice profiles are managed in voice_registry.py.
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    """Parse truthy strings from environment variables."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


# ==============================================================================
# CLIENT AUDIO CONFIGURATION
# ==============================================================================

GAIA_AUDIO_DISABLED = False
CLIENT_AUDIO_ENABLED = not GAIA_AUDIO_DISABLED
STREAMING_DEBUG_TTS_ENABLED = _as_bool(os.getenv("STREAMING_DEBUG_TTS_ENABLED"), True)
CLIENT_AUDIO_BUCKET = os.getenv("CLIENT_AUDIO_BUCKET") or os.getenv("CAMPAIGN_MEDIA_BUCKET", "")
CLIENT_AUDIO_BASE_PATH = os.getenv("CLIENT_AUDIO_BASE_PATH", "media/audio")
CLIENT_AUDIO_URL_TTL_SECONDS = int(os.getenv("CLIENT_AUDIO_URL_TTL_SECONDS", "900"))
AUTO_TTS_ENABLED = _as_bool(os.getenv("AUTO_TTS_ENABLED"), False)
# ==============================================================================
# CHUNKING CONFIGURATION
# ==============================================================================

# Target chunk size in characters
CHUNK_SIZE = 100

# Maximum chunk size in characters
MAX_CHUNK_SIZE = 200

# Maximum sentences per chunk
MAX_SENTENCES_PER_CHUNK = 5

# ==============================================================================
# AUDIO PLAYBACK CONFIGURATION
# ==============================================================================

# Delay between audio chunks in seconds
AUDIO_CHUNK_DELAY = 0.1

# Delay between paragraphs in seconds
PARAGRAPH_BREAK_DELAY = 1.5

# Seamless playback mode (concatenate chunks before playing)
AUTO_TTS_SEAMLESS = True

# ==============================================================================
# VOICE DETECTION CONFIGURATION (Moved to STT service)
# ==============================================================================
# All voice detection configuration has been moved to the standalone STT service

# ==============================================================================
# TTS CONFIGURATION
# ==============================================================================

# Auto-TTS settings
# Auto-detect environment and set appropriate audio output method
def get_auto_tts_output():
    """Auto-detect the appropriate TTS output method based on environment."""
    # Check if we are in Docker
    if os.path.exists("/.dockerenv"):
        # In Docker, use unix audio (PulseAudio)
        return "unix"
    
    # Check if we are in WSL
    if os.path.exists("/proc/version") and "microsoft" in open("/proc/version").read().lower():
        # In WSL, use Windows audio routing
        return "windows"
    
    # Default to auto-detection
    return os.getenv("AUTO_TTS_OUTPUT", "auto")


AUTO_TTS_VOICE = "nathaniel"  # Default to ElevenLabs DM/Narrator voice
AUTO_TTS_SPEED = 1.0
AUTO_TTS_OUTPUT = get_auto_tts_output()  # auto/unix/windows/windows_legacy

# Windows audio routing method
# "windows_utils" = Use dedicated windows_audio_utils.py (old working method with file copying)
# "windows_direct" = Use generic audio_utils.py Windows method (new method with WSL network paths)
WINDOWS_AUDIO_ROUTING = "windows_utils"  # windows_utils/windows_direct

# ==============================================================================
# AUDIO PATHS
# ==============================================================================

logger = logging.getLogger(__name__)


def _ensure_writable_directory(path: Path) -> Path:
    """Create the directory if needed and verify it is writable."""
    path.mkdir(parents=True, exist_ok=True)
    test_file = path / ".write_test"
    try:
        with test_file.open("w", encoding="utf-8") as handle:
            handle.write("ok")
    finally:
        test_file.unlink(missing_ok=True)
    return path


def _resolve_tts_temp_root() -> Path:
    """Choose a writable temp root for audio artifacts."""
    configured_base = Path(os.getenv("TTS_TEMP_PATH", "/tmp")).expanduser()
    configured_target = (
        configured_base if configured_base.name == "gaia_auto_tts" else configured_base / "gaia_auto_tts"
    )
    base_candidates = [
        configured_base,
        Path.home() / ".cache",
        Path(tempfile.gettempdir()),
    ]

    last_error: Optional[Exception] = None
    for base in base_candidates:
        candidate = base if base.name == "gaia_auto_tts" else base / "gaia_auto_tts"
        try:
            _ensure_writable_directory(candidate)
            if candidate != configured_target and configured_target.exists():
                logger.warning(
                    "Configured TTS temp path %s not writable; using %s instead",
                    configured_target,
                    candidate,
                )
            return candidate
        except Exception as exc:  # pragma: no cover - runtime environment guard
            last_error = exc
            logger.warning("Unable to use %s for TTS temp storage: %s", candidate, exc)

    # If all candidates fail, surface the most recent error for visibility
    raise RuntimeError(f"Could not initialize TTS temp directory: {last_error}")


TTS_TEMP_ROOT = _resolve_tts_temp_root()
AUDIO_TEMP_DIR = str(TTS_TEMP_ROOT)
TRANSCRIPTION_SESSIONS_DIR = str(TTS_TEMP_ROOT.parent / "gaia_transcription_sessions")
TEST_AUDIO_DIR = str(TTS_TEMP_ROOT.parent / "test_audio")
DEFAULT_CLIENT_AUDIO_LOCAL_ROOT = str(TTS_TEMP_ROOT / "client_audio")
CLIENT_AUDIO_LOCAL_ROOT = os.getenv("CLIENT_AUDIO_LOCAL_ROOT", DEFAULT_CLIENT_AUDIO_LOCAL_ROOT)

# Windows temp path for WSL audio passthrough
WINDOWS_TEMP_AUDIO_PATH = "C:\\Windows\\Temp\\gaia_narration.wav"

# ==============================================================================
# WEBSOCKET CONFIGURATION
# ==============================================================================

# STT buffer settings moved to standalone STT service

# ==============================================================================
# API KEYS - Set these directly in code
# ==============================================================================

# Note: For security, these should be loaded from environment variables
# in production. For development, you can set them here temporarily.

# TTS provider keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Speech-to-Text Configuration moved to standalone STT service

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_chunking_config() -> Dict[str, Any]:
    """Get all chunking configuration as a dictionary."""
    return {
        "chunk_size": CHUNK_SIZE,
        "max_chunk_size": MAX_CHUNK_SIZE,
        "max_sentences_per_chunk": MAX_SENTENCES_PER_CHUNK,
    }

def get_playback_config() -> Dict[str, Any]:
    """Get all playback configuration as a dictionary."""
    return {
        "chunk_delay": AUDIO_CHUNK_DELAY,
        "paragraph_delay": PARAGRAPH_BREAK_DELAY,
        "seamless": AUTO_TTS_SEAMLESS,
    }

def get_voice_detection_config() -> Dict[str, Any]:
    """Voice detection configuration moved to STT service."""
    return {"status": "Moved to standalone STT service"}

def get_tts_config() -> Dict[str, Any]:
    """Get all TTS configuration as a dictionary."""
    return {
        "enabled": AUTO_TTS_ENABLED,
        "voice": AUTO_TTS_VOICE,
        "speed": AUTO_TTS_SPEED,
        "output": AUTO_TTS_OUTPUT,
        "windows_routing": WINDOWS_AUDIO_ROUTING,
        "openai_key": OPENAI_API_KEY,
        "elevenlabs_key": ELEVENLABS_API_KEY,
    }


def get_client_audio_config() -> Dict[str, Any]:
    """Get configuration for client-side audio artifacts."""
    return {
        "enabled": CLIENT_AUDIO_ENABLED,
        "bucket": CLIENT_AUDIO_BUCKET,
        "base_path": CLIENT_AUDIO_BASE_PATH,
        "local_root": CLIENT_AUDIO_LOCAL_ROOT,
        "url_ttl_seconds": CLIENT_AUDIO_URL_TTL_SECONDS,
    }

def get_stt_config() -> Dict[str, Any]:
    """STT configuration moved to STT service."""
    return {"status": "Moved to standalone STT service"}

def get_all_config() -> Dict[str, Any]:
    """Get all audio configuration as a single dictionary."""
    return {
        "chunking": get_chunking_config(),
        "playback": get_playback_config(),
        "voice_detection": get_voice_detection_config(),
        "tts": get_tts_config(),
        "client_audio": get_client_audio_config(),
        "stt": get_stt_config(),
        "paths": {
            "audio_temp": AUDIO_TEMP_DIR,
            "transcription_sessions": TRANSCRIPTION_SESSIONS_DIR,
            "test_audio": TEST_AUDIO_DIR,
            "windows_temp": WINDOWS_TEMP_AUDIO_PATH,
        },
        "websocket": {"status": "Moved to standalone STT service"},
    }
