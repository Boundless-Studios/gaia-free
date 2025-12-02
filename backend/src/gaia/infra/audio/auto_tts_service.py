"""Auto-TTS service for automatic DM narration audio generation."""

import logging
import time
from collections import Counter
from typing import Optional, Callable, Dict, Any
from gaia.infra.audio.tts_service import tts_service
from gaia.infra.audio.voice_registry import VoiceRegistry, VoiceProvider
from gaia.infra.audio.provider_manager import provider_manager
from gaia.infra.audio.chunking_manager import chunking_manager
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter
from gaia.utils.audio_utils import play_audio_unix, play_audio_windows, play_audio_auto
from gaia.infra.audio.voice_and_tts_config import (
    get_tts_config,
    get_playback_config,
    get_chunking_config,
    get_client_audio_config,
)

logger = logging.getLogger(__name__)

class AutoTTSService:
    """Service for automatically generating TTS for DM responses using Local TTS by default."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # Load configuration from centralized config
        tts_config = get_tts_config()
        playback_config = get_playback_config()
        client_audio_config = get_client_audio_config()

        self.enabled = tts_config['enabled']
        self.speed = tts_config['speed']
        self.output_method = tts_config['output']
        self.seamless_mode = playback_config['seamless']
        self.client_audio_enabled = bool(client_audio_config.get('enabled', False))
        self.client_audio_bucket = client_audio_config.get('bucket')
        self.metrics: Counter[str] = Counter()

        # Use centralized voice configuration with LOCAL DM/Narrator as default
        configured_voice = tts_config['voice']
        if configured_voice and VoiceRegistry.get_voice(configured_voice):
            self.default_voice = configured_voice
            logger.info(f"Using configured voice: {configured_voice}")
        else:
            # Fallback to LOCAL DM/Narrator voice
            logger.warning(f"Configured voice '{configured_voice}' not available, using LOCAL DM/Narrator fallback")
            default_voice = VoiceRegistry.get_default_voice(VoiceProvider.LOCAL)
            if default_voice:
                self.default_voice = default_voice
                logger.info(f"Auto-TTS using LOCAL provider with DM/Narrator voice: {default_voice}")
            else:
                logger.error("No LOCAL DM/Narrator voice found! Check voice registry configuration.")
                self.default_voice = "dm"  # Hard fallback
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of AutoTTSService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def generate_audio(self, text: str, session_id: str = "default", return_artifact: bool = True, *, force: bool = False):
        """
        Generate and play audio for the given text using ElevenLabs chunked TTS.
        """
        if not (self.enabled or force):
            logger.info("Auto-TTS is disabled.")
            return None
        if not text or not text.strip():
            logger.info("No text provided for audio generation.")
            return None
        logger.debug(f"[AutoTTS] Generating and playing audio for {len(text)} characters using {self.default_voice}...")
        self.metrics["tts_requests_total"] += 1
        start_time = time.perf_counter()
        try:
            # Hybrid chunking parameter approach - centralized config with provider fallbacks
            chunking_params = self._get_chunking_params()
            persist_artifact = self.client_audio_enabled and return_artifact
            should_play_locally = not persist_artifact

            synthesis = await tts_service.synthesize_speech(
                text=text,
                voice=self.default_voice,
                speed=self.speed,
                chunked=True,
                play=should_play_locally,
                chunking_params=chunking_params,
                persist=persist_artifact,
                session_id=session_id,
            )
            elapsed = time.perf_counter() - start_time
            if persist_artifact:
                if synthesis.artifact:
                    payload = synthesis.artifact.to_payload()
                    payload["provider"] = synthesis.method
                    logger.debug(
                        "Client audio artifact ready in %.2fs (provider=%s, bytes=%s)",
                        elapsed,
                        synthesis.method,
                        len(synthesis.audio_bytes),
                    )
                    return payload
                logger.warning("Client audio requested but no artifact returned")
                return {
                    "success": False,
                    "error": "audio_artifact_unavailable",
                    "provider": synthesis.method,
                }
            logger.debug(
                "Auto-TTS playback finished in %.2fs (provider=%s, bytes=%s)",
                elapsed,
                synthesis.method,
                len(synthesis.audio_bytes),
            )
            return bool(synthesis.audio_bytes)
        except Exception as e:
            logger.error(f"Auto-TTS failed to generate audio: {e}")
            self.metrics["tts_failures_total"] += 1
            return None

    async def generate_audio_progressive(
        self,
        text: str,
        session_id: str,
        on_chunk_ready: Optional[Callable[[Dict], Any]] = None,
        *,
        force: bool = False,
        playback_writer: Optional[PlaybackRequestWriter] = None,
    ):
        """
        Generate audio progressively, persisting and broadcasting each chunk as it's ready.
        Used for client-side audio playback with streaming delivery.

        Args:
            text: Text to synthesize
            session_id: Campaign session identifier
            on_chunk_ready: Callback invoked when each chunk is persisted (receives artifact dict)
            playback_writer: Shared playback writer for DB persistence/broadcasting

        Returns:
            Summary dict with total chunks and generation time
        """
        if not (self.enabled or force) or not self.client_audio_enabled:
            logger.info("Auto-TTS or client audio is disabled.")
            return None
        if not text or not text.strip():
            logger.info("No text provided for audio generation.")
            return None

        logger.debug(
            f"[AutoTTS] Generating progressive audio for {len(text)} chars (session={session_id})"
        )
        self.metrics["tts_requests_total"] += 1
        start_time = time.perf_counter()

        try:
            chunking_params = self._get_chunking_params()

            # Determine provider for the current default voice
            voice_info = VoiceRegistry.get_voice(self.default_voice)
            provider = voice_info.provider if voice_info else None

            # Guard: only attempt progressive for supported and available providers
            progressive_supported = False
            if provider == VoiceProvider.ELEVENLABS and tts_service.is_provider_available(VoiceProvider.ELEVENLABS):
                progressive_supported = True
            elif provider == VoiceProvider.LOCAL and tts_service.is_provider_available(VoiceProvider.LOCAL):
                # Local progressive supported only when local TTS is available
                progressive_supported = True

            if not progressive_supported:
                prov_name = provider.value if provider else "unknown"
                logger.info(
                    "Progressive TTS not supported/available for provider=%s. Skipping to fallback.",
                    prov_name,
                )
                return None

            # Use the progressive synthesis path (supported)
            synthesis = await tts_service.synthesize_speech_progressive(
                text=text,
                voice=self.default_voice,
                speed=self.speed,
                chunked=True,
                chunking_params=chunking_params,
                session_id=session_id,
                on_chunk_ready=on_chunk_ready,
                playback_writer=playback_writer,
            )

            elapsed = time.perf_counter() - start_time
            logger.debug(
                "Progressive audio generation completed in %.2fs (provider=%s, chunks=%d)",
                elapsed,
                synthesis.get("method", "unknown"),
                synthesis.get("total_chunks", 0),
            )
            return synthesis

        except Exception as e:
            logger.error(f"Progressive audio generation failed: {e}", exc_info=True)
            self.metrics["tts_failures_total"] += 1
            return None

    def _get_chunking_params(self) -> dict:
        """Get chunking parameters using hybrid approach - centralized config with provider fallbacks."""
        try:
            # Try centralized config first (Main approach)
            chunking_config = get_chunking_config()
            return {
                'target_chunk_size': chunking_config['chunk_size'],
                'max_chunk_size': chunking_config['max_chunk_size'],
                'sentences_per_chunk': chunking_config['max_sentences_per_chunk']
            }
        except Exception as e:
            logger.warning(f"Centralized chunking config failed: {e}, using provider-specific config")
            # Fallback to provider-specific config (HEAD approach)
            voice_info = VoiceRegistry.get_voice(self.default_voice)
            if voice_info:
                config = chunking_manager.get_chunking_config(voice_info.provider)
                logger.info(f"Using {voice_info.provider.value} chunking config for voice {self.default_voice}")
            else:
                # Final fallback to ElevenLabs parameters if voice not found
                config = chunking_manager.get_chunking_config(VoiceProvider.ELEVENLABS)
                logger.info(f"Voice {self.default_voice} not found, using ElevenLabs chunking config")
            
            return {
                'target_chunk_size': config.target_chunk_size,
                'max_chunk_size': config.max_chunk_size,
                'sentences_per_chunk': config.sentences_per_chunk
            }

    def set_voice(self, voice: str) -> None:
        # Validate voice exists in registry
        if VoiceRegistry.get_voice(voice):
            self.default_voice = voice
            logger.info(f"Auto-TTS voice changed to: {voice}")
        else:
            logger.warning(f"Voice '{voice}' not found in registry. Available voices: {[v.id for v in VoiceRegistry.list_voices()]}")
            # Keep current voice

    def set_provider(self, provider: VoiceProvider) -> None:
        """Set the TTS provider and select an appropriate default voice for that provider.

        Args:
            provider: The VoiceProvider to use (LOCAL, ELEVENLABS, OPENAI)
        """
        # Get the default voice for this provider
        default_voice = VoiceRegistry.get_default_voice(provider)

        if default_voice:
            self.default_voice = default_voice
            logger.info(f"Auto-TTS provider changed to {provider.value}, using voice: {default_voice}")
        else:
            # Fallback: find any voice from this provider
            voices = VoiceRegistry.list_voices(provider=provider)
            if voices:
                self.default_voice = voices[0].id
                logger.info(f"Auto-TTS provider changed to {provider.value}, using fallback voice: {voices[0].id}")
            else:
                logger.warning(f"No voices available for provider {provider.value}, keeping current voice: {self.default_voice}")

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.25, min(4.0, speed))
        logger.info(f"Auto-TTS speed changed to: {self.speed}")

    def toggle_enabled(self) -> bool:
        self.enabled = not self.enabled
        logger.info(f"Auto-TTS {'enabled' if self.enabled else 'disabled'}")
        return self.enabled

    def cleanup(self):
        """Clean up any temporary files or resources."""
        logger.info("Auto-TTS service cleanup completed")

    async def _play_audio_unix(self, audio_path: str) -> None:
        """Play audio using Unix audio system."""
        await play_audio_unix(audio_path)

    async def _play_audio_windows(self, audio_path: str) -> None:
        """Play audio using Windows audio system."""
        await play_audio_windows(audio_path)

    async def _play_audio_auto(self, audio_path: str) -> None:
        """Play audio using auto-detected audio system."""
        await play_audio_auto(audio_path)

# Global instance
auto_tts_service = AutoTTSService()
