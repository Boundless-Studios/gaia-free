"""Audio queue manager to ensure sequential playback without overlaps."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from gaia.infra.audio.voice_and_tts_config import (
    AUTO_TTS_OUTPUT,
    get_playback_config,
    get_tts_config,
)

logger = logging.getLogger(__name__)

DEFAULT_SESSION_ID = "default"
SESSION_IDLE_TIMEOUT_SECONDS = 300


@dataclass
class _SessionState:
    """Internal per-session playback state."""

    session_id: str
    audio_queue: "queue.Queue[Dict[str, Any]]" = field(default_factory=queue.Queue)
    playback_history: deque = field(default_factory=lambda: deque(maxlen=50))
    is_playing: bool = False
    current_process: Optional[Any] = None
    stop_requested: bool = False
    worker_thread: Optional[threading.Thread] = None
    last_activity: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    shutdown: bool = False
    current_playback_id: Optional[str] = None
    pending_playback_counts: Dict[str, int] = field(default_factory=dict)


class AudioQueueManager:
    """Manages per-session audio playback queues to prevent overlapping audio."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._sessions: Dict[str, _SessionState] = {}
        self._sessions_lock = threading.Lock()
        self._max_history = 50
        self._session_idle_timeout = SESSION_IDLE_TIMEOUT_SECONDS

        # Pre-create the default session to preserve existing behaviour.
        self._ensure_session(DEFAULT_SESSION_ID)

    # ------------------------------------------------------------------ #
    # Session management helpers
    # ------------------------------------------------------------------ #
    def _normalize_session_id(self, session_id: Optional[str]) -> str:
        if session_id and isinstance(session_id, str) and session_id.strip():
            return session_id.strip()
        return DEFAULT_SESSION_ID

    def _ensure_session(self, session_id: Optional[str]) -> _SessionState:
        session_key = self._normalize_session_id(session_id)
        with self._sessions_lock:
            state = self._sessions.get(session_key)
            if state is None or state.shutdown:
                state = _SessionState(session_id=session_key)
                state.playback_history = deque(maxlen=self._max_history)
                self._start_worker_thread(state)
                self._sessions[session_key] = state
                logger.debug(
                    "Audio queue worker thread started for session %s", session_key
                )
        return state

    def _get_session(
        self, session_id: Optional[str], create: bool = True
    ) -> Optional[_SessionState]:
        session_key = self._normalize_session_id(session_id)
        with self._sessions_lock:
            state = self._sessions.get(session_key)
        if state is None and create:
            state = self._ensure_session(session_key)
        return state

    def _start_worker_thread(self, state: _SessionState) -> None:
        state.worker_thread = threading.Thread(
            target=self._audio_worker, args=(state,), daemon=True
        )
        state.worker_thread.start()

    # ------------------------------------------------------------------ #
    # Worker loop
    # ------------------------------------------------------------------ #
    def _audio_worker(self, state: _SessionState) -> None:
        logger.debug(
            "Audio queue worker thread running for session %s", state.session_id
        )

        while True:
            if state.shutdown:
                break

            try:
                audio_item = state.audio_queue.get(timeout=1.0)
            except queue.Empty:
                if self._should_terminate_session(state):
                    logger.debug(
                        "Audio queue worker idle for session %s; shutting down",
                        state.session_id,
                    )
                    self._mark_session_shutdown(state)
                    break
                continue

            if audio_item.get("__shutdown__"):
                state.audio_queue.task_done()
                logger.debug(
                    "Audio queue worker received shutdown signal for session %s",
                    state.session_id,
                )
                self._mark_session_shutdown(state)
                break

            item_description = audio_item.get("file_path", "paragraph_break")
            logger.debug(
                "Session %s processing audio item: %s",
                state.session_id,
                item_description,
            )
            state.last_activity = time.time()

            # Handle stop requests signalled from stop_current
            with state.lock:
                state.is_playing = True
                if state.stop_requested:
                    logger.info(
                        "Stop requested for session %s; skipping audio playback",
                        state.session_id,
                    )
                    state.stop_requested = False
                    state.is_playing = False
                    state.current_process = None
                    state.audio_queue.task_done()
                    self._sleep_between_items(audio_item)
                    continue

            start_time = time.time()
            playback_id = audio_item.get("playback_id")
            try:
                if audio_item.get("is_paragraph_break"):
                    # No audio playback, just honour the pause duration.
                    logger.debug(
                        "Session %s adding paragraph break pause",
                        state.session_id,
                    )
                else:
                    file_path = audio_item.get("file_path")
                    if not file_path or not Path(file_path).exists():
                        logger.error(
                            "Audio file not found for session %s: %s",
                            state.session_id,
                            file_path,
                        )
                    else:
                        output_method, windows_routing = self._resolve_playback_config()
                        if output_method in ("mute", "none"):
                            logger.debug(
                                "Session %s using %s output; skipping server-side playback for %s",
                                state.session_id,
                                output_method,
                                file_path,
                            )
                        else:
                            playback_process, loop = self._play_file(
                                file_path, output_method, windows_routing
                            )
                            if playback_process and loop:
                                with state.lock:
                                    state.current_process = playback_process
                                try:
                                    loop.run_until_complete(playback_process.wait())
                                finally:
                                    loop.close()
            except Exception as exc:  # pragma: no cover - safety net
                logger.error(
                    "Error playing audio for session %s: %s",
                    state.session_id,
                    exc,
                )
            finally:
                self._record_history(state, audio_item, start_time)
                with state.lock:
                    state.is_playing = False
                    state.current_process = None
                    if playback_id:
                        remaining = (
                            state.pending_playback_counts.get(playback_id, 0) - 1
                        )
                        if remaining <= 0:
                            state.pending_playback_counts.pop(playback_id, None)
                        else:
                            state.pending_playback_counts[playback_id] = remaining
                    if not state.pending_playback_counts:
                        state.current_playback_id = None
                    elif playback_id and playback_id not in state.pending_playback_counts:
                        state.current_playback_id = None
                state.audio_queue.task_done()
                self._sleep_between_items(audio_item)

        logger.debug("Audio queue worker exited for session %s", state.session_id)

    def _record_history(
        self, state: _SessionState, audio_item: Dict[str, Any], start_time: float
    ) -> None:
        entry = {
            "file_path": audio_item.get("file_path", "paragraph_break"),
            "timestamp": start_time,
            "duration": time.time() - start_time,
            "voice": audio_item.get("voice", "unknown"),
            "text_preview": audio_item.get("text", "")[:50],
            "is_paragraph_break": audio_item.get("is_paragraph_break", False),
            "session_id": state.session_id,
            "playback_id": audio_item.get("playback_id"),
            "metadata": audio_item.get("metadata") or {},
        }
        with state.lock:
            state.playback_history.append(entry)

    def _sleep_between_items(self, audio_item: Dict[str, Any]) -> None:
        process: Optional[Any] = None
        try:
            playback_config = get_playback_config()
            delay = (
                playback_config["paragraph_delay"]
                if audio_item.get("is_paragraph_break")
                else playback_config["chunk_delay"]
            )
        except Exception as exc:  # pragma: no cover - config fallback
            logger.warning("Failed to load playback config: %s", exc)
            delay = 0.0
        time.sleep(delay)

    def _resolve_playback_config(self) -> tuple[str, str]:
        try:
            tts_config = get_tts_config()
            output_method = tts_config["output"].lower()
            windows_routing = tts_config.get("windows_routing", "windows_utils").lower()
        except Exception as exc:  # pragma: no cover - config fallback
            output_method = AUTO_TTS_OUTPUT.lower()
            windows_routing = "windows_utils"
            logger.warning(
                "Falling back to default TTS config due to error: %s", exc
            )
        return output_method, windows_routing

    def _play_file(
        self,
        file_path: str,
        output_method: str,
        windows_routing: str,
    ) -> Tuple[Optional[Any], Optional[asyncio.AbstractEventLoop]]:
        """Create playback process using configured output method."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if output_method == "unix":
                from gaia.utils.audio_utils import play_audio_unix_with_process

                process = loop.run_until_complete(
                    play_audio_unix_with_process(file_path)
                )
            elif output_method == "windows":
                if windows_routing == "windows_direct":
                    from gaia.utils.audio_utils import (
                        play_audio_windows_direct_with_process,
                    )

                    process = loop.run_until_complete(
                        play_audio_windows_direct_with_process(file_path)
                    )
                else:
                    from gaia.utils.windows_audio_utils import (
                        play_audio_windows_with_process,
                    )

                    process = loop.run_until_complete(
                        play_audio_windows_with_process(file_path)
                    )
            elif output_method == "windows_direct":
                from gaia.utils.audio_utils import play_audio_windows_direct_with_process

                process = loop.run_until_complete(
                    play_audio_windows_direct_with_process(file_path)
                )
            else:
                from gaia.utils.audio_utils import play_audio_auto_with_process

                process = loop.run_until_complete(
                    play_audio_auto_with_process(file_path)
                )
        except Exception:
            loop.close()
            asyncio.set_event_loop(None)
            raise
        finally:
            asyncio.set_event_loop(None)

        if process is None:
            loop.close()
            return None, None

        return process, loop

    def _should_terminate_session(self, state: _SessionState) -> bool:
        if state.session_id == DEFAULT_SESSION_ID:
            return False
        if state.audio_queue.qsize() > 0:
            return False
        with state.lock:
            if state.is_playing:
                return False
        idle_for = time.time() - state.last_activity
        return idle_for > self._session_idle_timeout

    def _mark_session_shutdown(self, state: _SessionState) -> None:
        with state.lock:
            state.shutdown = True
            state.is_playing = False
            state.current_process = None
        with self._sessions_lock:
            existing = self._sessions.get(state.session_id)
            if existing is state and state.session_id != DEFAULT_SESSION_ID:
                del self._sessions[state.session_id]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def add_to_queue(
        self,
        file_path: str,
        voice: str = "unknown",
        text: str = "",
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add an audio file to a session playback queue."""
        session_key = self._normalize_session_id(session_id)
        if not Path(file_path).exists():
            logger.error(
                "Audio file not found for session %s: %s", session_key, file_path
            )
            state = self._get_session(session_id, create=False)
            queue_size = state.audio_queue.qsize() if state else 0
            return {
                "status": "error",
                "message": "Audio file not found",
                "queue_size": queue_size,
                "session_id": session_key,
            }

        state = self._ensure_session(session_key)
        queue_payload = {
            "file_path": file_path,
            "voice": voice,
            "text": text,
            "queued_at": time.time(),
            "playback_id": playback_id,
            "metadata": metadata or {},
        }
        state.audio_queue.put(queue_payload)
        state.last_activity = time.time()
        if playback_id:
            with state.lock:
                state.pending_playback_counts[playback_id] = (
                    state.pending_playback_counts.get(playback_id, 0) + 1
                )

        queue_size = state.audio_queue.qsize()
        return {
            "status": "queued",
            "message": f"Audio queued for playback (position: {queue_size})",
            "queue_size": queue_size,
            "is_playing": state.is_playing,
            "session_id": session_key,
        }

    async def add_paragraph_break(
        self,
        session_id: Optional[str] = None,
        playback_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a paragraph break pause to the queue."""
        state = self._ensure_session(session_id)
        state.audio_queue.put(
            {
                "is_paragraph_break": True,
                "queued_at": time.time(),
                "playback_id": playback_id,
                "metadata": metadata or {},
            }
        )
        state.last_activity = time.time()
        if playback_id:
            with state.lock:
                state.pending_playback_counts[playback_id] = (
                    state.pending_playback_counts.get(playback_id, 0) + 1
                )

        queue_size = state.audio_queue.qsize()
        return {
            "status": "queued",
            "message": f"Paragraph break queued (position: {queue_size})",
            "queue_size": queue_size,
            "is_playing": state.is_playing,
            "session_id": state.session_id,
        }

    def get_queue_status(
        self, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current queue status for a session."""
        session_key = self._normalize_session_id(session_id)
        state = self._get_session(session_id, create=False)
        if state is None:
            return {
                "session_id": session_key,
                "is_playing": False,
                "queue_size": 0,
                "history_count": 0,
                "last_played": None,
            }

        with state.lock:
            status = {
                "session_id": session_key,
                "is_playing": state.is_playing,
                "queue_size": state.audio_queue.qsize(),
                "history_count": len(state.playback_history),
                "last_played": state.playback_history[-1]
                if state.playback_history
                else None,
                "current_playback_id": state.current_playback_id,
                "pending_playback_ids": list(state.pending_playback_counts.keys()),
            }
        return status

    async def clear_queue(
        self, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clear all pending audio from the queue for a session."""
        state = self._get_session(session_id, create=False)
        if state is None:
            return {
                "status": "cleared",
                "cleared_count": 0,
                "queue_size": 0,
                "session_id": self._normalize_session_id(session_id),
            }

        cleared = 0
        while True:
            try:
                item = state.audio_queue.get_nowait()
                playback_id = item.get("playback_id")
                if playback_id:
                    with state.lock:
                        remaining = (
                            state.pending_playback_counts.get(playback_id, 0) - 1
                        )
                        if remaining <= 0:
                            state.pending_playback_counts.pop(playback_id, None)
                        else:
                            state.pending_playback_counts[playback_id] = remaining
                state.audio_queue.task_done()
                cleared += 1
            except queue.Empty:
                break

        with state.lock:
            if not state.pending_playback_counts:
                state.current_playback_id = None

        logger.info(
            "Cleared %s items from audio queue for session %s",
            cleared,
            state.session_id,
        )

        return {
            "status": "cleared",
            "cleared_count": cleared,
            "queue_size": state.audio_queue.qsize(),
            "session_id": state.session_id,
        }

    async def stop_current(
        self, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stop current playback and clear the queue for a session."""
        state = self._get_session(session_id, create=False)
        if state is None:
            return {
                "status": "stopped",
                "message": "No active playback for session",
                "queue_cleared": 0,
                "session_id": self._normalize_session_id(session_id),
            }

        logger.info("Stopping audio playback for session %s", state.session_id)
        with state.lock:
            state.stop_requested = True
            process = state.current_process if state.is_playing else None

        if process:
            try:
                process.terminate()
                await asyncio.sleep(0.1)
                if process.poll() is None:
                    process.kill()
                logger.info("Audio process terminated for session %s", state.session_id)
            except Exception as exc:  # pragma: no cover - safety net
                logger.error(
                    "Error terminating audio process for session %s: %s",
                    state.session_id,
                    exc,
                )

        queue_result = await self.clear_queue(session_id)
        with state.lock:
            state.is_playing = False
            state.current_process = None
            state.stop_requested = False
            state.pending_playback_counts.clear()
            state.current_playback_id = None

        return {
            "status": "stopped",
            "message": "Audio playback stopped",
            "queue_cleared": queue_result["cleared_count"],
            "session_id": state.session_id,
        }

    def __del__(self) -> None:
        """Cleanup worker threads when the manager is destroyed."""
        with self._sessions_lock:
            sessions = list(self._sessions.values())

        for state in sessions:
            with state.lock:
                state.shutdown = True
            # Push sentinel to ensure worker exits promptly.
            state.audio_queue.put({"__shutdown__": True})


# Global instance
audio_queue_manager = AudioQueueManager()
