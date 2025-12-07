"""Socket.IO-based broadcaster for campaign updates.

This module provides the broadcasting functionality using Socket.IO,
replacing the manual WebSocket connection management.

It's designed to be a drop-in replacement for the broadcast methods
in campaign_broadcaster.py while using Socket.IO's room-based routing.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from gaia.connection.socketio_server import (
    sio,
    broadcast_to_room,
    broadcast_to_user,
    get_unique_user_count,
    get_room_users,
)

logger = logging.getLogger(__name__)


class SocketIOBroadcaster:
    """Broadcasts campaign events using Socket.IO.

    This replaces the manual connection tracking in CampaignBroadcaster
    with Socket.IO's built-in room management.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Cache for last campaign state (for late joiners)
        self._campaign_states: Dict[str, Dict] = {}

    # =========================================================================
    # Connection Info (delegated to Socket.IO)
    # =========================================================================

    async def get_connected_count(self, session_id: str) -> int:
        """Get count of unique users connected to a session."""
        return await get_unique_user_count(session_id)

    async def get_connected_users(self, session_id: str) -> List[Dict]:
        """Get list of connected users in a session."""
        return await get_room_users(session_id)

    async def get_connected_user_ids(self, session_id: str) -> List[str]:
        """Return unique user IDs for a session (used by audio queueing)."""
        users = await get_room_users(session_id)
        return list({u["user_id"] for u in users if u.get("user_id")})

    # =========================================================================
    # Campaign State
    # =========================================================================

    def get_cached_campaign_state(self, session_id: str) -> Optional[Dict]:
        """Get cached campaign state for late joiners."""
        return self._campaign_states.get(session_id)

    def set_cached_campaign_state(self, session_id: str, state: Optional[Dict]) -> None:
        """Cache campaign state for late joiners."""
        if state:
            self._campaign_states[session_id] = state
        else:
            self._campaign_states.pop(session_id, None)

    # =========================================================================
    # Broadcast Methods
    # =========================================================================

    async def broadcast_campaign_update(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Broadcast a campaign update to all clients in a session.

        Args:
            session_id: Campaign/session ID
            event_type: Event type (e.g., 'narrative_chunk', 'campaign_updated')
            data: Event data
        """
        message = {
            "type": event_type,
            "campaign_id": session_id,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        # Update state cache for certain events
        if event_type in {"campaign_loaded", "campaign_updated", "campaign_active"}:
            if "structured_data" in data:
                cached_state = self._campaign_states.get(session_id, {}) or {}
                structured_data = data.get("structured_data") or {}
                if isinstance(structured_data, dict) and isinstance(cached_state, dict):
                    merged_state = {**cached_state, **structured_data}
                else:
                    merged_state = structured_data
                self._campaign_states[session_id] = merged_state
        elif event_type == "player_options":
            if "options" in data:
                cached = self._campaign_states.get(session_id, {}) or {}
                if not isinstance(cached, dict):
                    cached = {}
                cached["player_options"] = data["options"]
                self._campaign_states[session_id] = cached
        elif event_type == "personalized_player_options":
            # Merge personalized options into cached state for late joiners
            if "personalized_player_options" in data:
                cached = self._campaign_states.get(session_id, {}) or {}
                if not isinstance(cached, dict):
                    cached = {}
                cached["personalized_player_options"] = data["personalized_player_options"]
                self._campaign_states[session_id] = cached
        elif event_type == "pending_observations":
            # Merge pending observations into cached state for late joiners
            if "pending_observations" in data:
                cached = self._campaign_states.get(session_id, {}) or {}
                if not isinstance(cached, dict):
                    cached = {}
                cached["pending_observations"] = data["pending_observations"]
                self._campaign_states[session_id] = cached
        elif event_type == "campaign_deactivated":
            self._campaign_states.pop(session_id, None)

        await broadcast_to_room(session_id, event_type, message)

        count = await get_unique_user_count(session_id)
        self.logger.debug(
            "[SocketIO] Broadcast %s to %d users in session %s",
            event_type, count, session_id
        )

    async def broadcast_to_dm(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Broadcast to DM connections only.

        Note: With Socket.IO, we identify DMs by their connection_type
        stored in the session data. Uses direct SID targeting to avoid
        issues with null user_id matching all anonymous users.
        """
        message = {
            "type": event_type,
            "campaign_id": session_id,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        # Get all users and filter to DMs - use SID targeting for safety
        users = await get_room_users(session_id)
        for user in users:
            if user.get("connection_type") == "dm":
                # Use SID directly instead of user_id to avoid null user_id
                # matching all anonymous users when DISABLE_AUTH=true
                user_sid = user.get("sid")
                if user_sid:
                    await sio.emit(event_type, message, to=user_sid, namespace="/campaign")
                elif user.get("user_id"):
                    # Fallback to user_id targeting only if we have a real user_id
                    await broadcast_to_user(session_id, user["user_id"], event_type, message)

    async def broadcast_narrative_chunk(
        self,
        session_id: str,
        content: str,
        is_final: bool = False,
    ) -> None:
        """Broadcast narrative chunk to all players in a session."""
        await self.broadcast_campaign_update(
            session_id,
            "narrative_chunk",
            {"content": content, "is_final": is_final},
        )

    async def broadcast_player_response_chunk(
        self,
        session_id: str,
        content: str,
        is_final: bool = False,
    ) -> None:
        """Broadcast player response chunk to all players in a session."""
        await self.broadcast_campaign_update(
            session_id,
            "player_response_chunk",
            {"content": content, "is_final": is_final},
        )

    async def broadcast_player_options(
        self,
        session_id: str,
        options: List[str],
    ) -> None:
        """Broadcast player options to all players in a session."""
        await self.broadcast_campaign_update(
            session_id,
            "player_options",
            {"options": options},
        )

    async def broadcast_metadata_update(
        self,
        session_id: str,
        metadata: Dict,
    ) -> None:
        """Broadcast metadata update to all players in a session."""
        await self.broadcast_campaign_update(
            session_id,
            "metadata_update",
            {"metadata": metadata},
        )

    async def broadcast_seat_updated(
        self,
        session_id: str,
        seat_data: Dict,
    ) -> None:
        """Broadcast seat update to all players and DM in a session."""
        await self.broadcast_campaign_update(
            session_id,
            "room.seat_updated",
            {"seat": seat_data},
        )

    async def broadcast_seat_character_update(
        self,
        session_id: str,
        seat_id: str,
        character_id: str,
    ) -> None:
        """Broadcast that a seat has a new character assignment."""
        await self.broadcast_campaign_update(
            session_id,
            "room.seat_character_updated",
            {"seat_id": seat_id, "character_id": character_id},
        )

    async def broadcast_campaign_started(
        self,
        session_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """Broadcast standard room.campaign_started payload."""
        self.logger.info(
            "[SocketIO] room.campaign_started broadcast | session_id=%s",
            session_id,
        )
        await self.broadcast_campaign_update(
            session_id,
            "room.campaign_started",
            payload,
        )

    async def broadcast_player_vacated(
        self,
        session_id: str,
        seat_id: str,
        previous_owner_id: str,
    ) -> None:
        """Broadcast DM-forced seat removal."""
        await self.broadcast_campaign_update(
            session_id,
            "room.player_vacated",
            {
                "seat_id": seat_id,
                "previous_owner_id": previous_owner_id,
                "reason": "vacated_by_dm",
            },
        )

    async def broadcast_dm_joined(
        self,
        session_id: str,
        user_id: str,
        dm_joined_at: Optional[str] = None,
    ) -> None:
        """Broadcast that DM has joined the room."""
        await self.broadcast_campaign_update(
            session_id,
            "room.dm_joined",
            {
                "user_id": user_id,
                "dm_joined_at": dm_joined_at,
                "room_status": "active",
            },
        )

    async def broadcast_dm_left(
        self,
        session_id: str,
        user_id: str,
    ) -> None:
        """Broadcast that DM has left the room."""
        await self.broadcast_campaign_update(
            session_id,
            "room.dm_left",
            {
                "user_id": user_id,
                "room_status": "waiting_for_dm",
            },
        )

    # =========================================================================
    # Audio Broadcasts
    # =========================================================================

    async def broadcast_audio_chunk(
        self,
        session_id: str,
        chunk_data: Dict[str, Any],
        sequence_number: int,
        playback_group: str,
    ) -> None:
        """Broadcast audio chunk to all clients."""
        await self.broadcast_campaign_update(
            session_id,
            "audio_chunk_ready",
            {
                "chunk": chunk_data,
                "sequence_number": sequence_number,
                "playback_group": playback_group,
            },
        )

    async def broadcast_audio_stream_started(
        self,
        session_id: str,
        text: str,
        chunk_ids: List[str],
    ) -> None:
        """Broadcast that audio streaming has started."""
        await self.broadcast_campaign_update(
            session_id,
            "audio_stream_started",
            {"text": text, "chunk_ids": chunk_ids},
        )

    async def broadcast_audio_stream_stopped(
        self,
        session_id: str,
    ) -> None:
        """Broadcast that audio streaming has stopped."""
        await self.broadcast_campaign_update(
            session_id,
            "audio_stream_stopped",
            {},
        )

    async def broadcast_sfx_available(
        self,
        session_id: str,
        sfx_data: Dict[str, Any],
    ) -> None:
        """Broadcast sound effect availability."""
        await self.broadcast_campaign_update(
            session_id,
            "sfx_available",
            sfx_data,
        )

    # =========================================================================
    # Collaborative Editing Broadcasts
    # =========================================================================

    async def broadcast_yjs_update(
        self,
        session_id: str,
        update: List[int],
        player_id: str,
        source: str = "keyboard",
        skip_sid: Optional[str] = None,
    ) -> None:
        """Broadcast Yjs CRDT update to room."""
        await broadcast_to_room(
            session_id,
            "yjs_update",
            {
                "sessionId": session_id,
                "playerId": player_id,
                "update": update,
                "source": source,
                "timestamp": datetime.now().isoformat(),
            },
            skip_sid=skip_sid,
        )

    async def broadcast_player_list(
        self,
        session_id: str,
        players: List[Dict[str, str]],
    ) -> None:
        """Broadcast updated player list."""
        await self.broadcast_campaign_update(
            session_id,
            "player_list",
            {"sessionId": session_id, "players": players},
        )

    async def broadcast_partial_overlay(
        self,
        session_id: str,
        player_id: str,
        text: str,
    ) -> None:
        """Broadcast partial transcription overlay."""
        await self.broadcast_campaign_update(
            session_id,
            "partial_overlay",
            {"playerId": player_id, "text": text},
        )


# Singleton instance
socketio_broadcaster = SocketIOBroadcaster()
