"""Text-to-Speech service for Gaia."""

import asyncio
import os
import logging
import warnings
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import tempfile
import io
import time
import requests
import aiohttp
from openai import AsyncOpenAI

# Suppress known harmless warnings from TTS dependencies
warnings.filterwarnings("ignore", message=".*torchaudio.load_with_torchcodec.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Trying to convert audio automatically.*", category=UserWarning)
from gaia.utils.audio_utils import play_audio_unix, play_audio_screenshare
from gaia.infra.audio.voice_registry import VoiceRegistry, VoiceProvider
from gaia.infra.audio.provider_manager import provider_manager
from gaia.infra.audio.chunking_manager import chunking_manager
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter
from gaia.infra.audio.voice_and_tts_config import (
    get_chunking_config, get_playback_config, get_tts_config,
    AUDIO_TEMP_DIR, OPENAI_API_KEY, ELEVENLABS_API_KEY, AUTO_TTS_SEAMLESS
)

from gaia.infra.audio.audio_artifact_store import audio_artifact_store, AudioArtifact

from .f5_tts_config import get_gradio_url, get_speaker_config

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logger = logging.getLogger(__name__)

# Hard limit on text length for TTS requests to avoid accidental mega-requests to ElevenLabs
TTS_MAX_TEXT_LENGTH = 2000


@dataclass
class AudioSynthesisResult:
    """Container for synthesized audio and optional artifact metadata."""

    audio_bytes: bytes
    method: str
    artifact: Optional[AudioArtifact] = None


