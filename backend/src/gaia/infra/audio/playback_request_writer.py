"""Shared abstraction for managing audio playback request lifecycle.

ARCHITECTURE:
  This module provides the unified interface for persisting and broadcasting audio chunks.
  Choose the right abstraction based on your text availability:

  ┌─────────────────────────────────────────────────────────┐
  │ STREAMING TEXT (progressive generation)                 │
  │ ├─ Use: StreamingAudioBuffer                           │
  │ ├─ For: Streaming DM responses                         │
  │ └─ Features: Semantic buffering, sentence detection    │
  │             (internally uses PlaybackRequestWriter)    │
  └─────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │ COMPLETE TEXT (synchronous generation)                  │
  │ ├─ Use: PlaybackRequestWriter directly                 │
  │ ├─ For: Scene agents, sync DM, debug routes           │
  │ └─ Features: Simple persistence + broadcasting         │
  └─────────────────────────────────────────────────────────┘

Consolidates request creation, chunk persistence, broadcasting, and queue management
for both streaming DM responses and chunked scene agent audio.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional

from gaia.infra.audio.audio_playback_service import audio_playback_service

logger = logging.getLogger(__name__)


class PlaybackRequestWriter:
    """Manages playback request lifecycle for progressive audio generation.

    USAGE:
      Use this class directly when you have complete text ready for audio generation.
      For streaming text (progressive LLM responses), use StreamingAudioBuffer instead,
      which adds semantic buffering and sentence boundary detection.

    Handles:
    - Creating playback request in DB
    - Broadcasting queue updates
    - Persisting individual chunks
    - Broadcasting chunk-ready events
    - Marking request as started/completed
    - Triggering synchronized streaming
    """

    def __init__(
        self,
        session_id: str,
        broadcaster,
        playback_group: str = "narrative",
        text: Optional[str] = None,
    ):
        """Initialize playback request writer.

        Args:
            session_id: Campaign/session identifier
            broadcaster: CampaignBroadcaster instance
            playback_group: Group identifier (narrative, response, etc.)
            text: Full text that will be converted to audio (optional)
        """
        self.session_id = session_id
        self.broadcaster = broadcaster
        self.playback_group = playback_group
        self.request_id: Optional[uuid.UUID] = None
        self.stream_triggered = False
        self.chunk_count = 0

        # Create playback request in DB for persistence and queue tracking
        self.request_id = audio_playback_service.create_playback_request(
            campaign_id=session_id,
            playback_group=playback_group,
            text=text,
        )

        if self.request_id:
            logger.info(
                "[AUDIO_DEBUG] 🎯 Created playback request | session=%s request_id=%s playback_group=%s",
                session_id,
                self.request_id,
                playback_group,
            )
        else:
            logger.warning(
                "[AUDIO_DEBUG] ⚠️ Playback request not created (DB disabled) | session=%s playback_group=%s",
                session_id,
                playback_group,
            )

    async def add_chunk(
        self,
        artifact: Dict[str, Any],
        sequence_number: int,
        text_preview: Optional[str] = None,
    ) -> Optional[str]:
        """Add a chunk to the request and broadcast it.

        Args:
            artifact: Audio artifact metadata (from audio_artifact_store)
            sequence_number: 0-indexed sequence number for ordering
            text_preview: Optional text preview for debugging

        Returns:
            Chunk ID if persisted successfully, None otherwise
        """
        if not self.request_id:
            return None

        # Persist chunk to DB
        chunk_id = audio_playback_service.add_audio_chunk(
            request_id=self.request_id,
            campaign_id=self.session_id,
            artifact_id=artifact["id"],
            url=artifact["url"],
            sequence_number=sequence_number,
            mime_type=artifact["mime_type"],
            size_bytes=artifact["size_bytes"],
            storage_path=artifact["storage_path"],
            duration_sec=artifact.get("duration_sec"),
            bucket=artifact.get("bucket"),
        )

        if chunk_id:
            logger.debug(
                "[AUDIO_DEBUG] 💾 Persisted chunk to DB | request_id=%s chunk_id=%s seq=%d artifact_id=%s",
                self.request_id,
                chunk_id,
                sequence_number,
                artifact["id"],
            )

            # Add chunk to all connected users' queues
            user_ids = self.broadcaster.get_connected_user_ids(self.session_id)
            logger.info(
                "[AUDIO_DEBUG] 🔍 get_connected_user_ids returned %d users for campaign %s: %s",
                len(user_ids) if user_ids else 0,
                self.session_id,
                user_ids or "[]",
            )
            if user_ids:
                count = audio_playback_service.add_chunk_to_all_users(
                    user_ids=user_ids,
                    campaign_id=self.session_id,
                    chunk_id=chunk_id,
                    request_id=self.request_id,
                )
                logger.info(
                    "[AUDIO_DEBUG] 📊 Added chunk %s to %d user queues in campaign %s",
                    chunk_id,
                    count,
                    self.session_id,
                )

                # Broadcast simple notification that audio is available
                await self.broadcaster.broadcast_campaign_update(
                    self.session_id,
                    "audio_available",
                    {
                        "campaign_id": self.session_id,
                        "playback_group": self.playback_group,
                        "chunk_count": 1,
                    },
                )
                logger.info(
                    "[AUDIO_DEBUG] 📡 Broadcast audio_available event for campaign %s",
                    self.session_id,
                )
            else:
                logger.warning(
                    "[AUDIO_DEBUG] ⚠️ No connected users found for campaign %s - audio won't play! Check WebSocket connections.",
                    self.session_id,
                )

        logger.debug(
            "[AUDIO_DEBUG] 💾 Chunk persisted (user queue mode) | session=%s seq=%d chunk_id=%s url=%s text=%s",
            self.session_id,
            sequence_number,
            artifact["id"],
            artifact["url"][:80],
            (text_preview or "")[:80],
        )

        # Mark request as started on first chunk
        if not self.stream_triggered:
            self.stream_triggered = True
            if self.request_id:
                audio_playback_service.mark_request_started(self.request_id)
                logger.info(
                    "[AUDIO_DEBUG] 🎬 Request marked as GENERATING | request_id=%s session=%s",
                    self.request_id,
                    self.session_id,
                )

        self.chunk_count += 1
        return str(chunk_id) if chunk_id else None

    async def finalize(self, text: Optional[str] = None) -> None:
        """Mark generation complete and set total chunks and text.

        Args:
            text: Full text that was converted to audio (optional)

        This does NOT mark the request as COMPLETED - that happens when
        all chunks are played by the client (in mark_audio_played).
        """
        if self.request_id:
            # VALIDATION: Prevent finalizing requests with zero chunks
            if self.chunk_count == 0:
                logger.error(
                    "[AUDIO_DEBUG] ❌ REJECTED: Cannot finalize request with 0 chunks | request_id=%s text='%s'",
                    self.request_id,
                    (text[:80] + "...") if text and len(text) > 80 else (text or "(no text)"),
                )
                # Set total_chunks=0 so existing safety mechanisms will prevent streaming
                # and cleanup will mark as FAILED
                audio_playback_service.set_request_total_chunks(
                    self.request_id,
                    total_chunks=0,
                    text=text,
                )
                logger.warning(
                    "[AUDIO_DEBUG] 🗑️  Zero-chunk request will be cleaned up | request_id=%s",
                    self.request_id,
                )
                return

            audio_playback_service.set_request_total_chunks(
                self.request_id,
                self.chunk_count,
                text=text,
            )
            text_preview = (text[:80] + "...") if text and len(text) > 80 else (text or "(no text)")
            logger.info(
                "[AUDIO_DEBUG] ✅ QUEUED: \"%s\" | %d chunk(s) generated | session=%s",
                text_preview,
                self.chunk_count,
                self.session_id,
            )
