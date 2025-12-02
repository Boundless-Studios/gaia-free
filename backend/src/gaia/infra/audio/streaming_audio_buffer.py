"""Streaming audio buffer for ultra-responsive TTS generation.

Buffers incoming text chunks and triggers audio generation at semantic boundaries
(sentence endings, natural breaks) to minimize latency while maintaining natural prosody.
"""

import asyncio
import logging
import re
import uuid
from typing import Dict, Any, Optional, Callable, List

from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter

logger = logging.getLogger(__name__)


class StreamingAudioBuffer:
    """Buffers streaming text chunks and generates audio at semantic boundaries.

    This enables ultra-responsive audio that starts playing while narrative text
    is still being generated, rather than waiting for the complete narrative.

    Features:
    - Detects sentence boundaries for natural prosody
    - Assigns sequence numbers for ordered playback
    - Fires parallel audio generation tasks
    - Broadcasts chunks as they complete
    """

    def __init__(
        self,
        session_id: str,
        broadcaster,
        tts_generator: Callable[[str, str, bool], Any],
        playback_group: str = "narrative",
    ):
        """Initialize streaming audio buffer.

        Args:
            session_id: Campaign/session identifier
            broadcaster: WebSocket broadcaster for audio chunks
            tts_generator: Async function that generates audio (text, session_id, return_artifact) -> artifact
            playback_group: Group identifier for frontend playback sequencing
        """
        self.session_id = session_id
        self.tts_generator = tts_generator
        self.playback_group = playback_group

        self.buffer = ""
        self.full_text = ""  # Accumulate all text for database storage
        self.sequence_number = 0
        self.pending_tasks: List[asyncio.Task] = []
        self.finalized = False

        # Generate unique response ID to scope audio sequences per DM response
        # This prevents watermark collisions when new responses start mid-playback
        self.response_id = str(uuid.uuid4())

        # Use shared playback request writer for lifecycle management
        self.writer = PlaybackRequestWriter(
            session_id=session_id,
            broadcaster=broadcaster,
            playback_group=playback_group,
        )

    async def add_chunk(self, chunk: str, is_final: bool = False) -> None:
        """Add a text chunk and generate audio if semantic boundary reached.

        Args:
            chunk: Text chunk from streaming generation
            is_final: Whether this is the final chunk
        """
        if self.finalized:
            logger.warning(
                "StreamingAudioBuffer for session %s received chunk after finalization",
                self.session_id
            )
            return

        self.buffer += chunk
        self.full_text += chunk  # Accumulate full text for storage

        logger.debug(
            "[AUDIO_DEBUG] 📝 Text chunk added | session=%s buffer_len=%d full_text_len=%d buffer_preview='%s'",
            self.session_id,
            len(self.buffer),
            len(self.full_text),
            self.buffer[-80:].replace('\n', ' ') if len(self.buffer) > 80 else self.buffer.replace('\n', ' '),
        )

        # Check for semantic break or final chunk
        if self._has_semantic_break() or is_final:
            sentences = self._extract_complete_sentences()

            if sentences:
                # Capture sequence number NOW (before incrementing) to avoid race condition
                seq = self.sequence_number
                self.sequence_number += 1

                # Fire audio generation task (non-blocking) with captured sequence
                task = asyncio.create_task(
                    self._generate_and_broadcast_audio(sentences, seq)
                )
                self.pending_tasks.append(task)

                logger.debug(
                    "[AUDIO_DEBUG] 🎤 Queued audio generation | session=%s seq=%d text_preview='%s' pending_tasks=%d",
                    self.session_id,
                    seq,
                    sentences[:100].replace('\n', ' '),
                    len(self.pending_tasks)
                )

        if is_final:
            self.finalized = True
            # Process any remaining buffer
            if self.buffer.strip():
                # Capture sequence number NOW (before incrementing)
                seq = self.sequence_number
                self.sequence_number += 1

                task = asyncio.create_task(
                    self._generate_and_broadcast_audio(self.buffer, seq)
                )
                self.pending_tasks.append(task)
                logger.debug(
                    "[AUDIO_DEBUG] 🏁 Queued FINAL audio chunk | session=%s seq=%d text_preview='%s' pending_tasks=%d",
                    self.session_id,
                    seq,
                    self.buffer[:100].replace('\n', ' '),
                    len(self.pending_tasks)
                )
                self.buffer = ""

    def _has_semantic_break(self) -> bool:
        """Check if buffer contains a sentence boundary.

        Returns:
            True if buffer ends with sentence terminator + space/newline
        """
        if len(self.buffer) < 2:
            return False

        # Check for sentence endings: ". ", "! ", "? ", ".\n", etc.
        return bool(re.search(r'[.!?][\s\n]', self.buffer))

    def _extract_complete_sentences(self) -> str:
        """Extract complete sentences from buffer, leaving remainder.

        Returns:
            Complete sentences ready for TTS
        """
        # Find the last sentence boundary
        match = None
        for match in re.finditer(r'[.!?](?=[\s\n])', self.buffer):
            pass  # Find last match

        if match:
            end_idx = match.end()
            sentences = self.buffer[:end_idx]
            self.buffer = self.buffer[end_idx:].lstrip()
            return sentences

        return ""

    async def _generate_and_broadcast_audio(self, text: str, sequence_number: int) -> None:
        """Generate audio for text and broadcast when ready.

        Args:
            text: Text to convert to speech
            sequence_number: Sequence number for this chunk (captured at task creation)
        """
        if not text.strip():
            return

        seq = sequence_number

        try:
            logger.debug(
                "[StreamAudio] Session %s: Generating audio chunk %d (%d chars): %s",
                self.session_id,
                seq,
                len(text),
                text[:80] + "..." if len(text) > 80 else text
            )

            # Generate audio artifact
            artifact = await self.tts_generator(
                text,
                self.session_id,
                return_artifact=True
            )

            if not isinstance(artifact, dict):
                logger.error(
                    "[StreamAudio] Session %s: TTS generator returned non-dict: %s",
                    self.session_id,
                    type(artifact)
                )
                return

            # Add response ID metadata for watermark collision prevention
            artifact["response_id"] = self.response_id
            artifact["chunk_number"] = seq + 1  # 1-indexed for display

            # Use writer to persist chunk, broadcast, and trigger streaming
            await self.writer.add_chunk(
                artifact=artifact,
                sequence_number=seq,
                text_preview=text,
            )

        except Exception as e:
            logger.error(
                "[StreamAudio] Session %s: Failed to generate audio chunk %d: %s",
                self.session_id,
                seq,
                e,
                exc_info=True
            )

    async def finalize(self) -> None:
        """Wait for all pending audio generation tasks to complete."""
        if not self.finalized:
            self.finalized = True

            # Process any remaining buffer
            if self.buffer.strip():
                # Capture sequence number for final chunk
                seq = self.sequence_number
                self.sequence_number += 1
                await self._generate_and_broadcast_audio(self.buffer, seq)
                self.buffer = ""

        # Wait for all tasks
        if self.pending_tasks:
            logger.debug(
                "[StreamAudio] Session %s: Waiting for %d audio generation tasks to complete",
                self.session_id,
                len(self.pending_tasks)
            )
            await asyncio.gather(*self.pending_tasks, return_exceptions=True)
            logger.debug(
                "[StreamAudio] Session %s: All audio generation tasks complete",
                self.session_id
            )

        # Finalize the writer (sets total_chunks and text in DB)
        await self.writer.finalize(text=self.full_text)
