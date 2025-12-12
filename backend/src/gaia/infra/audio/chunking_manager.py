"""Unified chunking manager for all TTS providers."""

import os
import logging
import tempfile
import time
import io
import asyncio
import uuid
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass

from gaia.infra.audio.voice_registry import VoiceProvider
from gaia.infra.audio.voice_and_tts_config import (
    get_chunking_config, get_playback_config, AUTO_TTS_SEAMLESS, AUDIO_TEMP_DIR
)
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter

logger = logging.getLogger(__name__)

@dataclass
class ChunkingConfig:
    """Configuration for chunking parameters."""
    target_chunk_size: int
    max_chunk_size: int
    sentences_per_chunk: int
    audio_format: str  # 'mp3', 'wav', etc.
    seamless_supported: bool = True

class UnifiedChunkingManager:
    """Unified chunking manager for all TTS providers."""
    
    @staticmethod
    def _sanitize_identifier(value: Optional[str]) -> str:
        """Return a filesystem-safe identifier."""
        if not value or not str(value).strip():
            return "default"
        sanitized = re.sub(r'[^A-Za-z0-9_-]', '_', str(value))
        return sanitized[:64] or "default"

    @classmethod
    def _generate_playback_token(cls, session_id: Optional[str]) -> str:
        """Generate a unique playback token for a request."""
        safe_session = cls._sanitize_identifier(session_id)
        return f"{safe_session}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    
    # Provider-specific default configurations (using centralized config as base)
    @classmethod
    def _get_base_config(cls):
        """Get base configuration from centralized config with fallbacks."""
        try:
            config = get_chunking_config()
            return {
                'target_chunk_size': config['chunk_size'],
                'max_chunk_size': config['max_chunk_size'],
                'sentences_per_chunk': config['max_sentences_per_chunk']
            }
        except Exception:
            # Fallback values if centralized config fails
            return {
                'target_chunk_size': 400,
                'max_chunk_size': 500,
                'sentences_per_chunk': 3
            }
    
    @classmethod
    def _get_provider_configs(cls):
        """Get provider-specific configurations using centralized config as base."""
        base_config = cls._get_base_config()
        
        return {
            VoiceProvider.ELEVENLABS: ChunkingConfig(
                target_chunk_size=base_config['target_chunk_size'],
                max_chunk_size=base_config['max_chunk_size'],
                sentences_per_chunk=base_config['sentences_per_chunk'],
                audio_format="mp3",
                seamless_supported=True
            ),
            VoiceProvider.LOCAL: ChunkingConfig(
                target_chunk_size=base_config['target_chunk_size'],
                max_chunk_size=base_config['max_chunk_size'],
                sentences_per_chunk=base_config['sentences_per_chunk'],
                audio_format="wav",
                seamless_supported=True
            ),
            VoiceProvider.OPENAI: ChunkingConfig(
                # OpenAI typically handles longer chunks better
                target_chunk_size=max(base_config['target_chunk_size'], 750),
                max_chunk_size=max(base_config['max_chunk_size'], 900),
                sentences_per_chunk=max(base_config['sentences_per_chunk'], 9),
                audio_format="mp3",
                seamless_supported=True
            )
        }
    
    # Use property to get configs dynamically
    @property
    def PROVIDER_CONFIGS(self):
        return self._get_provider_configs()
    
    @classmethod
    def get_chunking_config(cls, provider: VoiceProvider) -> ChunkingConfig:
        """Get chunking configuration for a specific provider."""
        configs = cls._get_provider_configs()
        return configs.get(provider, configs[VoiceProvider.ELEVENLABS])
    
    @classmethod
    def get_chunking_config_with_centralized_fallback(cls, provider: VoiceProvider) -> ChunkingConfig:
        """Get chunking configuration with centralized config as fallback."""
        centralized_config = get_chunking_config()
        
        # Use centralized config values as fallback for the provider config
        provider_config = cls.get_chunking_config(provider)
        
        return ChunkingConfig(
            target_chunk_size=centralized_config.get('chunk_size', provider_config.target_chunk_size),
            max_chunk_size=centralized_config.get('max_chunk_size', provider_config.max_chunk_size),
            sentences_per_chunk=centralized_config.get('max_sentences_per_chunk', provider_config.sentences_per_chunk),
            audio_format=provider_config.audio_format,
            seamless_supported=provider_config.seamless_supported
        )
    
    @classmethod
    def chunk_text_by_sentences(cls, text: str, target_chunk_size: int = 750, max_chunk_size: int = 900, sentences_per_chunk: int = 9) -> List[str]:
        """
        Split text into chunks based on sentences and paragraphs.
        Groups sentences together, up to specified character limits.
        Respects paragraph boundaries for natural pauses.
        
        Args:
            text: Text to chunk
            target_chunk_size: Target size for each chunk in characters
            max_chunk_size: Maximum size for each chunk in characters
            sentences_per_chunk: Target number of sentences per chunk
            
        Returns:
            List of text chunks (includes "__PARAGRAPH_BREAK__" markers)
        """
        import re
        if not text or not text.strip():
            return []
        
        # First split by paragraphs (double newlines)
        paragraphs = re.split(r'\n\s*\n', text.strip())
        
        all_chunks = []
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            # Split by sentence endings
            sentence_pattern = r'(?<=[.!?])\s+'
            sentences = re.split(sentence_pattern, paragraph.strip())
            
            # Filter out empty sentences
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                continue
            
            # Process sentences within this paragraph
            current_chunk = []
            current_length = 0
            sentence_count = 0
            
            for sentence in sentences:
                sentence_length = len(sentence)
                
                # Check if adding this sentence would exceed limits
                would_exceed_size = current_length + sentence_length > max_chunk_size
                has_enough_sentences = sentence_count >= sentences_per_chunk
                is_good_chunk_size = current_length >= target_chunk_size
                
                # Start a new chunk if needed
                if current_chunk and (would_exceed_size or (has_enough_sentences and is_good_chunk_size)):
                    all_chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                    sentence_count = 0
                
                # Add sentence to current chunk
                current_chunk.append(sentence)
                current_length += sentence_length + 1  # +1 for space
                sentence_count += 1
            
            # Add the last chunk from this paragraph
            if current_chunk:
                all_chunks.append(' '.join(current_chunk))
                
            # Add a paragraph break marker if not the last paragraph
            if paragraph != paragraphs[-1]:
                all_chunks.append("__PARAGRAPH_BREAK__")
        
        logger.debug(f"Split text into {len(all_chunks)} chunks across {len(paragraphs)} paragraphs")
        for i, chunk in enumerate(all_chunks):
            if chunk == "__PARAGRAPH_BREAK__":
                logger.debug(f"Chunk {i+1}: [PARAGRAPH BREAK]")
            else:
                logger.debug(f"Chunk {i+1}: {len(chunk)} chars, {chunk[:50]}...")
        
        return all_chunks
    
    @classmethod
    async def synthesize_with_chunking(
        cls,
        text: str,
        provider: VoiceProvider,
        voice: str,
        speed: float,
        audio_creator_func: Callable[[str, str, float], Any],
        play: bool = True,
        chunked: bool = True,
        custom_chunking_params: Optional[Dict] = None,
        session_id: Optional[str] = None,
        persist_progressive: bool = False,
        on_chunk_ready: Optional[Callable[[Dict], Any]] = None,
        playback_group: str = "narrative",
        playback_writer: Optional[PlaybackRequestWriter] = None,
    ) -> Tuple[bytes, List[bytes]]:
        """
        Unified method to synthesize audio with chunking for any provider.
        Uses streaming approach - starts playback as soon as first chunk is ready.

        Args:
            text: Text to synthesize
            provider: TTS provider
            voice: Voice to use
            speed: Speed of speech
            audio_creator_func: Function to create audio for a single chunk
            play: Whether to play the audio
            chunked: Whether to use chunking
            custom_chunking_params: Override default chunking parameters
            session_id: Session identifier
            persist_progressive: If True, persist and broadcast each chunk as it's ready
            on_chunk_ready: Callback when chunk is persisted (receives artifact dict)
            playback_group: Group identifier for playback ordering (narrative, response, etc.)
            playback_writer: Optional shared playback writer for DB persistence/broadcasting

        Returns:
            Tuple of (combined_audio_data, list_of_chunk_audio_data)
        """
        config = cls.get_chunking_config(provider)

        # Use custom parameters if provided, otherwise use provider defaults
        if custom_chunking_params:
            target_chunk_size = custom_chunking_params.get('target_chunk_size', config.target_chunk_size)
            max_chunk_size = custom_chunking_params.get('max_chunk_size', config.max_chunk_size)
            sentences_per_chunk = custom_chunking_params.get('sentences_per_chunk', config.sentences_per_chunk)
        else:
            target_chunk_size = config.target_chunk_size
            max_chunk_size = config.max_chunk_size
            sentences_per_chunk = config.sentences_per_chunk

        # Chunk the text
        if chunked:
            chunks = cls.chunk_text_by_sentences(
                text,
                target_chunk_size=target_chunk_size,
                max_chunk_size=max_chunk_size,
                sentences_per_chunk=sentences_per_chunk
            )
        else:
            chunks = [text]

        playback_id = cls._generate_playback_token(session_id)

        # Playback request writer provided by caller (optional)
        writer = playback_writer if persist_progressive and session_id else None
 
        all_audio = b""
        chunk_audio_data: List[bytes] = []
        start_time = time.time()
        total_audio_size = 0
        successful_chunks = 0

        for index, chunk_text in enumerate(chunks):
            chunk_number = index + 1

            if chunk_text == "__PARAGRAPH_BREAK__":
                if play:
                    await cls._queue_paragraph_break_for_playback(
                        chunk_number,
                        session_id=session_id,
                        playback_id=playback_id,
                    )
                continue

            audio_data = await audio_creator_func(chunk_text, voice, speed)

            if play:
                await cls._queue_chunk_for_playback(
                    audio_data,
                    chunk_text,
                    voice,
                    chunk_number,
                    provider,
                    config,
                    session_id=session_id,
                    playback_id=playback_id,
                )

            # Progressive persistence for client audio
            if persist_progressive and writer and session_id:
                # Create artifact via audio_artifact_store
                artifact = await cls._create_audio_artifact(
                    audio_data,
                    chunk_text,
                    chunk_number,
                    len(chunks),
                    config,
                    session_id,
                    playback_group=playback_group,
                )

                if artifact:
                    # Persist to DB and broadcast via writer
                    await writer.add_chunk(
                        artifact=artifact,
                        sequence_number=chunk_number - 1,  # 0-indexed
                        text_preview=chunk_text,
                    )

                    # Call user callback if provided
                    if on_chunk_ready:
                        await on_chunk_ready(artifact)

            all_audio += audio_data
            chunk_audio_data.append(audio_data)
            total_audio_size += len(audio_data)
            successful_chunks += 1

        if play:
            await cls._handle_streaming_playback(
                chunks,
                voice,
                text,
                provider,
                config,
                session_id=session_id,
                playback_id=playback_id,
            )

        # Finalize the playback request writer
        if writer:
            await writer.finalize(text=text)

        total_time = time.time() - start_time
        avg_chunk_time = total_time / successful_chunks if successful_chunks > 0 else 0
        logger.debug(
            "🎵 [CHUNKS] ✅ %s completed: %s chunks total_time=%.2fs avg_chunk=%.2fs total_size=%sb",
            provider.value,
            successful_chunks,
            total_time,
            avg_chunk_time,
            total_audio_size,
        )

        return all_audio, chunk_audio_data
    
    @classmethod
    async def _queue_chunk_for_playback(
        cls,
        audio_data: bytes,
        chunk_text: str,
        voice: str,
        chunk_number: int,
        provider: VoiceProvider,
        config: ChunkingConfig,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
    ):
        """Queue a single chunk for immediate playback."""
        import tempfile
        from pathlib import Path
        from gaia.infra.audio.audio_queue_manager import audio_queue_manager
        
        # Use centralized temp directory instead of environment variable
        provider_name = provider.value
        temp_dir = Path(AUDIO_TEMP_DIR) / f"{provider_name}_tts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Write chunk to file
        filename = f"{provider.value}_chunk_{chunk_number}.{config.audio_format}"
        file_path = temp_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(audio_data)
        
        # Add to queue for immediate playback
        await audio_queue_manager.add_to_queue(
            file_path=str(file_path),
            voice=voice,
            text=chunk_text[:100],  # Preview of chunk
            session_id=session_id,
            playback_id=playback_id,
            metadata={
                "chunk_number": chunk_number,
                "total_text_length": len(chunk_text),
            },
        )
    
    @classmethod
    async def _queue_paragraph_break_for_playback(
        cls,
        chunk_number: int,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
    ) -> None:
        """Queue a paragraph break pause for playback."""
        from gaia.infra.audio.audio_queue_manager import audio_queue_manager

        await audio_queue_manager.add_paragraph_break(
            session_id=session_id,
            playback_id=playback_id,
        )

    @classmethod
    async def _create_audio_artifact(
        cls,
        audio_data: bytes,
        chunk_text: str,
        chunk_number: int,
        total_chunks: int,
        config: ChunkingConfig,
        session_id: str,
        playback_group: str = "narrative",
    ) -> Optional[Dict]:
        """Create audio artifact for a single chunk (without DB persistence).

        DB persistence and broadcasting is handled by PlaybackRequestWriter.
        """
        try:
            from gaia.infra.audio.audio_artifact_store import audio_artifact_store

            if not audio_artifact_store.enabled:
                logger.warning("Audio artifact store not enabled, cannot create chunk artifact")
                return None

            # Determine mime type based on audio format
            mime_type = "audio/mpeg" if config.audio_format == "mp3" else "audio/wav"

            # Create the artifact. In environments with a configured GCS bucket,
            # upload to GCS so any instance can serve the file. Fall back to
            # local-only persistence when no bucket is configured.
            artifact = audio_artifact_store.persist_audio(
                session_id=session_id,
                audio_bytes=audio_data,
                mime_type=mime_type,
                # If a bucket is available, do NOT skip upload. This avoids
                # 404s on serverless platforms where requests may hit
                # different instances that don't share local storage.
                skip_gcs_upload=not audio_artifact_store.uses_gcs,
            )

            logger.debug(
                f"Created artifact for chunk {chunk_number}/{total_chunks}, session {session_id}: {artifact.url}"
            )

            # Return artifact info as dict
            payload = artifact.to_payload()
            payload.update({
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "mime_type": artifact.mime_type,
                "text_preview": chunk_text[:100],
                "playback_group": playback_group,
                "sequence_number": chunk_number - 1,  # 0-indexed for consistency
            })
            return payload

        except Exception as e:
            logger.error(f"Failed to create artifact for chunk {chunk_number}: {e}", exc_info=True)
            return None

    @classmethod
    async def _handle_streaming_playback(
        cls,
        chunks: List[str],
        voice: str,
        full_text: str,
        provider: VoiceProvider,
        config: ChunkingConfig,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
    ):
        """Handle streaming playback - wait for queue to finish processing."""
        from gaia.infra.audio.audio_queue_manager import audio_queue_manager
        
        # Wait for all chunks to be processed by the queue for this session
        while True:
            status = audio_queue_manager.get_queue_status(session_id=session_id)
            queue_empty = status.get("queue_size", 0) == 0
            active_playback = status.get("is_playing")
            current_playback_id = status.get("current_playback_id")
            pending_groups = status.get("pending_playback_ids", [])

            if (
                queue_empty
                and not active_playback
                and (not playback_id or playback_id not in pending_groups)
                and (not playback_id or current_playback_id != playback_id)
            ):
                break
            await asyncio.sleep(0.1)
        


        logger.debug("Streaming playback completed - all chunks processed")
    

    @classmethod
    async def _handle_playback(
        cls,
        chunk_audio_data: List[bytes],
        chunks: List[str],
        voice: str,
        full_text: str,
        provider: VoiceProvider,
        config: ChunkingConfig,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
    ):
        """Handle audio playback with seamless or sequential options."""
        import tempfile
        from pathlib import Path
        
        # Use centralized temp directory instead of environment variable
        provider_name = provider.value
        temp_dir = Path(AUDIO_TEMP_DIR) / f"{provider_name}_tts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if seamless mode is enabled (use centralized config)
        try:
            seamless_mode = get_playback_config()['seamless']
        except Exception:
            # Fallback to centralized constant if config function fails
            seamless_mode = AUTO_TTS_SEAMLESS
        
        if seamless_mode and len(chunks) > 1 and config.seamless_supported:
            # Seamless mode: Concatenate all audio and play as one file
            logger.info(f"Using seamless playback mode for {provider.value} - concatenating audio chunks")
            
            try:
                from pydub import AudioSegment
                combined = AudioSegment.empty()
                
                for audio_data in chunk_audio_data:
                    if config.audio_format == "mp3":
                        segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
                    elif config.audio_format == "wav":
                        segment = AudioSegment.from_wav(io.BytesIO(audio_data))
                    else:
                        # Fallback to mp3
                        segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
                    combined += segment
                
                # Export combined audio
                filename = f"{provider_name}_combined_{int(time.time())}.{config.audio_format}"
                file_path = temp_dir / filename
                combined.export(file_path, format=config.audio_format)
                
                # Play the combined file
                from gaia.infra.audio.audio_queue_manager import audio_queue_manager
                await audio_queue_manager.add_to_queue(
                    file_path=str(file_path),
                    voice=voice,
                    text=full_text[:100],  # Preview of full text
                    session_id=session_id,
                    playback_id=playback_id,
                    metadata={"mode": "seamless"},
                )
                
            except ImportError:
                logger.warning("pydub not available for seamless playback, falling back to sequential mode")
                await cls._play_chunks_sequential(
                    chunk_audio_data,
                    chunks,
                    voice,
                    temp_dir,
                    provider,
                    config,
                    session_id=session_id,
                    playback_id=playback_id,
                )
        else:
            # Sequential mode or single chunk
            await cls._play_chunks_sequential(
                chunk_audio_data,
                chunks,
                voice,
                temp_dir,
                provider,
                config,
                session_id=session_id,
                playback_id=playback_id,
            )
    
    @classmethod
    async def _play_chunks_sequential(
        cls,
        chunk_audio_data: List[bytes],
        chunks: List[str],
        voice: str,
        temp_dir: Path,
        provider: VoiceProvider,
        config: ChunkingConfig,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
    ):
        """Play audio chunks sequentially."""
        from gaia.infra.audio.audio_queue_manager import audio_queue_manager
        
        logger.info(f"Queuing {len(chunks)} chunks for sequential playback")
        
        # Write all chunks to files first
        file_paths = []
        for i, (audio_data, chunk_text) in enumerate(zip(chunk_audio_data, chunks)):
            filename = f"{provider.value}_chunk_{i+1}.{config.audio_format}"
            file_path = temp_dir / filename
            
            with open(file_path, "wb") as f:
                f.write(audio_data)
            
            file_paths.append((str(file_path), chunk_text))
        
        # Queue all chunks in order
        for i, (file_path, chunk_text) in enumerate(file_paths):
            logger.info(f"Adding chunk {i+1}/{len(file_paths)} to queue: {file_path}")
            await audio_queue_manager.add_to_queue(
                file_path=file_path,
                voice=voice,
                text=chunk_text[:100],  # Preview of chunk
                session_id=session_id,
                playback_id=playback_id,
                metadata={"source": "sequential_fallback", "chunk_number": i + 1},
            )

# Global instance
chunking_manager = UnifiedChunkingManager() 