class TTSService:
    """Text-to-Speech service supporting multiple providers."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.openai_client = None
        self.local_tts_available = False
        self.elevenlabs_client = None
        self.elevenlabs_api_key: Optional[str] = None
        self.elevenlabs_available = False
        self.gradio_url = None
        self.temp_dir = Path(AUDIO_TEMP_DIR)
        self.temp_dir.mkdir(exist_ok=True)

        # Persistent Gradio client for connection reuse
        self._gradio_client = None
        self._gradio_client_lock = None
        
        # Load configuration from centralized config
        chunking_config = get_chunking_config()
        playback_config = get_playback_config()
        tts_config = get_tts_config()
        
        # Set up chunking configuration
        self.chunking_config = {
            'target_chunk_size': chunking_config['chunk_size'],
            'max_chunk_size': chunking_config['max_chunk_size'],
            'sentences_per_chunk': chunking_config['max_sentences_per_chunk'],
            'chunk_delay': playback_config['chunk_delay'],
            'seamless_mode': playback_config['seamless'],
            'default_speed': tts_config['speed']
        }
        
        # Initialize OpenAI client if API key is available
        if OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI TTS client initialized")
        else:
            logger.info("OpenAI API key not found, will use local TTS")
        
        # Initialize ElevenLabs client if API key is available
        self._check_elevenlabs()

        # F5-TTS DISABLED - No longer checking for local TTS
        # self._check_local_tts()

        # F5-TTS DISABLED - No longer need Gradio client lock
        # import asyncio
        # try:
        #     self._gradio_client_lock = asyncio.Lock()
        # except RuntimeError:
        #     # If no event loop is running, lock will be created when needed
        #     self._gradio_client_lock = None

    
    def _check_elevenlabs(self):
        """Check if ElevenLabs is available and initialize it."""
        try:
            # Try to import ElevenLabs - this will fail if the package is not installed
            import elevenlabs
            from elevenlabs.client import ElevenLabs
            # Get API key from centralized config
            tts_config = get_tts_config()
            elevenlabs_api_key = tts_config['elevenlabs_key']
            if elevenlabs_api_key:
                self.elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
                self.elevenlabs_available = True
                self.elevenlabs_api_key = elevenlabs_api_key
                logger.info("ElevenLabs TTS client initialized")
            else:
                logger.info("ElevenLabs API key not found")
                
        except ImportError as e:
            logger.warning(f"ElevenLabs not available: {e}")
            self.elevenlabs_available = False
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs: {e}")
            self.elevenlabs_available = False
    
    def _get_gradio_url_from_config(self) -> Optional[str]:
        """Get Gradio URL from Python configuration."""
        try:
            gradio_url = get_gradio_url()
            logger.info(f"Loaded Gradio URL from config: {gradio_url}")
            return gradio_url
        except Exception as e:
            logger.warning(f"Failed to get Gradio URL from config: {e}")
            return None
    
    def _check_local_tts(self):
        """Check if local F5-TTS Gradio server is available."""
        try:
            # Get Gradio URL from config file
            gradio_url = self._get_gradio_url_from_config()
            
            # If no URL found in config, use default
            if not gradio_url:
                gradio_url = "http://localhost:7860"
                logger.info("Using default Gradio URL: http://localhost:7860")
            
            # Try to connect to the local Gradio server
            response = requests.get(f"{gradio_url}/", timeout=5)
            if response.status_code == 200:
                self.local_tts_available = True
                self.gradio_url = gradio_url
                logger.info(f"✅ Local F5-TTS Gradio server detected and available at {gradio_url}")
            else:
                logger.warning(f"Local F5-TTS server not responding at {gradio_url}: {response.status_code}")
                self.local_tts_available = False
        except requests.exceptions.ConnectionError:
            # F5-TTS not available - this is expected
            self.local_tts_available = False
        except Exception as e:
            # F5-TTS not available - this is expected
            self.local_tts_available = False

    async def _get_gradio_client(self):
        """Get or create a persistent Gradio client for connection reuse."""
        import asyncio

        # Create lock if it doesn't exist (for cases where init happened outside event loop)
        if self._gradio_client_lock is None:
            self._gradio_client_lock = asyncio.Lock()

        async with self._gradio_client_lock:
            # Check if we have a valid client
            if self._gradio_client is not None:
                try:
                    # Test if client is still valid by checking if it can make a quick request
                    # We'll assume it's valid if it exists - Gradio clients are generally persistent
                    return self._gradio_client
                except Exception:
                    # Client is stale, will create new one
                    self._gradio_client = None

            # Create new client
            if self.gradio_url:
                try:
                    from gradio_client import Client
                    self._gradio_client = Client(self.gradio_url)
                    return self._gradio_client
                except Exception as e:
                    logger.error(f"Failed to create Gradio client: {e}")
                    raise RuntimeError(f"Failed to create Gradio client: {e}")
            else:
                raise RuntimeError("No Gradio URL available")
    
    async def synthesize_speech(
        self,
        text: str,
        voice: str = None,  # Will use dynamic default if None
        model: str = "tts-1",
        speed: float = 1.0,
        chunked: bool = True,
        play: bool = True,
        chunking_params: Optional[dict] = None,
        persist: bool = False,
        session_id: Optional[str] = None,
        mime_type: str = "audio/mpeg",
    ) -> AudioSynthesisResult:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice to use (if None, uses dynamic default based on available providers)
            model: TTS model to use (for OpenAI: tts-1, tts-1-hd)
            speed: Speed of speech (0.25 to 4.0)
            chunked: Whether to chunk the text (for ElevenLabs)
            play: Whether to play audio as soon as it's ready
            chunking_params: Dict of chunking parameters
            persist: Persist synthesized audio for client playback when True
            session_id: Campaign session identifier (required when persist=True)
            mime_type: Desired mime type for the generated artifact
            
        Returns:
            Synthesized audio container with optional artifact metadata
        """
        # Use dynamic default voice if none specified
        if voice is None:
            voice = VoiceRegistry.get_default_voice()
            if voice is None:
                raise RuntimeError("No TTS providers are available. Please check your TTS configuration.")

        # Apply hard limit on text length to avoid mega-requests
        original_len = len(text)
        if original_len > TTS_MAX_TEXT_LENGTH:
            text = text[:TTS_MAX_TEXT_LENGTH]
            logger.warning(f"🎵 TTS text truncated from {original_len} to {TTS_MAX_TEXT_LENGTH} chars")

        def finalize(audio_data: bytes, method: str) -> AudioSynthesisResult:
            artifact = None
            if persist and audio_data:
                if not session_id:
                    raise ValueError("session_id is required when persist=True")
                if audio_artifact_store.enabled:
                    try:
                        artifact = audio_artifact_store.persist_audio(
                            session_id=session_id,
                            audio_bytes=audio_data,
                            mime_type=mime_type,
                        )
                    except Exception as exc:
                        logger.error("Failed to persist client audio artifact: %s", exc)
                else:
                    logger.warning("Persist requested but audio artifact store is disabled")
            return AudioSynthesisResult(audio_bytes=audio_data or b"", method=method, artifact=artifact)

        # Determine which provider this voice belongs to
        voice_info = VoiceRegistry.get_voice(voice.lower())
        if voice_info:
            preferred_provider = voice_info.provider
        else:
            preferred_provider = VoiceProvider.LOCAL
            logger.warning(f"Voice '{voice}' not found in registry, using LOCAL fallback")

        logger.debug(f"🎵 TTS: voice={voice} provider={preferred_provider.value} text_len={len(text)}")

        # Try the preferred provider first
        if preferred_provider == VoiceProvider.LOCAL and self.local_tts_available:
            try:
                audio_data = await self._synthesize_local(
                    text,
                    voice,
                    speed,
                    chunked=chunked,
                    play=play,
                    chunking_params=chunking_params,
                    session_id=session_id,
                )
                return finalize(audio_data, "local")
            except Exception as e:
                logger.error(f"🎵 ❌ LOCAL synthesis failed: {e}")
                raise RuntimeError(f"Local TTS synthesis failed: {e}")

        elif preferred_provider == VoiceProvider.ELEVENLABS and self.elevenlabs_available:
            try:
                audio_data = await self._synthesize_elevenlabs(
                    text,
                    voice,
                    speed,
                    chunked=chunked,
                    play=play,
                    chunking_params=chunking_params,
                    session_id=session_id,
                )
                return finalize(audio_data, "elevenlabs")
            except Exception as e:
                logger.error(f"🎵 ❌ ELEVENLABS synthesis failed: {e}")
                raise RuntimeError(f"ElevenLabs TTS synthesis failed: {e}")

        elif preferred_provider == VoiceProvider.OPENAI and self.openai_client:
            try:
                audio_data = await self._synthesize_openai(text, voice, speed)
                return finalize(audio_data, "openai")
            except Exception as e:
                logger.error(f"🎵 ❌ OPENAI synthesis failed: {e}")
                raise RuntimeError(f"OpenAI TTS synthesis failed: {e}")

        # If preferred provider is not available, try fallback providers
        if preferred_provider == VoiceProvider.LOCAL and not self.local_tts_available:
            logger.warning("Local TTS is not available, trying fallback providers")
            # Try ElevenLabs fallback
            if self.elevenlabs_available:
                try:
                    logger.info("Falling back to ElevenLabs TTS")
                    audio_data = await self._synthesize_elevenlabs(
                        text,
                        voice,
                        speed,
                        chunked=chunked,
                        play=play,
                        chunking_params=chunking_params,
                        session_id=session_id,
                    )
                    return finalize(audio_data, "elevenlabs")
                except Exception as e:
                    logger.error(f"ElevenLabs fallback failed: {e}")
            # Try OpenAI fallback
            if self.openai_client:
                try:
                    logger.info("Falling back to OpenAI TTS")
                    audio_data = await self._synthesize_openai(text, voice, speed)
                    return finalize(audio_data, "openai")
                except Exception as e:
                    logger.error(f"OpenAI fallback failed: {e}")
        
        elif preferred_provider == VoiceProvider.ELEVENLABS and not self.elevenlabs_available:
            logger.warning("ElevenLabs TTS is not available, trying fallback providers")
            # Try Local fallback
            if self.local_tts_available:
                try:
                    logger.info("Falling back to Local TTS")
                    audio_data = await self._synthesize_local(
                        text,
                        voice,
                        speed,
                        chunked=chunked,
                        play=play,
                        chunking_params=chunking_params,
                        session_id=session_id,
                    )
                    return finalize(audio_data, "local")
                except Exception as e:
                    logger.error(f"Local fallback failed: {e}")
            # Try OpenAI fallback
            if self.openai_client:
                try:
                    logger.info("Falling back to OpenAI TTS")
                    audio_data = await self._synthesize_openai(text, voice, speed)
                    return finalize(audio_data, "openai")
                except Exception as e:
                    logger.error(f"OpenAI fallback failed: {e}")
        
        elif preferred_provider == VoiceProvider.OPENAI and not self.openai_client:
            logger.warning("OpenAI TTS is not available, trying fallback providers")
            # Try Local fallback
            if self.local_tts_available:
                try:
                    logger.info("Falling back to Local TTS")
                    audio_data = await self._synthesize_local(text, voice, speed, chunked=chunked, play=play, chunking_params=chunking_params)
                    return finalize(audio_data, "local")
                except Exception as e:
                    logger.error(f"Local fallback failed: {e}")
            # Try ElevenLabs fallback
            if self.elevenlabs_available:
                try:
                    logger.info("Falling back to ElevenLabs TTS")
                    audio_data = await self._synthesize_elevenlabs(text, voice, speed, chunked=chunked, play=play, chunking_params=chunking_params)
                    return finalize(audio_data, "elevenlabs")
                except Exception as e:
                    logger.error(f"ElevenLabs fallback failed: {e}")
        
        logger.error("No TTS engines available")
        return finalize(b"", "none")

    async def synthesize_speech_progressive(
        self,
        text: str,
        voice: str = None,
        speed: float = 1.0,
        chunked: bool = True,
        chunking_params: Optional[dict] = None,
        session_id: Optional[str] = None,
        on_chunk_ready: Optional[Callable[[Dict], Any]] = None,
        playback_writer: Optional[PlaybackRequestWriter] = None,
    ) -> Dict:
        """
        Synthesize speech progressively, persisting and broadcasting each chunk as it's ready.

        Args:
            text: Text to synthesize
            voice: Voice to use (if None, uses dynamic default)
            speed: Speed of speech (0.25 to 4.0)
            chunked: Whether to chunk the text
            chunking_params: Dict of chunking parameters
            session_id: Campaign session identifier (required)
            on_chunk_ready: Callback when chunk is persisted (receives artifact dict)
            playback_writer: Optional playback request writer for DB persistence/broadcasting

        Returns:
            Dict with summary info (method, total_chunks, etc.)
        """
        if voice is None:
            voice = VoiceRegistry.get_default_voice()
            if voice is None:
                raise RuntimeError("No TTS providers are available. Please check your TTS configuration.")

        # Apply hard limit on text length to avoid mega-requests
        original_len = len(text)
        if original_len > TTS_MAX_TEXT_LENGTH:
            text = text[:TTS_MAX_TEXT_LENGTH]
            logger.warning(f"🎵 TTS text truncated from {original_len} to {TTS_MAX_TEXT_LENGTH} chars")

        # Determine provider
        voice_info = VoiceRegistry.get_voice(voice.lower())
        if not voice_info:
            raise ValueError(f"Voice {voice} not found in registry")

        preferred_provider = voice_info.provider

        # Generate progressively based on provider
        if preferred_provider == VoiceProvider.LOCAL and self.local_tts_available:
            audio_data, chunk_list = await self._synthesize_local_progressive(
                text, voice, speed, chunked, chunking_params, session_id, on_chunk_ready, playback_writer
            )
            return {"method": "local", "total_chunks": len(chunk_list), "total_bytes": len(audio_data)}

        elif preferred_provider == VoiceProvider.ELEVENLABS and self.elevenlabs_available:
            audio_data, chunk_list = await self._synthesize_elevenlabs_progressive(
                text, voice, speed, chunked, chunking_params, session_id, on_chunk_ready, playback_writer
            )
            return {"method": "elevenlabs", "total_chunks": len(chunk_list), "total_bytes": len(audio_data)}

        else:
            raise RuntimeError(f"Progressive synthesis not supported for provider {preferred_provider}")

    async def _synthesize_elevenlabs_progressive(
        self,
        text: str,
        voice: str,
        speed: float,
        chunked: bool,
        chunking_params: Optional[dict],
        session_id: str,
        on_chunk_ready: Optional[Callable[[Dict], Any]],
        playback_writer: Optional[PlaybackRequestWriter],
    ):
        """Synthesize using ElevenLabs with progressive persistence."""
        voice_id = VoiceRegistry.get_provider_voice_id(voice.lower(), VoiceProvider.ELEVENLABS)

        async def create_elevenlabs_audio(chunk_text: str, voice: str, speed: float) -> bytes:
            if chunk_text == "__PARAGRAPH_BREAK__":
                return b""
            return await self._create_elevenlabs_audio(chunk_text, voice_id)

        all_audio, chunk_audio_data = await chunking_manager.synthesize_with_chunking(
            text=text,
            provider=VoiceProvider.ELEVENLABS,
            voice=voice,
            speed=speed,
            audio_creator_func=create_elevenlabs_audio,
            play=False,  # Don't play locally
            chunked=chunked,
            custom_chunking_params=chunking_params,
            session_id=session_id,
            persist_progressive=True,
            on_chunk_ready=on_chunk_ready,
            playback_group="narrative",
            playback_writer=playback_writer,
        )

        return all_audio, chunk_audio_data

    async def _synthesize_local_progressive(
        self,
        text: str,
        voice: str,
        speed: float,
        chunked: bool,
        chunking_params: Optional[dict],
        session_id: str,
        on_chunk_ready: Optional[Callable[[Dict], Any]],
        playback_writer: Optional[PlaybackRequestWriter],
    ):
        """Synthesize using Local TTS with progressive persistence."""
        voice_id = VoiceRegistry.get_provider_voice_id(voice.lower(), VoiceProvider.LOCAL)

        async def create_local_audio(chunk_text: str, voice: str, speed: float) -> bytes:
            return await self._create_local_audio(chunk_text, voice_id)

        all_audio, chunk_audio_data = await chunking_manager.synthesize_with_chunking(
            text=text,
            provider=VoiceProvider.LOCAL,
            voice=voice,
            speed=speed,
            audio_creator_func=create_local_audio,
            play=False,  # Don't play locally
            chunked=chunked,
            custom_chunking_params=chunking_params,
            session_id=session_id,
            persist_progressive=True,
            on_chunk_ready=on_chunk_ready,
            playback_group="narrative",
            playback_writer=playback_writer,
        )

        return all_audio, chunk_audio_data

    def _preprocess_text_for_tts(self, text: str) -> str:
        """Preprocess text to avoid TTS artifacts."""
        # Remove multiple spaces
        text = ' '.join(text.split())
        # Remove zero-width characters
        text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
        # Ensure proper spacing after punctuation
        text = text.replace('.', '. ').replace('!', '! ').replace('?', '? ')
        # Clean up multiple spaces again
        text = ' '.join(text.split())
        return text.strip()

    async def _create_elevenlabs_audio(self, chunk_text, voice_id, model_id="eleven_multilingual_v2") -> bytes:
        if not self.elevenlabs_available or not self.elevenlabs_api_key:
            logger.error("ElevenLabs streaming requested but client/API key not configured")
            return b""

        cleaned_text = self._preprocess_text_for_tts(chunk_text)

        # ElevenLabs streaming endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        headers = {
            "Accept": "audio/mpeg",
            "xi-api-key": self.elevenlabs_api_key,
        }
        payload = {
            "text": cleaned_text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.8,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": False,
            },
            # Optimize streaming for low latency (1-4; 0 disables)
            "optimize_streaming_latency": 2,
        }

        audio_bytes = bytearray()

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            "ElevenLabs streaming request failed (%s): %s",
                            response.status,
                            error_text[:200],
                        )
                        return b""

                    async for chunk in response.content.iter_chunked(4096):
                        if chunk:
                            audio_bytes.extend(chunk)

        except Exception as exc:
            logger.error("Error during ElevenLabs streaming synthesis: %s", exc, exc_info=True)
            return b""

        result_bytes = bytes(audio_bytes)
        logger = logging.getLogger(__name__)
        logger.debug(
            "ElevenLabs streaming produced %d bytes for voice_id=%s text_len=%d",
            len(result_bytes),
            voice_id,
            len(cleaned_text),
        )
        return result_bytes

    async def _synthesize_elevenlabs(
        self,
        text: str,
        voice: str,
        speed: float,
        chunked: bool = True,
        play: bool = True,
        chunking_params: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> bytes:
        """Synthesize speech using ElevenLabs TTS with unified chunking and enhanced features."""
        # Get voice ID from registry
        voice_id = VoiceRegistry.get_provider_voice_id(voice.lower(), VoiceProvider.ELEVENLABS)
        
        # Check if seamless mode is enabled (use centralized config)
        try:
            seamless_mode = self.chunking_config['seamless_mode']
        except (KeyError, AttributeError):
            # Fallback to playback config
            try:
                playback_config = get_playback_config()
                seamless_mode = playback_config['seamless']
            except Exception:
                # Final fallback to centralized constant
                seamless_mode = AUTO_TTS_SEAMLESS
        
        # Create enhanced audio creator function for ElevenLabs with paragraph break support
        async def create_elevenlabs_audio(chunk_text: str, voice: str, speed: float) -> bytes:
            # Skip paragraph breaks - they don't need audio
            if chunk_text == "__PARAGRAPH_BREAK__":
                return b""
            return await self._create_elevenlabs_audio(chunk_text, voice_id)
        
        # Use unified chunking manager with custom parameters
        all_audio, chunk_audio_data = await chunking_manager.synthesize_with_chunking(
            text=text,
            provider=VoiceProvider.ELEVENLABS,
            voice=voice,
            speed=speed,
            audio_creator_func=create_elevenlabs_audio,
            play=play,
            chunked=chunked,
            custom_chunking_params=chunking_params,
            session_id=session_id,
        )
        
        return all_audio
    
    async def _play_chunks_sequential(
        self,
        chunk_audio_data,
        voice,
        chunks,
        temp_dir,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
    ):
        """Play audio chunks sequentially."""
        from gaia.infra.audio.audio_queue_manager import audio_queue_manager
        
        # Filter out paragraph breaks from audio data (they don't have audio)
        audio_index = 0
        
        for i, chunk_text in enumerate(chunks):
            if chunk_text == "__PARAGRAPH_BREAK__":
                # Add a pause item to the queue for paragraph breaks
                await audio_queue_manager.add_paragraph_break(
                    session_id=session_id,
                    playback_id=playback_id,
                )
            else:
                # Regular audio chunk
                audio_data = chunk_audio_data[audio_index]
                audio_index += 1
                
                filename = f"elevenlabs_chunk_{i+1}.mp3"
                file_path = temp_dir / filename
                with open(file_path, "wb") as f:
                    f.write(audio_data)
                # Add to queue
                await audio_queue_manager.add_to_queue(
                    file_path=str(file_path),
                    voice=voice,
                    text=chunk_text[:100],  # Preview of chunk
                    session_id=session_id,
                    playback_id=playback_id,
                )
    

    
    async def _synthesize_local(
        self,
        text: str,
        voice: str,
        speed: float,
        chunked: bool = True,
        play: bool = True,
        chunking_params: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> bytes:
        """Synthesize speech using local F5-TTS Gradio server with unified chunking."""
        if not self.local_tts_available or not self.gradio_url:
            raise RuntimeError("Local TTS not available")
        
        # Get voice ID from registry
        voice_id = VoiceRegistry.get_provider_voice_id(voice, VoiceProvider.LOCAL)
        if not voice_id:
            logger.warning(f"Voice '{voice}' not found in local registry, using default 'dm'")
            voice_id = "dm"
        
        # Create audio creator function for Local TTS
        async def create_local_audio(chunk_text: str, voice: str, speed: float) -> bytes:
            return await self._create_local_audio(chunk_text, voice_id)
        
        # Use unified chunking manager
        all_audio, _ = await chunking_manager.synthesize_with_chunking(
            text=text,
            provider=VoiceProvider.LOCAL,
            voice=voice,
            speed=speed,
            audio_creator_func=create_local_audio,
            play=play,
            chunked=chunked,
            custom_chunking_params=chunking_params,
            session_id=session_id,
        )
        
        return all_audio

    async def _create_local_audio(self, chunk_text: str, voice_id: str) -> bytes:
        """Create audio for a single chunk using local F5-TTS."""
        # Import required modules
        from pathlib import Path
        import time
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO

        start_time = time.time()

        try:

            # Get speaker configuration from Python config
            speaker_config = get_speaker_config(voice_id)
            if not speaker_config:
                raise RuntimeError(f"Speaker '{voice_id}' not found in configuration")
            
            ref_audio_path = speaker_config.reference_audio
            ref_text = speaker_config.reference_text
            
            # Check if reference audio file exists
            if not Path(ref_audio_path).exists():
                logger.error(f"❌ Reference audio not found: {ref_audio_path}")
                raise RuntimeError(f"Reference audio file not found: {ref_audio_path}")

            # Get persistent Gradio client (reuse connection)
            client_start = time.time()
            client = await self._get_gradio_client()
            client_time = time.time() - client_start

            # Create FileData object for reference audio
            file_data = {
                "path": ref_audio_path,
                "meta": {"_type": "gradio.FileData"}
            }

            # Use basic_tts endpoint with F5TTS_v1_Base model
            # Suppress F5-TTS debug output (gen_text lines) during prediction
            predict_start = time.time()
            f_stdout = StringIO()
            f_stderr = StringIO()

            # Note: F5-TTS model prints directly to stdout, which we can't fully suppress
            # via Gradio client, but we suppress what we can
            with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                try:
                    result = client.predict(
                        file_data,
                        ref_text,
                        chunk_text,
                        "F5TTS_v1_Base",  # model
                        api_name="/basic_tts"
                    )
                except Exception as e:
                    # If suppression fails, continue without it
                    result = client.predict(
                        file_data,
                        ref_text,
                        chunk_text,
                        "F5TTS_v1_Base",  # model
                        api_name="/basic_tts"
                    )
            predict_time = time.time() - predict_start

            # Handle the result
            if isinstance(result, (list, tuple)):
                generated_audio_path = result[0]
            else:
                generated_audio_path = result

            # Read the generated audio file
            with open(generated_audio_path, "rb") as f:
                audio_data = f.read()

            total_time = time.time() - start_time
            logger.info(f"🎵 ✅ Chunk: connect={client_time:.2f}s synthesis={predict_time:.2f}s total={total_time:.2f}s size={len(audio_data)}b")

            return audio_data

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"🎵 ❌ Chunk failed after {total_time:.2f}s: {e}")
            raise RuntimeError(f"Local TTS synthesis failed: {e}")


    
    async def _synthesize_openai(
        self,
        text: str,
        voice: str,
        speed: float
    ) -> bytes:
        """Synthesize speech using OpenAI TTS."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")
        
        try:
            # Get voice ID from registry
            voice_id = VoiceRegistry.get_provider_voice_id(voice, VoiceProvider.OPENAI)
            
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice_id,
                input=text,
                speed=speed
            )
            
            return response.content
            
        except Exception as e:
            raise RuntimeError(f"OpenAI TTS synthesis failed: {e}")
    
    
    def is_provider_available(self, provider: VoiceProvider) -> bool:
        """Check if a specific TTS provider is available."""
        if provider == VoiceProvider.LOCAL:
            return self.local_tts_available and self.gradio_url is not None
        elif provider == VoiceProvider.ELEVENLABS:
            return self.elevenlabs_available
        elif provider == VoiceProvider.OPENAI:
            return self.openai_client is not None
        return False

    def recheck_availability(self):
        """Recheck all TTS provider availability (useful for timing issues)."""
        logger.info("Rechecking TTS provider availability...")

        # F5-TTS DISABLED - No longer checking for local TTS
        # self._check_local_tts()

        # Recheck ElevenLabs
        self._check_elevenlabs()

        # Log current status
        logger.info(f"TTS Availability after recheck - ElevenLabs: {self.elevenlabs_available}, OpenAI: {self.openai_client is not None}")

        return {
            "elevenlabs": self.elevenlabs_available,
            "openai": self.openai_client is not None
        }

    def get_available_voices(self) -> list:
        """Get list of available voices for providers that are actually working."""
        voices = []
        
        # Only add ElevenLabs voices if ElevenLabs is available and working
        if self.elevenlabs_available and self.elevenlabs_client:
            for voice in VoiceRegistry.list_voices(VoiceProvider.ELEVENLABS):
                voices.append({
                    "id": voice.id,
                    "name": f"{voice.name} ({voice.provider.value})",
                    "provider": voice.provider.value,
                    "description": voice.description,
                    "gender": voice.gender,
                    "style": voice.style,
                    "character_role": voice.character_role
                })
            # Only log once during initialization, not every time the method is called
            if not hasattr(self, '_elevenlabs_logged'):
                logger.info(f"ElevenLabs is available, {len(voices)} ElevenLabs voices loaded from registry")
                self._elevenlabs_logged = True
        else:
            if not hasattr(self, '_elevenlabs_not_available_logged'):
                logger.info("ElevenLabs not available, skipping ElevenLabs voices")
                self._elevenlabs_not_available_logged = True
        
        # Only add local voices if local TTS is available and working
        if self.local_tts_available and self.gradio_url:
            for voice in VoiceRegistry.list_voices(VoiceProvider.LOCAL):
                voices.append({
                    "id": voice.id,
                    "name": f"{voice.name} ({voice.provider.value})",
                    "provider": voice.provider.value,
                    "description": voice.description,
                    "gender": voice.gender,
                    "style": voice.style,
                    "character_role": voice.character_role
                })
            # Only log once during initialization, not every time the method is called
            if not hasattr(self, '_local_logged'):
                logger.info(f"Local F5-TTS is available, {len(voices)} total voices loaded from registry")
                self._local_logged = True
        else:
            # F5-TTS not available - silently skip local voices
            pass
        
        # Only add OpenAI voices if OpenAI is available and working
        if self.openai_client:
            for voice in VoiceRegistry.list_voices(VoiceProvider.OPENAI):
                voices.append({
                    "id": voice.id,
                    "name": f"{voice.name} ({voice.provider.value})",
                    "provider": voice.provider.value,
                    "description": voice.description,
                    "gender": voice.gender,
                    "style": voice.style,
                    "character_role": voice.character_role
                })
            # Only log once during initialization, not every time the method is called
            if not hasattr(self, '_openai_logged'):
                logger.info(f"OpenAI is available, {len(voices)} total voices loaded from registry")
                self._openai_logged = True
        else:
            if not hasattr(self, '_openai_not_available_logged'):
                logger.info("OpenAI not available, skipping OpenAI voices")
                self._openai_not_available_logged = True
        
        return voices
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            for file in self.temp_dir.glob("tts_*.wav"):
                file.unlink(missing_ok=True)



    async def synthesize_and_play_elevenlabs_chunked_unix(
        self,
        text: str,
        voice: str = "priyanka",
        speed: float = 1.0,
        session_id: Optional[str] = None,
    ):
        """
        Chunk the text, synthesize each chunk with ElevenLabs, and play each chunk via Unix audio as soon as it's ready.
        """
        if not self.elevenlabs_available:
            raise RuntimeError("ElevenLabs TTS is not available")

        # Apply hard limit on text length to avoid mega-requests
        original_len = len(text)
        if original_len > TTS_MAX_TEXT_LENGTH:
            text = text[:TTS_MAX_TEXT_LENGTH]
            logger.warning(f"🎵 TTS text truncated from {original_len} to {TTS_MAX_TEXT_LENGTH} chars")

        chunks = self.chunk_text_by_sentences(text)
        if not chunks:
            logger.warning("No chunks to synthesize")
            return
        logger.info(f"Synthesizing and playing {len(chunks)} chunks with ElevenLabs...")
        import tempfile
        from pathlib import Path
        # Use centralized temp directory instead of environment variable
        temp_dir = Path(AUDIO_TEMP_DIR) / "elevenlabs_tts_chunks"
        temp_dir.mkdir(parents=True, exist_ok=True)
        async def synth_and_play(chunk_text, idx):
            audio_data = await self._synthesize_elevenlabs(
                chunk_text,
                voice,
                speed,
                session_id=session_id,
            )
            file_path = temp_dir / f"chunk_{idx:03d}.mp3"
            with open(file_path, "wb") as f:
                f.write(audio_data)
            # Add to queue instead of playing directly
            from gaia.infra.audio.audio_queue_manager import audio_queue_manager
            await audio_queue_manager.add_to_queue(
                file_path=str(file_path),
                voice=voice,
                text=chunk_text[:100],  # Preview of chunk
                session_id=session_id,
            )
        # Synthesize and play the first chunk, then the rest in parallel (but play in order)
        await synth_and_play(chunks[0], 0)
        for idx, chunk_text in enumerate(chunks[1:], 1):
            await synth_and_play(chunk_text, idx)

# Global TTS service instance
tts_service = TTSService() 
