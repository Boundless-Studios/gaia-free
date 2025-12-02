"""Sound Effects service using ElevenLabs Sound Effects API."""

import logging
import io
from typing import Optional
from dataclasses import dataclass

from gaia.infra.audio.voice_and_tts_config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)


@dataclass
class SoundEffectResult:
    """Container for generated sound effect audio."""

    audio_bytes: bytes
    duration_seconds: Optional[float] = None
    prompt: str = ""


class SFXService:
    """Sound Effects service using ElevenLabs text-to-sound-effects API."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.elevenlabs_client = None
        self.elevenlabs_available = False
        self._init_elevenlabs()

    def _init_elevenlabs(self):
        """Initialize ElevenLabs client for sound effects."""
        try:
            from elevenlabs.client import ElevenLabs

            if ELEVENLABS_API_KEY:
                self.elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
                self.elevenlabs_available = True
                logger.info("ElevenLabs SFX client initialized")
            else:
                logger.info("ElevenLabs API key not found for SFX service")
        except ImportError as e:
            logger.warning(f"ElevenLabs not available for SFX: {e}")
            self.elevenlabs_available = False
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs SFX client: {e}")
            self.elevenlabs_available = False

    async def generate_sound_effect(
        self,
        text: str,
        duration_seconds: Optional[float] = None,
        prompt_influence: float = 0.3,
    ) -> SoundEffectResult:
        """Generate a sound effect from a text description.

        Args:
            text: Description of the sound effect to generate (e.g., "dragon roar",
                  "thunder crack", "sword clash")
            duration_seconds: Optional duration in seconds (0.5-22). If None, the API
                              will determine optimal duration.
            prompt_influence: How closely to follow the prompt (0-1, default 0.3).
                              Higher values make generation follow prompt more closely.

        Returns:
            SoundEffectResult with audio bytes and metadata

        Raises:
            RuntimeError: If ElevenLabs is not available
            ValueError: If parameters are invalid
        """
        if not self.elevenlabs_available or not self.elevenlabs_client:
            raise RuntimeError(
                "ElevenLabs Sound Effects not available. "
                "Please configure ELEVENLABS_API_KEY."
            )

        # Validate duration if provided
        if duration_seconds is not None:
            if duration_seconds < 0.5 or duration_seconds > 22:
                raise ValueError("duration_seconds must be between 0.5 and 22")

        # Validate prompt_influence
        if prompt_influence < 0 or prompt_influence > 1:
            raise ValueError("prompt_influence must be between 0 and 1")

        logger.info(
            f"Generating sound effect: text='{text[:50]}...' duration={duration_seconds} "
            f"prompt_influence={prompt_influence}"
        )

        try:
            # Call ElevenLabs text-to-sound-effects API
            # The API returns an iterator of audio bytes
            audio_generator = self.elevenlabs_client.text_to_sound_effects.convert(
                text=text,
                duration_seconds=duration_seconds,
                prompt_influence=prompt_influence,
            )

            # Collect all audio bytes from the generator
            audio_buffer = io.BytesIO()
            for chunk in audio_generator:
                audio_buffer.write(chunk)

            audio_bytes = audio_buffer.getvalue()

            logger.info(
                f"Sound effect generated successfully: {len(audio_bytes)} bytes"
            )

            return SoundEffectResult(
                audio_bytes=audio_bytes,
                duration_seconds=duration_seconds,
                prompt=text,
            )

        except Exception as e:
            logger.error(f"Failed to generate sound effect: {e}")
            raise RuntimeError(f"Sound effect generation failed: {e}") from e

    def is_available(self) -> bool:
        """Check if the SFX service is available."""
        return self.elevenlabs_available


# Singleton instance
sfx_service = SFXService()
