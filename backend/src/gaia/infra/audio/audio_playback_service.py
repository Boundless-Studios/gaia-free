"""Service for managing audio playback state in the database."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import select, update, and_
from sqlalchemy.orm import Session, selectinload

from db.src.connection import db_manager
from gaia.infra.audio.audio_models import (
    AudioPlaybackRequest,
    AudioChunk,
    UserAudioQueue,
    PlaybackStatus,
)

logger = logging.getLogger(__name__)


class AudioPlaybackService:
    """Manages audio playback state persistence in database."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._db_enabled = False
        self._db_failed_reason: Optional[str] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables for audio playback tracking."""
        if os.getenv("AUDIO_PLAYBACK_DISABLE_DB", "").lower() in {"1", "true", "yes"}:
            logger.info("Audio playback database sync disabled via environment flag")
            return

        try:
            db_manager.initialize()
            engine = getattr(db_manager, "sync_engine", None)
            if engine is None:
                logger.warning("Database engine not available; audio playback persistence disabled")
                return

            with engine.begin() as connection:
                # Create tables if they don't exist
                AudioPlaybackRequest.__table__.create(bind=connection, checkfirst=True)
                AudioChunk.__table__.create(bind=connection, checkfirst=True)
                UserAudioQueue.__table__.create(bind=connection, checkfirst=True)
                logger.info("Audio playback tables initialized successfully")

            self._db_enabled = True
        except Exception as exc:
            self._db_failed_reason = str(exc)
            logger.warning("Audio playback database initialization failed: %s", exc)
            logger.info("Audio playback will continue without persistence")

    @property
    def db_enabled(self) -> bool:
        """Check if database persistence is enabled."""
        return self._db_enabled

    def _get_session(self) -> Optional[Session]:
        """Get a database session."""
        if not self._db_enabled:
            return None
        session_factory = getattr(db_manager, "sync_session_factory", None)
        if session_factory is None:
            return None
        return session_factory()

    def create_playback_request(
        self,
        campaign_id: str,
        playback_group: str,
        text: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Optional[uuid.UUID]:
        """Create a new playback request and return its ID.

        Args:
            campaign_id: Campaign/session identifier
            playback_group: Group identifier (narrative, response, etc.)
            text: Full text that will be converted to audio (optional)
            message_id: Source message identifier for auditing/cleanup (optional)

        Returns:
            Request UUID if successful, None if database disabled
        """
        if not self._db_enabled:
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            request = AudioPlaybackRequest(
                campaign_id=campaign_id,
                playback_group=playback_group,
                status=PlaybackStatus.PENDING,
                requested_at=datetime.now(timezone.utc),
                text=text,
                message_id=message_id,
            )
            session.add(request)
            session.commit()
            request_id = request.request_id
            logger.debug(
                "[AUDIO_DB] Created playback request: %s for campaign %s, group %s, text=%s, message=%s",
                request_id,
                campaign_id,
                playback_group,
                (text[:50] + "...") if text and len(text) > 50 else text,
                message_id,
            )
            return request_id
        except Exception as exc:
            logger.error("Failed to create playback request: %s", exc)
            session.rollback()
            return None
        finally:
            session.close()

    def add_audio_chunk(
        self,
        request_id: uuid.UUID,
        campaign_id: str,
        artifact_id: str,
        url: str,
        sequence_number: int,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        duration_sec: Optional[float] = None,
        bucket: Optional[str] = None,
    ) -> Optional[uuid.UUID]:
        """Add an audio chunk to a playback request.

        Args:
            request_id: Parent playback request ID
            campaign_id: Campaign/session identifier
            artifact_id: Audio artifact ID from storage
            url: Proxy URL for client playback
            sequence_number: Order within the request
            mime_type: Audio MIME type
            size_bytes: File size in bytes
            storage_path: Path to audio file (local or GCS)
            duration_sec: Optional audio duration
            bucket: Optional GCS bucket name

        Returns:
            Chunk UUID if successful, None if database disabled
        """
        if not self._db_enabled:
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            chunk = AudioChunk(
                request_id=request_id,
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                url=url,
                sequence_number=sequence_number,
                status=PlaybackStatus.PENDING,
                mime_type=mime_type,
                size_bytes=size_bytes,
                duration_sec=duration_sec,
                storage_path=storage_path,
                bucket=bucket,
            )
            session.add(chunk)
            session.commit()
            chunk_id = chunk.chunk_id
            logger.debug(
                "[AUDIO_DB] Added chunk %s to request %s: seq=%d, url=%s",
                chunk_id,
                request_id,
                sequence_number,
                url,
            )
            return chunk_id
        except Exception as exc:
            logger.error("Failed to add audio chunk: %s", exc)
            session.rollback()
            return None
        finally:
            session.close()

    def get_pending_chunks(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get all pending audio chunks for a campaign in playback order.

        Returns chunks that are still awaiting playback even if their parent
        request has already moved into GENERATING (streaming) status. Chunks
        from COMPLETED/FAILED requests remain excluded to avoid resending audio
        that already finished or errored.

        Args:
            campaign_id: Campaign/session identifier

        Returns:
            List of chunk dictionaries ordered by request time, then sequence
        """
        if not self._db_enabled:
            return []

        session = self._get_session()
        if session is None:
            return []

        try:
            # Query pending chunks with their parent requests, ordered by submission
            # CRITICAL: Filter by request status to exclude COMPLETED/FAILED requests
            stmt = (
                select(AudioChunk)
                .join(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioChunk.campaign_id == campaign_id,
                        AudioChunk.status == PlaybackStatus.PENDING,
                        AudioPlaybackRequest.status.in_([
                            PlaybackStatus.PENDING,
                            PlaybackStatus.GENERATING,
                            PlaybackStatus.GENERATED,
                        ]),
                    )
                )
                .order_by(
                    AudioPlaybackRequest.requested_at,
                    AudioChunk.sequence_number,
                )
                .options(selectinload(AudioChunk.request))
            )

            chunks = session.execute(stmt).scalars().all()

            results = []
            for chunk in chunks:
                results.append({
                    "chunk_id": str(chunk.chunk_id),
                    "request_id": str(chunk.request_id),
                    "campaign_id": chunk.campaign_id,
                    "artifact_id": chunk.artifact_id,
                    "url": chunk.url,
                    "sequence_number": chunk.sequence_number,
                    "playback_group": chunk.request.playback_group,
                    "mime_type": chunk.mime_type,
                    "size_bytes": chunk.size_bytes,
                    "duration_sec": chunk.duration_sec,
                    "storage_path": chunk.storage_path,
                    "bucket": chunk.bucket,
                    "requested_at": chunk.request.requested_at.isoformat(),
                })

            logger.debug(
                "[AUDIO_DB] Found %d pending chunks (from PENDING requests only) for campaign %s",
                len(results),
                campaign_id,
            )
            return results
        except Exception as exc:
            logger.error("Failed to get pending chunks: %s", exc)
            return []
        finally:
            session.close()

    def get_chunks_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific request, regardless of status.

        Used by synchronized streaming to get the exact chunks for a request.
        This ensures the frontend receives the correct chunk IDs to acknowledge
        when the stream completes.

        Args:
            request_id: Request UUID as string

        Returns:
            List of chunk dictionaries ordered by sequence number
        """
        if not self._db_enabled:
            return []

        session = self._get_session()
        if session is None:
            return []

        try:
            request_uuid = uuid.UUID(request_id)
            stmt = (
                select(AudioChunk)
                .where(AudioChunk.request_id == request_uuid)
                .order_by(AudioChunk.sequence_number)
                .options(selectinload(AudioChunk.request))
            )

            chunks = session.execute(stmt).scalars().all()

            results = []
            for chunk in chunks:
                results.append({
                    "chunk_id": str(chunk.chunk_id),
                    "request_id": str(chunk.request_id),
                    "campaign_id": chunk.campaign_id,
                    "artifact_id": chunk.artifact_id,
                    "url": chunk.url,
                    "sequence_number": chunk.sequence_number,
                    "playback_group": chunk.request.playback_group,
                    "mime_type": chunk.mime_type,
                    "size_bytes": chunk.size_bytes,
                    "duration_sec": chunk.duration_sec,
                    "storage_path": chunk.storage_path,
                    "bucket": chunk.bucket,
                    "requested_at": chunk.request.requested_at.isoformat(),
                })

            logger.debug(
                "[AUDIO_DB] Found %d chunks for request %s",
                len(results),
                request_id,
            )
            return results
        except Exception as exc:
            logger.error("Failed to get chunks for request %s: %s", request_id, exc)
            return []
        finally:
            session.close()

    def mark_chunk_played(self, chunk_id: str) -> bool:
        """Mark an audio chunk as played.

        Args:
            chunk_id: Chunk UUID as string

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            chunk_uuid = uuid.UUID(chunk_id)
            stmt = (
                update(AudioChunk)
                .where(AudioChunk.chunk_id == chunk_uuid)
                .values(
                    status=PlaybackStatus.PLAYED,
                    played_at=datetime.now(timezone.utc),
                )
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.debug("[AUDIO_DB] Marked chunk %s as played", chunk_id)
                return True
            else:
                logger.warning("[AUDIO_DB] Chunk %s not found", chunk_id)
                return False
        except Exception as exc:
            logger.error("Failed to mark chunk as played: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    # ===== User Audio Queue Management =====

    def add_chunk_to_user_queue(
        self,
        user_id: str,
        campaign_id: str,
        chunk_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> Optional[uuid.UUID]:
        """Add a chunk to a user's playback queue.

        Args:
            user_id: User identifier (email or user_id)
            campaign_id: Campaign identifier
            chunk_id: Audio chunk UUID
            request_id: Parent playback request UUID

        Returns:
            Queue entry UUID if successful, None otherwise
        """
        if not self._db_enabled:
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            queue_entry = UserAudioQueue(
                user_id=user_id,
                campaign_id=campaign_id,
                chunk_id=chunk_id,
                request_id=request_id,
                queued_at=datetime.now(timezone.utc),
            )
            session.add(queue_entry)
            session.commit()
            queue_id = queue_entry.queue_id
            logger.debug(
                "[USER_QUEUE] Added chunk %s to queue for user %s in campaign %s",
                chunk_id,
                user_id,
                campaign_id,
            )
            return queue_id
        except Exception as exc:
            logger.error("Failed to add chunk to user queue: %s", exc)
            session.rollback()
            return None
        finally:
            session.close()

    def add_chunk_to_all_users(
        self,
        user_ids: List[str],
        campaign_id: str,
        chunk_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> int:
        """Add a chunk to multiple users' queues (bulk operation).

        Args:
            user_ids: List of user identifiers
            campaign_id: Campaign identifier
            chunk_id: Audio chunk UUID
            request_id: Parent playback request UUID

        Returns:
            Number of queue entries created
        """
        if not self._db_enabled:
            return 0

        session = self._get_session()
        if session is None:
            return 0

        try:
            queue_entries = [
                UserAudioQueue(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    chunk_id=chunk_id,
                    request_id=request_id,
                    queued_at=datetime.now(timezone.utc),
                )
                for user_id in user_ids
            ]
            session.add_all(queue_entries)
            session.commit()
            count = len(queue_entries)
            logger.debug(
                "[USER_QUEUE] Added chunk %s to queues for %d users in campaign %s",
                chunk_id,
                count,
                campaign_id,
            )
            return count
        except Exception as exc:
            logger.error("Failed to add chunk to user queues: %s", exc)
            session.rollback()
            return 0
        finally:
            session.close()

    def get_user_pending_queue(
        self, user_id: str, campaign_id: str
    ) -> List[Dict[str, Any]]:
        """Get all pending audio chunks for a user in a campaign.

        Returns chunks that have not been played yet, ordered by request time
        and sequence number. This is what the client GETs on connect/reconnect.

        Args:
            user_id: User identifier
            campaign_id: Campaign identifier

        Returns:
            List of chunk dictionaries with queue metadata
        """
        if not self._db_enabled:
            return []

        session = self._get_session()
        if session is None:
            return []

        try:
            # Query user's pending queue entries with chunk and request data
            stmt = (
                select(UserAudioQueue)
                .join(AudioChunk, UserAudioQueue.chunk_id == AudioChunk.chunk_id)
                .join(
                    AudioPlaybackRequest,
                    UserAudioQueue.request_id == AudioPlaybackRequest.request_id,
                )
                .where(
                    and_(
                        UserAudioQueue.user_id == user_id,
                        UserAudioQueue.campaign_id == campaign_id,
                        UserAudioQueue.played_at.is_(None),  # Not played yet
                    )
                )
                .order_by(
                    AudioPlaybackRequest.requested_at,
                    AudioChunk.sequence_number,
                )
                .options(
                    selectinload(UserAudioQueue.chunk),
                    selectinload(UserAudioQueue.request),
                )
            )

            queue_entries = session.execute(stmt).scalars().all()

            results = []
            for entry in queue_entries:
                chunk = entry.chunk
                request = entry.request
                results.append({
                    "queue_id": str(entry.queue_id),
                    "chunk_id": str(chunk.chunk_id),
                    "request_id": str(request.request_id),
                    "url": chunk.url,
                    "sequence_number": chunk.sequence_number,
                    "playback_group": request.playback_group,
                    "mime_type": chunk.mime_type,
                    "size_bytes": chunk.size_bytes,
                    "duration_sec": chunk.duration_sec,
                    "queued_at": entry.queued_at.isoformat(),
                    "delivered_at": entry.delivered_at.isoformat() if entry.delivered_at else None,
                })

            logger.debug(
                "[USER_QUEUE] Found %d pending chunks for user %s in campaign %s",
                len(results),
                user_id,
                campaign_id,
            )
            return results
        except Exception as exc:
            logger.error("Failed to get user pending queue: %s", exc)
            return []
        finally:
            session.close()

    def mark_chunk_delivered_to_user(self, queue_id: str) -> bool:
        """Mark a chunk as delivered to a user.

        Args:
            queue_id: Queue entry UUID as string

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            queue_uuid = uuid.UUID(queue_id)
            stmt = (
                update(UserAudioQueue)
                .where(UserAudioQueue.queue_id == queue_uuid)
                .values(delivered_at=datetime.now(timezone.utc))
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.debug("[USER_QUEUE] Marked queue entry %s as delivered", queue_id)
                return True
            else:
                logger.warning("[USER_QUEUE] Queue entry %s not found", queue_id)
                return False
        except Exception as exc:
            logger.error("Failed to mark chunk delivered: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    def mark_chunk_played_by_user(self, queue_id: str) -> bool:
        """Mark a chunk as played by a user.

        Args:
            queue_id: Queue entry UUID as string

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            queue_uuid = uuid.UUID(queue_id)
            stmt = (
                update(UserAudioQueue)
                .where(UserAudioQueue.queue_id == queue_uuid)
                .values(played_at=datetime.now(timezone.utc))
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.debug("[USER_QUEUE] Marked queue entry %s as played", queue_id)

                # Check if all chunks for this user+request are now played
                # Fetch the queue entry to get request_id and user_id
                queue_entry = session.query(UserAudioQueue).filter_by(queue_id=queue_uuid).first()
                if queue_entry:
                    request_id = queue_entry.request_id
                    user_id = queue_entry.user_id

                    # Count total and played chunks for this user+request
                    total_chunks = session.query(UserAudioQueue).filter_by(
                        request_id=request_id,
                        user_id=user_id
                    ).count()

                    played_chunks = session.query(UserAudioQueue).filter_by(
                        request_id=request_id,
                        user_id=user_id
                    ).filter(UserAudioQueue.played_at.isnot(None)).count()

                    logger.debug(
                        "[USER_QUEUE] Request completion check | request_id=%s user=%s played=%d/%d",
                        request_id, user_id, played_chunks, total_chunks
                    )

                    # If all chunks played, mark request as completed
                    if total_chunks > 0 and played_chunks == total_chunks:
                        logger.info(
                            "[USER_QUEUE] All chunks played by user %s | request_id=%s - marking as COMPLETED",
                            user_id, request_id
                        )
                        self.mark_request_completed(request_id, total_chunks)

                return True
            else:
                logger.warning("[USER_QUEUE] Queue entry %s not found", queue_id)
                return False
        except Exception as exc:
            logger.error("Failed to mark chunk played: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    def cleanup_played_queue_entries(self, campaign_id: str, days: int = 7) -> int:
        """Remove played queue entries older than specified days.

        Args:
            campaign_id: Campaign identifier
            days: Remove entries played more than this many days ago

        Returns:
            Number of entries removed
        """
        if not self._db_enabled:
            return 0

        session = self._get_session()
        if session is None:
            return 0

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = (
                select(UserAudioQueue)
                .where(
                    and_(
                        UserAudioQueue.campaign_id == campaign_id,
                        UserAudioQueue.played_at.isnot(None),
                        UserAudioQueue.played_at < cutoff,
                    )
                )
            )
            old_entries = session.execute(stmt).scalars().all()

            for entry in old_entries:
                session.delete(entry)

            session.commit()
            count = len(old_entries)
            logger.info(
                "[USER_QUEUE] Cleaned up %d played queue entries older than %d days for campaign %s",
                count,
                days,
                campaign_id,
            )
            return count
        except Exception as exc:
            logger.error("Failed to cleanup queue entries: %s", exc)
            session.rollback()
            return 0
        finally:
            session.close()

    # ===== End User Audio Queue Management =====

    def mark_request_started(self, request_id: uuid.UUID) -> bool:
        """Mark a playback request as started (streaming).

        IMPORTANT: GENERATING status means "generation has started", NOT "chunks are ready".
        This allows the request to move to GENERATING immediately when generation begins,
        even if chunks haven't been created yet. This prevents race conditions where:
        1. Generation starts
        2. mark_request_started() is called
        3. First chunk hasn't been persisted yet
        4. Old validation would reject the status change

        The frontend should show "Generating..." for GENERATING requests, not "Playing".
        Actual playback begins when chunks are delivered via WebSocket.

        Args:
            request_id: Request UUID

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            # Check if request exists (no chunk validation - see docstring)
            check_stmt = select(AudioPlaybackRequest).where(
                AudioPlaybackRequest.request_id == request_id
            )
            req = session.execute(check_stmt).scalar_one_or_none()

            if not req:
                logger.warning("[AUDIO_DB] Request %s not found", request_id)
                return False

            # Mark as GENERATING without chunk validation
            stmt = (
                update(AudioPlaybackRequest)
                .where(AudioPlaybackRequest.request_id == request_id)
                .values(
                    status=PlaybackStatus.GENERATING,
                    started_at=datetime.now(timezone.utc),
                )
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.info(
                    "[AUDIO_DEBUG] 🎬 Marked request %s as GENERATING | total_chunks=%s",
                    request_id,
                    req.total_chunks,
                )
                return True
            else:
                logger.warning("[AUDIO_DB] Request %s not found", request_id)
                return False
        except Exception as exc:
            logger.error("Failed to mark request as started: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    def set_request_total_chunks(
        self,
        request_id: uuid.UUID,
        total_chunks: int,
        text: Optional[str] = None,
    ) -> bool:
        """Set the total_chunks count and mark request as GENERATED.

        When total_chunks > 0, marks the request as GENERATED to indicate
        that chunk generation is complete and the request is ready for playback.
        When total_chunks = 0, does not change status (allows cleanup logic to mark as FAILED).

        Args:
            request_id: Request UUID
            total_chunks: Total number of chunks in this request
            text: Full text that was converted to audio (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            # Build values dict dynamically
            values = {"total_chunks": total_chunks}
            if text is not None:
                values["text"] = text

            # Mark as GENERATED when chunks are finalized (unless total_chunks=0)
            if total_chunks > 0:
                values["status"] = PlaybackStatus.GENERATED.value

            stmt = (
                update(AudioPlaybackRequest)
                .where(AudioPlaybackRequest.request_id == request_id)
                .values(**values)
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                text_preview = (text[:40] + "...") if text and len(text) > 40 else text
                status_msg = f", status=GENERATED" if total_chunks > 0 else ""
                logger.debug(
                    "[AUDIO_DEBUG] 📊 Set total_chunks=%d, text=%s%s for request %s",
                    total_chunks,
                    text_preview,
                    status_msg,
                    request_id
                )
                return True
            else:
                logger.warning("[AUDIO_DB] Request %s not found", request_id)
                return False
        except Exception as exc:
            logger.error("Failed to set total_chunks: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    def mark_request_completed(self, request_id: uuid.UUID, total_chunks: int) -> bool:
        """Mark a playback request as completed.

        Validates chunk sequences before marking as COMPLETED:
        - Checks that all sequence numbers from 0 to total_chunks-1 exist
        - Prevents marking as COMPLETED if there are gaps in the sequence

        Args:
            request_id: Request UUID
            total_chunks: Total number of chunks in this request

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            # Validate chunk sequence before marking as COMPLETED
            if total_chunks > 0:
                # Get all sequence numbers for this request
                seq_stmt = (
                    select(AudioChunk.sequence_number)
                    .where(AudioChunk.request_id == request_id)
                    .order_by(AudioChunk.sequence_number)
                )
                sequence_numbers = session.execute(seq_stmt).scalars().all()

                # Check for gaps or missing chunks
                expected_sequences = set(range(total_chunks))
                actual_sequences = set(sequence_numbers)

                if expected_sequences != actual_sequences:
                    missing = expected_sequences - actual_sequences
                    extra = actual_sequences - expected_sequences

                    logger.warning(
                        "[AUDIO_DB] ⚠️  Sequence validation found inconsistencies (allowing completion anyway) | "
                        "request_id=%s expected_chunks=%d actual_chunks=%d missing=%s extra=%s",
                        request_id,
                        total_chunks,
                        len(actual_sequences),
                        sorted(missing) if missing else "none",
                        sorted(extra) if extra else "none",
                    )

            stmt = (
                update(AudioPlaybackRequest)
                .where(AudioPlaybackRequest.request_id == request_id)
                .values(
                    status=PlaybackStatus.COMPLETED,
                    completed_at=datetime.now(timezone.utc),
                    total_chunks=total_chunks,
                )
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.info(
                    "[AUDIO_DEBUG] ✅ Marked request %s as COMPLETED (total_chunks=%d, validated sequence)",
                    request_id,
                    total_chunks
                )
                return True
            else:
                logger.warning("[AUDIO_DB] Request %s not found", request_id)
                return False
        except Exception as exc:
            logger.error("Failed to mark request as completed: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    def cancel_request(self, request_id: uuid.UUID) -> bool:
        """Cancel a playback request by marking it as FAILED.

        This allows the frontend to explicitly stop playback instead of relying on timeouts.
        Useful for "skip" or "stop" buttons.

        Args:
            request_id: Request UUID to cancel

        Returns:
            True if successful, False otherwise
        """
        if not self._db_enabled:
            return False

        session = self._get_session()
        if session is None:
            return False

        try:
            stmt = (
                update(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.request_id == request_id,
                        AudioPlaybackRequest.status.in_([
                            PlaybackStatus.PENDING,
                            PlaybackStatus.GENERATING,
                            PlaybackStatus.GENERATED,
                        ])
                    )
                )
                .values(
                    status=PlaybackStatus.FAILED,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.info("[AUDIO_DB] ⏹️  Cancelled request %s", request_id)
                return True
            else:
                logger.debug("[AUDIO_DB] Request %s not found or already completed/failed", request_id)
                return False
        except Exception as exc:
            logger.error("Failed to cancel request: %s", exc)
            session.rollback()
            return False
        finally:
            session.close()

    def get_playback_queue(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get all playback requests for a campaign ordered by submission.

        Args:
            campaign_id: Campaign/session identifier

        Returns:
            List of request dictionaries with status and chunk info
        """
        if not self._db_enabled:
            return []

        session = self._get_session()
        if session is None:
            return []

        try:
            stmt = (
                select(AudioPlaybackRequest)
                .where(AudioPlaybackRequest.campaign_id == campaign_id)
                .order_by(AudioPlaybackRequest.requested_at)
                .options(selectinload(AudioPlaybackRequest.chunks))
            )

            requests = session.execute(stmt).scalars().all()

            results = []
            for request in requests:
                chunk_count = len(request.chunks)
                played_count = sum(1 for chunk in request.chunks if chunk.status == PlaybackStatus.PLAYED)

                results.append({
                    "request_id": str(request.request_id),
                    "campaign_id": request.campaign_id,
                    "playback_group": request.playback_group,
                    "status": request.status.value,
                    "chunk_count": chunk_count,
                    "played_count": played_count,
                    "requested_at": request.requested_at.isoformat(),
                    "started_at": request.started_at.isoformat() if request.started_at else None,
                    "completed_at": request.completed_at.isoformat() if request.completed_at else None,
                })

            logger.debug(
                "[AUDIO_DB] Found %d requests for campaign %s",
                len(results),
                campaign_id,
            )
            return results
        except Exception as exc:
            logger.error("Failed to get playback queue: %s", exc)
            return []
        finally:
            session.close()

    def get_current_request(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get the currently streaming request for a campaign.

        Args:
            campaign_id: Campaign/session identifier

        Returns:
            Request dictionary if found, None otherwise
        """
        if not self._db_enabled:
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            stmt = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.status.in_([
                            PlaybackStatus.GENERATING,
                            PlaybackStatus.GENERATED,
                        ]),
                    )
                )
                .order_by(AudioPlaybackRequest.requested_at.asc())  # Get oldest first
                .options(selectinload(AudioPlaybackRequest.chunks))
            )

            request = session.execute(stmt).scalars().first()  # Get first, handle multiples gracefully

            if request is None:
                return None

            chunk_count = len(request.chunks)
            played_count = sum(1 for chunk in request.chunks if chunk.status == PlaybackStatus.PLAYED)

            return {
                "request_id": str(request.request_id),
                "campaign_id": request.campaign_id,
                "playback_group": request.playback_group,
                "status": request.status.value,
                "chunk_count": chunk_count,
                "played_count": played_count,
                "requested_at": request.requested_at.isoformat(),
                "started_at": request.started_at.isoformat() if request.started_at else None,
            }
        except Exception as exc:
            logger.error("Failed to get current request: %s", exc)
            return None
        finally:
            session.close()

    def get_next_pending_request(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get the next pending audio request for a campaign, ordered by creation time.

        This supports automatic queue advancement - when current playback completes,
        frontend can fetch and start the next pending request.

        Args:
            campaign_id: Campaign/session identifier

        Returns:
            Request dictionary with metadata and chunk_ids if found, None otherwise
        """
        if not self._db_enabled:
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            # CLEANUP: First, detect and mark any stuck requests as FAILED
            # (requests with total_chunks=None that were created more than 5 minutes ago)
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)

            cleanup_stmt = (
                update(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.total_chunks == None,
                        AudioPlaybackRequest.requested_at < cutoff_time,
                    )
                )
                .values(
                    status=PlaybackStatus.FAILED,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            cleanup_result = session.execute(cleanup_stmt)
            if cleanup_result.rowcount > 0:
                session.commit()
                logger.warning(
                    "[AUDIO_DEBUG] 🧹 AUTO-CLEANUP: Marked %d stuck request(s) as FAILED (total_chunks=None, age>5min) | campaign=%s",
                    cleanup_result.rowcount,
                    campaign_id,
                )

            # CLEANUP: Also detect requests stuck in GENERATING/GENERATED status
            # (marked as GENERATING/GENERATED but no chunks played in 3+ minutes - indicates frontend never connected or crashed)
            streaming_cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)

            # Find GENERATING/GENERATED requests older than threshold
            streaming_check = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.status.in_([
                            PlaybackStatus.GENERATING,
                            PlaybackStatus.GENERATED,
                        ]),
                        AudioPlaybackRequest.started_at < streaming_cutoff,
                    )
                )
                .options(selectinload(AudioPlaybackRequest.chunks))
            )

            stuck_streaming = session.execute(streaming_check).scalars().all()
            stuck_count = 0

            for req in stuck_streaming:
                # Check if ANY chunks have been played
                has_progress = any(chunk.played_at is not None for chunk in req.chunks)

                if not has_progress:
                    # No chunks played - frontend never connected or crashed
                    req.status = PlaybackStatus.FAILED
                    req.completed_at = datetime.now(timezone.utc)
                    stuck_count += 1
                    logger.warning(
                        "[AUDIO_DEBUG] 🧹 AUTO-CLEANUP: Marking GENERATING/GENERATED request as FAILED (no playback progress in 3min) | request_id=%s text='%s'",
                        req.request_id,
                        (req.text[:80] + "...") if req.text and len(req.text) > 80 else (req.text or "(no text)"),
                    )

            if stuck_count > 0:
                session.commit()
                logger.warning(
                    "[AUDIO_DEBUG] 🧹 AUTO-CLEANUP: Marked %d GENERATING request(s) as FAILED (no progress) | campaign=%s",
                    stuck_count,
                    campaign_id,
                )

            stmt = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.status == PlaybackStatus.PENDING,
                    )
                )
                .order_by(AudioPlaybackRequest.requested_at)  # Oldest first (FIFO queue)
                .options(selectinload(AudioPlaybackRequest.chunks))
            )

            request = session.execute(stmt).first()

            if request is None:
                return None

            # Extract the request object from the row
            request_obj = request[0]

            # VALIDATION: Skip requests with zero chunks
            if len(request_obj.chunks) == 0:
                if request_obj.total_chunks == 0:
                    # Intentionally invalid request (finalized with 0 chunks) - mark as FAILED
                    logger.warning(
                        "[AUDIO_DEBUG] ⚠️ Marking invalid request as FAILED | request_id=%s total_chunks=0",
                        request_obj.request_id,
                    )
                    request_obj.status = PlaybackStatus.FAILED
                    request_obj.completed_at = datetime.now(timezone.utc)
                    session.commit()
                    # Recursively get next request
                    return self.get_next_pending_request(campaign_id)
                else:
                    # Request is still generating (total_chunks=None) - skip for now, don't fail
                    logger.info(
                        "[AUDIO_DEBUG] ⏸️  Skipping request still generating chunks | request_id=%s total_chunks=%s (will retry on next auto-advance)",
                        request_obj.request_id,
                        request_obj.total_chunks,
                    )
                    # Return None to stop auto-advance and let the request finish generating
                    return None

            # Also check if total_chunks=0 but somehow has chunks (shouldn't happen)
            if request_obj.total_chunks == 0:
                logger.warning(
                    "[AUDIO_DEBUG] ⚠️ Marking invalid request as FAILED | request_id=%s total_chunks=0 but has %d chunks",
                    request_obj.request_id,
                    len(request_obj.chunks),
                )
                request_obj.status = PlaybackStatus.FAILED
                request_obj.completed_at = datetime.now(timezone.utc)
                session.commit()
                # Recursively get next request
                return self.get_next_pending_request(campaign_id)

            # Get chunk IDs ordered by sequence number
            chunk_ids = [
                str(chunk.chunk_id)
                for chunk in sorted(request_obj.chunks, key=lambda c: c.sequence_number)
            ]

            return {
                "request_id": str(request_obj.request_id),
                "campaign_id": request_obj.campaign_id,
                "playback_group": request_obj.playback_group,
                "status": request_obj.status.value,
                "chunk_count": len(request_obj.chunks),
                "chunk_ids": chunk_ids,
                "requested_at": request_obj.requested_at.isoformat(),
                "text": request_obj.text,  # Include text for debug logging
            }
        except Exception as exc:
            logger.error("Failed to get next pending request: %s", exc)
            return None
        finally:
            session.close()

    def get_queue_status(self, campaign_id: str) -> Dict[str, Any]:
        """Get detailed status of audio playback queue.

        Returns:
            Dictionary with:
                - currently_playing: Dict with request info if GENERATING, None otherwise
                - pending_requests: List of pending request dicts
                - total_pending_requests: int
                - total_pending_chunks: int
                - status_message: str - Human-readable status
        """
        if not self._db_enabled:
            return {
                "currently_playing": None,
                "pending_requests": [],
                "total_pending_requests": 0,
                "total_pending_chunks": 0,
                "status_message": "Database disabled - queue status unavailable",
            }

        session = self._get_session()
        if session is None:
            return {
                "currently_playing": None,
                "pending_requests": [],
                "total_pending_requests": 0,
                "total_pending_chunks": 0,
                "status_message": "Database unavailable - queue status unavailable",
            }

        try:
            # CLEANUP: Run the same cleanup as get_next_pending_request
            # This ensures stuck requests are detected even when just checking queue status
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)

            # Cleanup stuck requests with total_chunks=None
            cleanup_stmt = (
                update(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.total_chunks == None,
                        AudioPlaybackRequest.requested_at < cutoff_time,
                    )
                )
                .values(
                    status=PlaybackStatus.FAILED,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            cleanup_result = session.execute(cleanup_stmt)
            if cleanup_result.rowcount > 0:
                session.commit()

            # Cleanup requests stuck in GENERATING/GENERATED status
            streaming_cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)
            streaming_check = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.status.in_([
                            PlaybackStatus.GENERATING,
                            PlaybackStatus.GENERATED,
                        ]),
                        AudioPlaybackRequest.started_at < streaming_cutoff,
                    )
                )
                .options(selectinload(AudioPlaybackRequest.chunks))
            )
            stuck_streaming = session.execute(streaming_check).scalars().all()
            stuck_count = 0
            for req in stuck_streaming:
                has_progress = any(chunk.played_at is not None for chunk in req.chunks)
                if not has_progress:
                    req.status = PlaybackStatus.FAILED
                    req.completed_at = datetime.now(timezone.utc)
                    stuck_count += 1
            if stuck_count > 0:
                session.commit()

            # Get currently GENERATING/GENERATED request (oldest one if multiple exist)
            streaming_stmt = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.status.in_([
                            PlaybackStatus.GENERATING,
                            PlaybackStatus.GENERATED,
                        ]),
                    )
                )
                .options(selectinload(AudioPlaybackRequest.chunks))
                .order_by(AudioPlaybackRequest.requested_at)
                .limit(1)
            )
            streaming_result = session.execute(streaming_stmt).scalars().first()

            # CLEANUP: Detect and fix stuck GENERATING/GENERATED requests with 0 total_chunks
            if streaming_result and (streaming_result.total_chunks is None or streaming_result.total_chunks == 0):
                logger.warning(
                    "[AUDIO_DEBUG] 🧹 CLEANUP: Found stuck GENERATING/GENERATED request with %s total_chunks | request_id=%s",
                    streaming_result.total_chunks,
                    streaming_result.request_id,
                )
                # Mark as FAILED to remove from queue
                streaming_result.status = PlaybackStatus.FAILED
                streaming_result.completed_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(
                    "[AUDIO_DEBUG] 🧹 CLEANUP: Marked stuck request as FAILED | request_id=%s",
                    streaming_result.request_id,
                )
                streaming_result = None  # Treat as if no request is playing

            currently_playing = None
            if streaming_result:
                text_preview = (streaming_result.text[:40] + "...") if streaming_result.text and len(streaming_result.text) > 40 else streaming_result.text
                currently_playing = {
                    "request_id": str(streaming_result.request_id),
                    "chunk_count": len(streaming_result.chunks),
                    "total_chunks": streaming_result.total_chunks or len(streaming_result.chunks),
                    "text": streaming_result.text,
                    "text_preview": text_preview,
                }

            # Get all PENDING requests
            pending_stmt = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.campaign_id == campaign_id,
                        AudioPlaybackRequest.status == PlaybackStatus.PENDING,
                    )
                )
                .options(selectinload(AudioPlaybackRequest.chunks))
                .order_by(AudioPlaybackRequest.requested_at)
            )
            pending_results = session.execute(pending_stmt).scalars().all()

            pending_requests = []
            total_pending_chunks = 0
            for req in pending_results:
                chunk_count = len(req.chunks)
                total_pending_chunks += chunk_count
                text_preview = (req.text[:40] + "...") if req.text and len(req.text) > 40 else req.text
                pending_requests.append({
                    "request_id": str(req.request_id),
                    "chunk_count": chunk_count,
                    "text": req.text,
                    "text_preview": text_preview,
                })

            # Build status message
            if currently_playing:
                text_part = f'"{currently_playing["text_preview"]}"' if currently_playing.get("text_preview") else "unknown text"
                status = f"Currently playing {text_part}, chunk ? of {currently_playing['total_chunks']}. "
            else:
                status = "No audio currently playing. "

            if pending_requests:
                status += f"{len(pending_requests)} request(s) ({total_pending_chunks} chunk(s)) queued."
            else:
                status += "Queue is empty."

            # Log comprehensive queue status
            logger.info(
                "[AUDIO_DEBUG] 🎵 QUEUE STATUS | campaign=%s",
                campaign_id,
            )
            if currently_playing:
                logger.info(
                    "[AUDIO_DEBUG]   ▶️  CURRENTLY PLAYING: request_id=%s chunks=%d/%d text='%s'",
                    currently_playing["request_id"],
                    len(streaming_result.chunks) if streaming_result else 0,
                    currently_playing["total_chunks"],
                    (currently_playing.get("text") or "(no text)")[:200],
                )
            else:
                logger.info("[AUDIO_DEBUG]   ⚪ NO AUDIO PLAYING")

            if pending_requests:
                logger.info(
                    "[AUDIO_DEBUG]   📋 PENDING QUEUE: %d request(s), %d total chunk(s)",
                    len(pending_requests),
                    total_pending_chunks,
                )
                for idx, req in enumerate(pending_requests, 1):
                    logger.info(
                        "[AUDIO_DEBUG]     %d. request_id=%s chunks=%d text='%s'",
                        idx,
                        req["request_id"],
                        req["chunk_count"],
                        (req.get("text") or "(no text)")[:150],
                    )
            else:
                logger.info("[AUDIO_DEBUG]   📋 QUEUE EMPTY")

            return {
                "currently_playing": currently_playing,
                "pending_requests": pending_requests,
                "total_pending_requests": len(pending_requests),
                "total_pending_chunks": total_pending_chunks,
                "status_message": status,
            }

        except Exception as exc:
            logger.error("Failed to get queue status: %s", exc)
            return {
                "currently_playing": None,
                "pending_requests": [],
                "total_pending_requests": 0,
                "total_pending_chunks": 0,
                "status_message": f"Error retrieving queue status: {exc}",
            }
        finally:
            session.close()

    def get_request_for_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Find the parent playback request for a chunk.

        Args:
            chunk_id: Chunk UUID as string

        Returns:
            Request dictionary with all chunks if found, None otherwise
        """
        if not self._db_enabled:
            return None

        session = self._get_session()
        if session is None:
            return None

        try:
            chunk_uuid = uuid.UUID(chunk_id)
            stmt = (
                select(AudioChunk)
                .where(AudioChunk.chunk_id == chunk_uuid)
                .options(selectinload(AudioChunk.request).selectinload(AudioPlaybackRequest.chunks))
            )

            chunk = session.execute(stmt).scalar_one_or_none()

            if chunk is None or chunk.request is None:
                return None

            request = chunk.request
            chunk_count = len(request.chunks)
            played_count = sum(1 for c in request.chunks if c.status == PlaybackStatus.PLAYED)

            return {
                "request_id": str(request.request_id),
                "campaign_id": request.campaign_id,
                "playback_group": request.playback_group,
                "status": request.status.value,
                "chunk_count": chunk_count,
                "played_count": played_count,
                "total_chunks": request.total_chunks,
                "all_chunks_played": played_count == chunk_count,
            }
        except Exception as exc:
            logger.error("Failed to get request for chunk: %s", exc)
            return None
        finally:
            session.close()

    def cleanup_old_chunks(self, campaign_id: str, days: int = 7) -> int:
        """Delete played chunks older than specified days.

        Args:
            campaign_id: Campaign/session identifier
            days: Age threshold in days

        Returns:
            Number of chunks deleted
        """
        if not self._db_enabled:
            return 0

        session = self._get_session()
        if session is None:
            return 0

        try:
            from datetime import timedelta

            threshold = datetime.now(timezone.utc) - timedelta(days=days)

            # Delete old played chunks
            stmt = (
                select(AudioChunk)
                .where(
                    and_(
                        AudioChunk.campaign_id == campaign_id,
                        AudioChunk.status == PlaybackStatus.PLAYED,
                        AudioChunk.played_at < threshold,
                    )
                )
            )
            chunks = session.execute(stmt).scalars().all()

            for chunk in chunks:
                session.delete(chunk)

            session.commit()
            deleted_count = len(chunks)
            if deleted_count > 0:
                logger.info(
                    "[AUDIO_DB] Cleaned up %d old played chunks for campaign %s",
                    deleted_count,
                    campaign_id,
                )
            return deleted_count
        except Exception as exc:
            logger.error("Failed to cleanup old chunks: %s", exc)
            session.rollback()
            return 0
        finally:
            session.close()

    def cleanup_stuck_requests(self, max_age_minutes: int = 15) -> int:
        """Mark stuck GENERATED/GENERATING requests as FAILED.

        Requests stuck in GENERATED or GENERATING status for longer than max_age_minutes
        are likely abandoned (user disconnected, browser crashed, network issues, etc.).
        This prevents them from cluttering the queue.

        Args:
            max_age_minutes: Age threshold in minutes (default: 15)

        Returns:
            Number of requests marked as FAILED
        """
        if not self._db_enabled:
            return 0

        session = self._get_session()
        if session is None:
            return 0

        try:
            from datetime import timedelta

            threshold = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)

            # Find stuck requests (GENERATED or GENERATING older than threshold)
            stmt = (
                select(AudioPlaybackRequest)
                .where(
                    and_(
                        AudioPlaybackRequest.status.in_([PlaybackStatus.GENERATED, PlaybackStatus.GENERATING]),
                        AudioPlaybackRequest.requested_at < threshold,
                    )
                )
            )
            stuck_requests = session.execute(stmt).scalars().all()

            # Mark them as FAILED
            for request in stuck_requests:
                request.status = PlaybackStatus.FAILED
                request.completed_at = datetime.now(timezone.utc)

            session.commit()
            cleaned_count = len(stuck_requests)

            if cleaned_count > 0:
                logger.info(
                    "[AUDIO_CLEANUP] Marked %d stuck requests as FAILED (older than %d minutes)",
                    cleaned_count,
                    max_age_minutes,
                )

            return cleaned_count
        except Exception as exc:
            logger.error("Failed to cleanup stuck requests: %s", exc)
            session.rollback()
            return 0
        finally:
            session.close()


# Global instance
audio_playback_service = AudioPlaybackService()
