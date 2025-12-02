"""Connection pool manager for ElevenLabs Scribe V2 WebSocket connections.

Manages concurrent connections to ElevenLabs API to stay within rate limits.
Provides queueing when at capacity with status updates to waiting clients.
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QueuedRequest:
    """A queued connection request waiting for a slot."""
    request_id: str
    notify_callback: Callable[[str, dict], Awaitable[None]]
    queued_at: float = field(default_factory=time.time)
    cancelled: bool = False


class ElevenLabsConnectionPool:
    """
    Manages a pool of concurrent ElevenLabs Scribe V2 connections.

    When the pool is at capacity, new requests are queued and notified
    of their position. When a slot becomes available, the next queued
    request is activated.
    """

    def __init__(self, max_connections: int = 20):
        """
        Initialize the connection pool.

        Args:
            max_connections: Maximum concurrent ElevenLabs connections
        """
        self.max_connections = max_connections
        self.active_connections = 0
        self.waiting_queue: asyncio.Queue[QueuedRequest] = asyncio.Queue()
        self.queue_list: list[QueuedRequest] = []  # For position tracking
        self._lock = asyncio.Lock()
        logger.info(f"🔌 Connection pool initialized with max {max_connections} connections")

    async def acquire(
        self,
        request_id: str,
        notify_callback: Callable[[str, dict], Awaitable[None]]
    ) -> bool:
        """
        Acquire a connection slot from the pool.

        If a slot is available, returns True immediately.
        If at capacity, queues the request and notifies the client.

        Args:
            request_id: Unique identifier for this request
            notify_callback: Async callback to notify client of status updates
                            Called with (event_type, data) where event_type is
                            'queued', 'queue_position', or 'slot_available'

        Returns:
            True when a slot is acquired (may wait if queued)
        """
        async with self._lock:
            if self.active_connections < self.max_connections:
                # Slot available immediately
                self.active_connections += 1
                logger.debug(f"🟢 Slot acquired for {request_id} ({self.active_connections}/{self.max_connections} active)")
                return True

            # At capacity - queue the request
            queued_request = QueuedRequest(
                request_id=request_id,
                notify_callback=notify_callback
            )
            self.queue_list.append(queued_request)
            position = len(self.queue_list)

            logger.info(f"⏳ Request {request_id} queued at position {position}")

        # Notify client they're queued (outside lock)
        try:
            await notify_callback('queued', {
                'position': position,
                'message': f'Waiting for available slot. Position: {position}'
            })
        except Exception as e:
            logger.warning(f"Failed to notify queued client: {e}")

        # Wait for a slot to become available
        while True:
            await asyncio.sleep(0.5)  # Check every 500ms

            async with self._lock:
                # Check if cancelled
                if queued_request.cancelled:
                    if queued_request in self.queue_list:
                        self.queue_list.remove(queued_request)
                    return False

                # Check if we're at the front of the queue and a slot is available
                if self.queue_list and self.queue_list[0] == queued_request:
                    if self.active_connections < self.max_connections:
                        self.queue_list.pop(0)
                        self.active_connections += 1
                        logger.debug(f"🟢 Slot acquired for queued {request_id} ({self.active_connections}/{self.max_connections} active)")

                        try:
                            await notify_callback('slot_available', {
                                'message': 'Connection slot available, starting transcription'
                            })
                        except Exception as e:
                            logger.warning(f"Failed to notify slot available: {e}")

                        return True

                # Update position if still queued
                try:
                    current_position = self.queue_list.index(queued_request) + 1
                    if current_position != position:
                        position = current_position
                        try:
                            await notify_callback('queue_position', {
                                'position': position,
                                'message': f'Queue position updated: {position}'
                            })
                        except Exception as e:
                            logger.warning(f"Failed to notify position update: {e}")
                except ValueError:
                    # Not in queue anymore
                    pass

    async def release(self, request_id: str):
        """
        Release a connection slot back to the pool.

        Args:
            request_id: Identifier of the connection being released
        """
        async with self._lock:
            if self.active_connections > 0:
                self.active_connections -= 1
                logger.debug(f"🔴 Slot released by {request_id} ({self.active_connections}/{self.max_connections} active)")

    def cancel_queued(self, request_id: str):
        """
        Cancel a queued request (client disconnected while waiting).

        Args:
            request_id: Identifier of the request to cancel
        """
        for req in self.queue_list:
            if req.request_id == request_id:
                req.cancelled = True
                logger.info(f"❌ Cancelled queued request {request_id}")
                break

    @property
    def available_slots(self) -> int:
        """Number of currently available connection slots."""
        return max(0, self.max_connections - self.active_connections)

    @property
    def queue_length(self) -> int:
        """Number of requests currently waiting in queue."""
        return len(self.queue_list)

    def get_status(self) -> dict:
        """Get current pool status for monitoring."""
        return {
            'max_connections': self.max_connections,
            'active_connections': self.active_connections,
            'available_slots': self.available_slots,
            'queue_length': self.queue_length
        }


# Singleton instance
_connection_pool: Optional[ElevenLabsConnectionPool] = None


def get_connection_pool(max_connections: int = 20) -> ElevenLabsConnectionPool:
    """Get or create the connection pool singleton."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ElevenLabsConnectionPool(max_connections=max_connections)
    return _connection_pool
