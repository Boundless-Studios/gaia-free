"""WebSocket message handler for audio playback operations."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AudioWebSocketHandler:
    """Handles audio-related WebSocket messages and delegates to campaign broadcaster."""

    def __init__(self, broadcaster):
        """Initialize handler with campaign broadcaster instance.

        Args:
            broadcaster: CampaignBroadcaster instance for audio operations
        """
        self.broadcaster = broadcaster

    async def handle_audio_played(
        self,
        data: Dict[str, Any],
        session_id: str,
        connection_type: str = "player",
        connection: Optional[Any] = None
    ) -> None:
        """Handle audio_played message - marks chunks as played.

        Args:
            data: Message data containing campaign_id, chunk_ids, and optional connection_token
            session_id: Session ID from connection
            connection_type: "player" or "dm" for logging purposes
            connection: ConnectionInfo object for registry tracking (optional)
        """
        campaign_id = data.get("campaign_id") or session_id
        raw_chunk_ids = data.get("chunk_ids")
        chunk_id = data.get("chunk_id")
        connection_token = data.get("connection_token")

        # Parse chunk IDs from message
        chunk_ids: List[str] = []
        if isinstance(raw_chunk_ids, list):
            chunk_ids.extend(str(cid) for cid in raw_chunk_ids if cid)
        if chunk_id:
            chunk_ids.append(str(chunk_id))

        # Determine connection_id for registry tracking
        connection_id_str = None
        if connection and hasattr(connection, 'registry_connection_id'):
            connection_id_str = connection.registry_connection_id
        elif connection_token:
            # Look up connection by token from client message
            from gaia.connection.connection_registry import connection_registry
            conn_data = connection_registry.get_connection_by_token(connection_token)
            if conn_data and conn_data.get("session_id") == campaign_id:
                connection_id_str = conn_data.get("connection_id")
            elif conn_data:
                logger.warning(
                    "[AUDIO_WS] Connection token session mismatch | token=%s expected_session=%s actual_session=%s",
                    connection_token[:12] if connection_token else "None",
                    campaign_id,
                    conn_data.get("session_id")
                )

        # Mark each chunk as played
        if campaign_id and chunk_ids:
            for cid in chunk_ids:
                await self.broadcaster.mark_audio_played(campaign_id, cid)
                logger.debug(
                    "[%s] Marked audio chunk %s as played for %s",
                    connection_type.upper(),
                    cid,
                    campaign_id,
                )

                # Record chunk acknowledged and played in connection playback tracker
                if connection_id_str:
                    from gaia.connection.connection_playback_tracker import connection_playback_tracker
                    import uuid
                    try:
                        conn_id = uuid.UUID(connection_id_str)
                        chunk_uuid = uuid.UUID(cid)

                        # Record both acknowledged and played
                        connection_playback_tracker.record_chunk_acknowledged(conn_id, chunk_uuid)
                        connection_playback_tracker.record_chunk_played(conn_id, chunk_uuid)

                        logger.debug(
                            "[PLAYBACK_TRACKER] Recorded chunk %s acknowledged/played for connection %s",
                            cid,
                            connection_id_str,
                        )
                    except Exception as exc:
                        logger.warning(
                            "[PLAYBACK_TRACKER] Failed to record chunk acknowledged/played: %s", exc
                        )

    async def handle_start_audio_stream(
        self,
        data: Dict[str, Any],
        session_id: str
    ) -> None:
        """Handle start_audio_stream message - starts synchronized streaming.

        Args:
            data: Message data containing campaign_id and stream_url
            session_id: Session ID from connection
        """
        campaign_id = data.get("campaign_id") or session_id
        stream_url = data.get("stream_url")
        request_id = data.get("request_id")

        if campaign_id and stream_url:
            await self.broadcaster.start_synchronized_stream(
                campaign_id,
                stream_url,
                request_id=request_id
            )
            logger.info(
                "[DM] Started audio stream for %s: %s (request_id=%s)",
                campaign_id,
                stream_url,
                request_id
            )
        else:
            logger.warning(
                "[DM] Invalid start_audio_stream: missing campaign_id or stream_url"
            )

    async def handle_stop_audio_stream(
        self,
        data: Dict[str, Any],
        session_id: str
    ) -> None:
        """Handle stop_audio_stream message - stops synchronized streaming.

        Args:
            data: Message data containing campaign_id
            session_id: Session ID from connection
        """
        campaign_id = data.get("campaign_id") or session_id

        if campaign_id:
            await self.broadcaster.stop_synchronized_stream(campaign_id)
            logger.info("[DM] Stopped audio stream for %s", campaign_id)

    async def handle_clear_audio_queue(
        self,
        data: Dict[str, Any],
        session_id: str,
        websocket
    ) -> None:
        """Handle clear_audio_queue message - clears pending audio.

        Args:
            data: Message data containing campaign_id
            session_id: Session ID from connection
            websocket: WebSocket connection to send response
        """
        campaign_id = data.get("campaign_id") or session_id

        if campaign_id:
            result = self.broadcaster.clear_audio_queue(campaign_id)
            await websocket.send_json({
                "type": "audio_queue_cleared",
                "campaign_id": campaign_id,
                "timestamp": datetime.now().isoformat(),
                **result,
            })

    async def handle_get_stream_position(
        self,
        data: Dict[str, Any],
        session_id: str,
        websocket
    ) -> None:
        """Handle get_stream_position message - returns current playback position.

        Args:
            data: Message data containing campaign_id
            session_id: Session ID from connection
            websocket: WebSocket connection to send response
        """
        campaign_id = data.get("campaign_id") or session_id

        if campaign_id:
            position_data = self.broadcaster.get_stream_position(campaign_id)
            if position_data:
                await websocket.send_json({
                    "type": "stream_position",
                    **position_data,
                })
