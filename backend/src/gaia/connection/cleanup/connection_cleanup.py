"""Background task for cleaning up old WebSocket connections."""

import asyncio
import logging

from gaia.connection.connection_registry import connection_registry

logger = logging.getLogger(__name__)


class ConnectionCleanupTask:
    """Background task to cleanup old connections from the registry."""

    def __init__(self, cleanup_interval_seconds: int = 3600, max_age_hours: int = 24):
        """Initialize cleanup task.

        Args:
            cleanup_interval_seconds: How often to run cleanup (default: 1 hour)
            max_age_hours: Age threshold for removing connections (default: 24 hours)
        """
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.max_age_hours = max_age_hours
        self._task = None
        self._running = False

    async def start(self):
        """Start the background cleanup task."""
        if self._running:
            logger.warning("Cleanup task is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.debug(
            "Started connection cleanup task (interval=%ds, max_age=%dh)",
            self.cleanup_interval_seconds,
            self.max_age_hours,
        )

    async def stop(self):
        """Stop the background cleanup task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped connection cleanup task")

    async def _cleanup_loop(self):
        """Main cleanup loop that runs periodically."""
        while self._running:
            try:
                # Wait for the next cleanup interval
                await asyncio.sleep(self.cleanup_interval_seconds)

                if not self._running:
                    break

                # Run cleanup
                if connection_registry.db_enabled:
                    try:
                        removed = connection_registry.cleanup_old_connections(
                            max_age_hours=self.max_age_hours
                        )
                        if removed > 0:
                            logger.info(
                                "[CONN_CLEANUP] Removed %d old connections (older than %dh)",
                                removed,
                                self.max_age_hours,
                            )
                    except Exception as exc:
                        logger.error(
                            "[CONN_CLEANUP] Error during cleanup: %s",
                            exc,
                            exc_info=True,
                        )
                else:
                    logger.debug(
                        "[CONN_CLEANUP] Skipping cleanup - connection registry database not enabled"
                    )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "[CONN_CLEANUP] Unexpected error in cleanup loop: %s",
                    exc,
                    exc_info=True,
                )
                # Continue running despite errors


# Global singleton instance
cleanup_task = ConnectionCleanupTask()
