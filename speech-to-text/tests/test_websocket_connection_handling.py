"""
Unit tests for WebSocket connection handling and error scenarios.

Tests cover:
- Normal websocket closures (1000 OK)
- Race conditions when connection closes during message send
- Cleanup behavior when websocket is already closed
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from starlette.websockets import WebSocketDisconnect

from src.scribe_message_processor import ScribeMessageProcessor


class TestWebSocketConnectionClosures:
    """Test handling of websocket connection closures."""

    @pytest.mark.asyncio
    async def test_normal_closure_does_not_raise_error(self):
        """Test that normal websocket closure (1000 OK) is handled gracefully."""
        # Create a mock send callback that raises ConnectionClosedOK
        send_callback = AsyncMock(side_effect=ConnectionClosedOK(1000, "OK"))

        processor = ScribeMessageProcessor(send_callback)

        # Process some partial text
        await processor.on_partial({"text": "Hello world"})

        # Trigger cleanup - should not raise exception
        await processor.cleanup()

        # Verify send was attempted but failure was handled gracefully
        assert send_callback.called
        # No exception should be raised

    @pytest.mark.asyncio
    async def test_abnormal_closure_logged_as_warning(self):
        """Test that abnormal closures are logged but don't crash."""
        send_callback = AsyncMock(side_effect=ConnectionClosedError(1006, "Abnormal closure"))

        processor = ScribeMessageProcessor(send_callback)
        await processor.on_partial({"text": "Hello"})

        # Should handle the error gracefully
        await processor.cleanup()

        assert send_callback.called

    @pytest.mark.asyncio
    async def test_race_condition_during_finalize(self):
        """Test race condition when connection closes during timer finalization."""
        # Create a send callback that fails on second call (simulating close during finalize)
        call_count = 0

        async def flaky_send(message):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise RuntimeError("Unexpected ASGI message 'websocket.send', after sending 'websocket.close'.")

        send_callback = AsyncMock(side_effect=flaky_send)
        processor = ScribeMessageProcessor(send_callback, timer_delay_secs=0.1)

        # Add committed text
        await processor.on_committed_transcript({"text": "Final text"})

        # Wait for timer to trigger
        await asyncio.sleep(0.2)

        # Should have tried to send but handled the error
        assert send_callback.called

    @pytest.mark.asyncio
    async def test_cleanup_with_closed_websocket(self):
        """Test cleanup when websocket is already closed."""
        send_callback = AsyncMock(
            side_effect=RuntimeError("Unexpected ASGI message 'websocket.send', after sending 'websocket.close'.")
        )

        processor = ScribeMessageProcessor(send_callback)
        await processor.on_partial({"text": "Partial text"})

        # Cleanup should not raise exception even though send fails
        await processor.cleanup()

        # Verify state was reset despite send failure
        assert processor.expected_commit_text == ""
        assert processor.pending_commit_text == ""


class TestScribeMessageProcessorRobustness:
    """Test ScribeMessageProcessor handles edge cases robustly."""

    @pytest.mark.asyncio
    async def test_multiple_cleanup_calls(self):
        """Test that calling cleanup multiple times is safe."""
        send_callback = AsyncMock()
        processor = ScribeMessageProcessor(send_callback)

        await processor.on_partial({"text": "Test"})

        # First cleanup
        await processor.cleanup()
        first_call_count = send_callback.call_count

        # Second cleanup should be safe
        await processor.cleanup()

        # Should not send additional messages
        assert send_callback.call_count == first_call_count

    @pytest.mark.asyncio
    async def test_cleanup_with_pending_timer(self):
        """Test cleanup properly cancels pending timer task."""
        send_callback = AsyncMock()
        processor = ScribeMessageProcessor(send_callback, timer_delay_secs=10.0)

        # Trigger a commit that starts the timer
        await processor.on_committed_transcript({"text": "Test"})

        # Verify timer task was created
        assert processor.commit_timer_task is not None
        assert not processor.commit_timer_task.done()

        # Cleanup should cancel the timer
        await processor.cleanup()

        # Timer should be cancelled
        assert processor.commit_timer_task is None or processor.commit_timer_task.done()

    @pytest.mark.asyncio
    async def test_send_after_close_handled_gracefully(self):
        """Test that attempting to send after close doesn't cause issues."""
        messages_sent = []

        async def tracking_send(message):
            if len(messages_sent) >= 2:
                # Simulate connection closed after first message
                raise RuntimeError("Unexpected ASGI message 'websocket.send', after sending 'websocket.close'.")
            messages_sent.append(message)

        send_callback = AsyncMock(side_effect=tracking_send)
        processor = ScribeMessageProcessor(send_callback)

        # Send partial
        await processor.on_partial({"text": "Partial 1"})

        # Send committed (triggers timer)
        await processor.on_committed_transcript({"text": "Committed"})

        # Try another partial - should handle gracefully if connection closed
        await processor.on_partial({"text": "Partial 2"})

        # Cleanup
        await processor.cleanup()

        # Should have attempted to send but handled errors
        assert send_callback.called


class TestConnectionPoolGracefulShutdown:
    """Test connection pool handles shutdowns gracefully."""

    @pytest.mark.asyncio
    async def test_release_after_shutdown(self):
        """Test that releasing a slot after shutdown is safe."""
        from src.services.connection_pool import ConnectionPool

        pool = ConnectionPool(max_connections=5)

        # Acquire a slot
        acquired = await pool.acquire_slot("test-123")
        assert acquired

        # Release the slot - should be safe
        await pool.release_slot("test-123")

        # Second release should also be safe
        await pool.release_slot("test-123")

    @pytest.mark.asyncio
    async def test_queue_cancel_on_disconnect(self):
        """Test that queued requests can be cancelled when client disconnects."""
        from src.services.connection_pool import ConnectionPool

        pool = ConnectionPool(max_connections=1)

        # Fill the pool
        await pool.acquire_slot("conn-1")

        # Queue a second request
        acquire_task = asyncio.create_task(
            pool.acquire_slot("conn-2", lambda event, data: asyncio.sleep(0))
        )

        # Give it time to queue
        await asyncio.sleep(0.1)

        # Cancel the queued request (simulating client disconnect)
        pool.cancel_queued("conn-2")

        # Task should complete (return False)
        result = await acquire_task
        assert result is False
