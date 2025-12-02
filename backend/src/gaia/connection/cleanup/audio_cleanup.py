"""Background task for cleaning up old audio chunks."""

import asyncio
import logging

from sqlalchemy import select, distinct
from db.src.connection import db_manager
from gaia.infra.audio.audio_models import AudioPlaybackRequest
from gaia.infra.audio.audio_playback_service import audio_playback_service

logger = logging.getLogger(__name__)


class AudioCleanupTask:
    """Background task to cleanup old audio chunks from the database."""

    def __init__(self, cleanup_interval_seconds: int = 60, max_age_days: int = 7):
        """Initialize audio cleanup task.

        Args:
            cleanup_interval_seconds: How often to run cleanup (default: 60 seconds)
            max_age_days: Age threshold for removing played chunks (default: 7 days)
        """
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.max_age_days = max_age_days
        self._task = None
        self._running = False

    async def start(self):
        """Start the background audio cleanup task."""
        if self._running:
            logger.warning("Audio cleanup task is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.debug(
            "Started audio cleanup task (interval=%ds, max_age=%dd)",
            self.cleanup_interval_seconds,
            self.max_age_days,
        )

    async def stop(self):
        """Stop the background audio cleanup task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped audio cleanup task")

    async def _cleanup_loop(self):
        """Main cleanup loop that runs periodically."""
        while self._running:
            try:
                # Wait for the next cleanup interval
                await asyncio.sleep(self.cleanup_interval_seconds)

                if not self._running:
                    break

                # Run cleanup for all active sessions
                if audio_playback_service.db_enabled:
                    try:
                        # Get all active campaign IDs from playback queue
                        with db_manager.get_sync_session() as session:
                            stmt = select(distinct(AudioPlaybackRequest.campaign_id))
                            campaign_ids = session.execute(stmt).scalars().all()

                        total_removed = 0
                        for campaign_id in campaign_ids:
                            removed = audio_playback_service.cleanup_old_chunks(
                                campaign_id,
                                days=self.max_age_days
                            )
                            total_removed += removed

                        if total_removed > 0:
                            logger.info(
                                "[AUDIO_CLEANUP] Removed %d old audio chunks (older than %dd)",
                                total_removed,
                                self.max_age_days,
                            )

                        # Clean up stuck requests (GENERATED/GENERATING older than 15 minutes)
                        stuck_cleaned = audio_playback_service.cleanup_stuck_requests(max_age_minutes=15)
                        if stuck_cleaned > 0:
                            logger.info(
                                "[AUDIO_CLEANUP] Marked %d stuck requests as FAILED",
                                stuck_cleaned,
                            )
                    except Exception as exc:
                        logger.error(
                            "[AUDIO_CLEANUP] Error during cleanup: %s",
                            exc,
                            exc_info=True,
                        )
                else:
                    logger.debug(
                        "[AUDIO_CLEANUP] Skipping cleanup - audio playback database not enabled"
                    )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "[AUDIO_CLEANUP] Unexpected error in cleanup loop: %s",
                    exc,
                    exc_info=True,
                )
                # Continue running despite errors


# Global singleton instance
audio_cleanup_task = AudioCleanupTask()
