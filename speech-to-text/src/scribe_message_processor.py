"""Scribe V2 message processor for handling ElevenLabs transcription messages.

This module extracts the message processing logic from websocket_handlers.py
into a testable class with timer-based commit handling.

State Machine:
1. Partials: Forward immediately, track as expected_commit_text (fallback)
2. Commits: Update pending_commit_text, start timer if not running
3. Timer fires: Send empty partial (clear overlay) + final transcription
4. Late commits/partials after timer: Blocked during cooldown period
5. After cooldown expires: Reset and accept new speech

Key fixes:
- utterance_finalized blocks both commits AND partials (prevents overlay refill)
- Cooldown period after finalization allows ElevenLabs duplicates to drain
- After cooldown, automatically reset for new speech
- cleanup() method flushes pending text on websocket close
"""

import asyncio
import logging
import time
from typing import Dict, Any, Callable, Awaitable, Optional, List

logger = logging.getLogger(__name__)

# Cooldown period after finalization (seconds)
# During this time, all partials/commits are blocked to let ElevenLabs drain duplicates
FINALIZATION_COOLDOWN_SECS = 1.0


class ScribeMessageProcessor:
    """Processes messages from ElevenLabs Scribe V2 API.

    Uses timer-based commit handling:
    - First commit starts a timer (default 2 seconds)
    - Additional commits within window update pending text
    - Timer fires: sends final transcription
    - Late commits after timer are blocked until new speech starts
    """

    def __init__(
        self,
        send_callback: Callable[[Dict[str, Any]], Awaitable[None]],
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
        timer_delay_secs: float = 2.0
    ):
        """Initialize the message processor.

        Args:
            send_callback: Async function to send messages to frontend
            on_error: Optional callback for V2 errors (billing, etc.)
            timer_delay_secs: Delay before finalizing commits (default 2s)
        """
        self.send_callback = send_callback
        self.on_error = on_error
        self.timer_delay_secs = timer_delay_secs

        # State machine variables
        self.expected_commit_text = ""      # Latest partial (fallback if commit empty)
        self.pending_commit_text = ""       # Text to be committed after timer expires
        self.commit_timer_task: Optional[asyncio.Task] = None
        self.utterance_finalized = False    # Block late commits/partials after timer fires
        self.finalization_time = 0.0        # Timestamp when finalization occurred

        # Track sent messages for testing
        self._sent_messages: List[Dict[str, Any]] = []
        self._pending_tasks: List[asyncio.Task] = []

    def reset(self) -> None:
        """Reset processor state for new session."""
        self.expected_commit_text = ""
        self.pending_commit_text = ""
        self.utterance_finalized = False
        self.finalization_time = 0.0
        self._sent_messages.clear()

        # Cancel timer if running
        if self.commit_timer_task and not self.commit_timer_task.done():
            self.commit_timer_task.cancel()
        self.commit_timer_task = None

        # Cancel any other pending tasks
        for task in self._pending_tasks:
            if not task.done():
                task.cancel()
        self._pending_tasks.clear()

    async def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a message from ElevenLabs Scribe V2.

        Args:
            message: Message from ElevenLabs with message_type and text

        Returns:
            The message sent to frontend, or None if nothing sent yet
        """
        message_type = message.get("message_type", "unknown")

        if message_type == "partial_transcript":
            return await self._handle_partial(message)
        elif message_type == "committed_transcript":
            return await self._handle_commit(message)
        elif message_type == "error":
            return await self._handle_error(message)

        return None

    async def _handle_partial(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle partial transcript message.

        During cooldown period after finalization, partials are blocked to prevent
        ElevenLabs duplicate messages from refilling the overlay.
        After cooldown expires, reset and accept new speech.

        Args:
            message: Partial transcript from ElevenLabs

        Returns:
            Message sent to frontend, or None if blocked
        """
        text = message.get("text", "")

        # Check if we're in finalized state
        if self.utterance_finalized:
            elapsed = time.time() - self.finalization_time
            if elapsed < FINALIZATION_COOLDOWN_SECS:
                # Still in cooldown - block this partial
                logger.debug(f"⏭️ Ignoring partial during cooldown ({elapsed:.2f}s)")
                return None
            else:
                # Cooldown expired - reset for new speech
                logger.info("🔄 Cooldown expired, accepting new speech")
                self.utterance_finalized = False
                self.finalization_time = 0.0

        # Track as expected commit (fallback if commit comes back empty)
        self.expected_commit_text = text
        logger.debug(f"📝 Partial: {text}")

        outgoing = {
            "event": "partial_transcript",
            "data": {
                "text": text,
                "is_partial": True,
                "timestamp": time.time()
            }
        }

        await self.send_callback(outgoing)
        self._sent_messages.append(outgoing)
        return outgoing

    async def _handle_commit(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle committed transcript message.

        Timer-based handling:
        - If finalized and in cooldown, block the commit (it's late)
        - If cooldown expired, reset and accept as new speech
        - Otherwise, update pending text
        - Start timer on first commit

        Args:
            message: Committed transcript from ElevenLabs

        Returns:
            None (actual send happens when timer fires)
        """
        # Check if we're in finalized state
        if self.utterance_finalized:
            elapsed = time.time() - self.finalization_time
            if elapsed < FINALIZATION_COOLDOWN_SECS:
                # Still in cooldown - block this commit
                logger.debug(f"⏭️ Ignoring late commit during cooldown ({elapsed:.2f}s)")
                return None
            else:
                # Cooldown expired - reset for new speech
                logger.debug("🔄 Cooldown expired, accepting new commit")
                self.utterance_finalized = False
                self.finalization_time = 0.0

        text = message.get("text", "")

        # Determine commit text: use actual if non-empty, else fallback to partial
        commit_text = text.strip() if text.strip() else self.expected_commit_text.strip()

        if not commit_text:
            logger.debug("Ignoring empty committed_transcript (no partial fallback)")
            return None

        # Update pending commit (allows refinement within timer window)
        self.pending_commit_text = commit_text
        logger.info(f"📝 Pending commit updated: {self.pending_commit_text}")

        # Start timer on first commit (if not already running)
        if self.commit_timer_task is None:
            # Starting a new timer = new utterance, so reset finalized
            self.utterance_finalized = False
            self.commit_timer_task = asyncio.create_task(self._finalize_after_delay())
            self._pending_tasks.append(self.commit_timer_task)
            logger.info("⏱️ Started commit timer")

        return None  # Actual send happens in timer callback

    async def _finalize_after_delay(self) -> None:
        """Timer callback: send final transcription after delay."""
        await asyncio.sleep(self.timer_delay_secs)

        if self.pending_commit_text.strip():
            final_text = self.pending_commit_text.strip() + ". "
            logger.info(f"✅ Committed (after {self.timer_delay_secs}s): {final_text}")

            # First: send empty partial to clear the overlay
            clear_partial = {
                "event": "partial_transcript",
                "data": {
                    "text": "",
                    "is_partial": True,
                    "timestamp": time.time()
                }
            }
            try:
                await self.send_callback(clear_partial)
                self._sent_messages.append(clear_partial)
            except Exception as e:
                logger.debug(f"Failed to send clear partial (connection likely closed): {e}")
                return  # Connection closed, no point continuing

            # Then: send the final transcription segment
            final_msg = {
                "event": "transcription_segment",
                "data": {
                    "text": final_text,
                    "is_final": True,
                    "timestamp": time.time()
                }
            }
            try:
                await self.send_callback(final_msg)
                self._sent_messages.append(final_msg)
            except Exception as e:
                logger.debug(f"Failed to send final (connection likely closed): {e}")

        # Mark utterance as finalized to block late commits/partials during cooldown
        self.utterance_finalized = True
        self.finalization_time = time.time()

        # Reset state for next utterance
        self.pending_commit_text = ""
        self.expected_commit_text = ""
        self.commit_timer_task = None

    async def _handle_error(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle error message from ElevenLabs.

        Args:
            message: Error message

        Returns:
            Error message sent to frontend, or None if handled by callback
        """
        error = message.get("error", "Unknown error")
        logger.error(f"❌ Scribe V2 error: {error}")

        # Check for billing errors that should trigger fallback
        if "insufficient_funds" in error.lower() or "billing" in error.lower():
            if self.on_error:
                await self.on_error(error)
            return None

        outgoing = {
            "event": "error",
            "data": {
                "message": error,
                "timestamp": time.time()
            }
        }

        await self.send_callback(outgoing)
        self._sent_messages.append(outgoing)
        return outgoing

    async def flush_pending(self) -> None:
        """Wait for all pending tasks (including timer) to complete."""
        tasks_to_wait = [t for t in self._pending_tasks if not t.done()]
        if tasks_to_wait:
            await asyncio.gather(*tasks_to_wait, return_exceptions=True)
        self._pending_tasks.clear()

    async def cleanup(self) -> None:
        """Cleanup on websocket close - send any pending text immediately.

        This ensures that:
        1. Any pending commit text is sent before the connection closes
        2. The overlay is cleared with an empty partial
        3. All state is reset
        """
        # Cancel the timer if running
        if self.commit_timer_task and not self.commit_timer_task.done():
            self.commit_timer_task.cancel()
            try:
                await self.commit_timer_task
            except asyncio.CancelledError:
                pass

        # Send pending text if any
        if self.pending_commit_text.strip():
            final_text = self.pending_commit_text.strip() + ". "
            logger.info(f"🏁 Cleanup: sending pending text: {final_text}")

            # First: send empty partial to clear the overlay
            clear_partial = {
                "event": "partial_transcript",
                "data": {
                    "text": "",
                    "is_partial": True,
                    "timestamp": time.time()
                }
            }
            try:
                await self.send_callback(clear_partial)
                self._sent_messages.append(clear_partial)
            except Exception as e:
                logger.debug(f"Failed to send clear partial during cleanup (connection likely closed): {e}")

            # Then: send the final transcription segment
            final_msg = {
                "event": "transcription_segment",
                "data": {
                    "text": final_text,
                    "is_final": True,
                    "timestamp": time.time()
                }
            }
            try:
                await self.send_callback(final_msg)
                self._sent_messages.append(final_msg)
            except Exception as e:
                logger.debug(f"Failed to send final during cleanup (connection likely closed): {e}")

        # If no pending commit but partial text exists, commit it as final
        # This handles the case where user closes websocket while still talking
        elif self.expected_commit_text.strip():
            final_text = self.expected_commit_text.strip() + ". "
            logger.debug(f"🏁 Cleanup: committing partial as final: {final_text}")

            # First: send empty partial to clear the overlay
            clear_partial = {
                "event": "partial_transcript",
                "data": {
                    "text": "",
                    "is_partial": True,
                    "timestamp": time.time()
                }
            }
            try:
                await self.send_callback(clear_partial)
                self._sent_messages.append(clear_partial)
            except Exception as e:
                logger.debug(f"Failed to send clear partial during cleanup (connection likely closed): {e}")

            # Then: send the partial text as final transcription
            final_msg = {
                "event": "transcription_segment",
                "data": {
                    "text": final_text,
                    "is_final": True,
                    "timestamp": time.time()
                }
            }
            try:
                await self.send_callback(final_msg)
                self._sent_messages.append(final_msg)
            except Exception as e:
                logger.debug(f"Failed to send final during cleanup (connection likely closed): {e}")

        # Reset state
        self.reset()

    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """Get all messages sent to frontend (for testing)."""
        return self._sent_messages.copy()

    def get_final_messages(self) -> List[Dict[str, Any]]:
        """Get only transcription_segment messages (finals)."""
        return [m for m in self._sent_messages if m.get("event") == "transcription_segment"]

    def get_partial_messages(self) -> List[Dict[str, Any]]:
        """Get only partial_transcript messages."""
        return [m for m in self._sent_messages if m.get("event") == "partial_transcript"]

    @property
    def is_timer_running(self) -> bool:
        """Check if the commit timer is currently running."""
        return self.commit_timer_task is not None and not self.commit_timer_task.done()
