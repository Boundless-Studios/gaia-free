"""Message handlers for collaborative editing WebSocket messages."""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from .session import CollaborativeSession

logger = logging.getLogger(__name__)


class CollaborativeMessageHandler:
    """Handles incoming WebSocket messages for collaborative editing."""

    def __init__(self, session: CollaborativeSession, websocket: WebSocket, broadcaster):
        """Initialize message handler.

        Args:
            session: The collaborative session
            websocket: Client WebSocket connection
            broadcaster: Campaign broadcaster for multi-client sync
        """
        self.session = session
        self.websocket = websocket
        self.broadcaster = broadcaster
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None

    async def handle_register(self, data: Dict[str, Any]) -> None:
        """Handle player registration.

        Args:
            data: Message data containing playerId and optional playerName
        """
        player_id = data.get("playerId")
        player_name = data.get("playerName")

        if not player_id:
            logger.warning("[CollabHandler] Registration missing playerId")
            return

        # Register player and get assigned name
        assigned_name, is_new = self.session.register_player(player_id, player_name)
        self.player_id = player_id
        self.player_name = assigned_name

        # Initialize document with player's label if they're new
        doc_modified = False
        if is_new:
            doc_modified = self.session.initialize_document_with_player(assigned_name)

        # Send initial state to this player
        state_update = self.session.get_state_update()
        all_players = self.session.get_all_players()

        await self.websocket.send_json({
            "type": "initial_state",
            "sessionId": self.session.session_id,
            "update": list(state_update),
            "assignedName": assigned_name,
            "allPlayers": all_players,
            "timestamp": datetime.now().isoformat()
        })
        logger.info("[CollabHandler] Sent initial_state to player %s (size=%d bytes)",
                   assigned_name, len(state_update))

        # Broadcast document update to other players if we modified it
        if doc_modified:
            await self._broadcast_to_others({
                "type": "yjs_update",
                "sessionId": self.session.session_id,
                "playerId": "_server_",
                "update": list(state_update),
                "timestamp": datetime.now().isoformat()
            })

        # Broadcast updated player list
        await self._broadcast_player_list()

    async def handle_reset_document(self, data: Dict[str, Any]) -> None:
        """Handle request to reset a player's section.

        Args:
            data: Message data containing playerId
        """
        requester_id = data.get("playerId") or self.player_id
        requester_name = self.session.get_player_name(requester_id)

        if not requester_name:
            logger.warning("[CollabHandler] Reset requested by unknown player=%s", requester_id)
            return

        logger.info("[CollabHandler] Clearing section for player=%s (%s)",
                   requester_name, requester_id)

        # Clear the player's section
        chars_cleared = self.session.clear_player_section(requester_id)

        if chars_cleared > 0:
            # Broadcast the update
            state_update = self.session.get_state_update()
            await self.broadcaster.broadcast_campaign_update(
                self.session.session_id,
                "yjs_update",
                {
                    "sessionId": self.session.session_id,
                    "playerId": "_server_",
                    "update": list(state_update),
                    "timestamp": datetime.now().isoformat()
                }
            )

    async def handle_dm_submit_turn(self, data: Dict[str, Any]) -> None:
        """Handle DM submit turn - clears all player sections.

        Args:
            data: Message data (not currently used)
        """
        logger.info("[CollabHandler] DM submit - clearing all player sections")

        # Clear all player sections
        total_cleared = self.session.clear_all_player_sections()

        if total_cleared > 0:
            # Broadcast the update
            state_update = self.session.get_state_update()
            await self.broadcaster.broadcast_campaign_update(
                self.session.session_id,
                "yjs_update",
                {
                    "sessionId": self.session.session_id,
                    "playerId": "_server_",
                    "update": list(state_update),
                    "timestamp": datetime.now().isoformat()
                }
            )

    async def handle_yjs_update(self, data: Dict[str, Any]) -> None:
        """Handle Yjs CRDT update and broadcast to other clients.

        CRITICAL: We must apply the update to server-side doc before broadcasting.
        This keeps the server-side YJS in sync with frontend keyboard edits.
        Without this, voice transcription would read stale state and overwrite typed text.

        Args:
            data: Message data containing update payload
        """
        update_payload = data.get("update")
        if update_payload is None:
            logger.warning("[CollabHandler] yjs_update missing payload")
            return

        # Apply update to server-side YJS doc to keep it in sync with frontend
        if isinstance(update_payload, (list, tuple)):
            update_bytes = bytes(update_payload)
            self.session.apply_update(update_bytes)

        await self.broadcaster.broadcast_campaign_update(
            self.session.session_id,
            "yjs_update",
            {
                "sessionId": self.session.session_id,
                "playerId": data.get("playerId"),
                "update": update_payload,
                "timestamp": data.get("timestamp", datetime.now().isoformat())
            }
        )
        logger.debug("[CollabHandler] Broadcast yjs_update from player=%s size=%s",
                    data.get("playerId"),
                    len(update_payload) if isinstance(update_payload, (list, tuple)) else "unknown")

    async def handle_awareness_update(self, data: Dict[str, Any]) -> None:
        """Handle awareness update (cursor/selection) and broadcast.

        Args:
            data: Message data containing awareness update payload
        """
        update_payload = data.get("update")
        if update_payload is None:
            logger.warning("[CollabHandler] awareness_update missing payload")
            return

        await self.broadcaster.broadcast_campaign_update(
            self.session.session_id,
            "awareness_update",
            {
                "sessionId": self.session.session_id,
                "playerId": data.get("playerId"),
                "update": update_payload,
                "timestamp": data.get("timestamp", datetime.now().isoformat())
            }
        )
        logger.debug("[CollabHandler] Broadcast awareness_update from player=%s",
                    data.get("playerId"))

    async def handle_request_state(self, data: Dict[str, Any]) -> None:
        """Handle request for current document state.

        Args:
            data: Message data (not currently used)
        """
        state_update = self.session.get_state_update()
        all_players = self.session.get_all_players()

        await self.websocket.send_json({
            "type": "initial_state",
            "sessionId": self.session.session_id,
            "update": list(state_update),
            "assignedName": self.player_name,
            "allPlayers": all_players,
            "timestamp": datetime.now().isoformat()
        })
        logger.info("[CollabHandler] Sent state refresh to player %s", self.player_name)

    async def handle_voice_transcription(self, data: Dict[str, Any]) -> None:
        """Handle voice transcription from frontend.

        Simplified architecture:
        - Partials: Broadcast as visual overlay only (no YJS modification)
        - Finals: Append text to player's section and broadcast YJS update

        Args:
            data: Message data containing text and is_partial flag
        """
        

        if not self.player_id:
            logger.warning("[CollabHandler] voice_transcription received but player not registered")
            return

        text = data.get("text", "").strip()
        is_partial = data.get("is_partial", False)

        if not text:
            return

        logger.debug(f"Updating transcribed state from frontend: {text}")
        try:
            if is_partial:
                # Partials: Send only to sender as visual overlay - don't modify YJS
                await self.websocket.send_json({
                    "type": "partial_overlay",
                    "sessionId": self.session.session_id,
                    "playerId": self.player_id,
                    "text": text,
                    "timestamp": datetime.now().isoformat()
                })
                logger.debug("[CollabHandler] Sent partial overlay to sender player_id=%s len=%d",
                           self.player_id, len(text))
            else:
                # Finals: Append to player's section (simple append-only)
                doc_modified = self.session.append_to_player_section(
                    self.player_id,
                    text
                )

                if doc_modified:
                    # Clear any partial overlay for this player
                    await self.broadcaster.broadcast_campaign_update(
                        self.session.session_id,
                        "partial_overlay",
                        {
                            "sessionId": self.session.session_id,
                            "playerId": self.player_id,
                            "text": "",  # Empty text clears overlay
                            "timestamp": datetime.now().isoformat()
                        }
                    )

                    # Broadcast Y.js update to all clients
                    state_update = self.session.get_state_update()
                    await self.broadcaster.broadcast_campaign_update(
                        self.session.session_id,
                        "yjs_update",
                        {
                            "sessionId": self.session.session_id,
                            "playerId": self.player_id,
                            "update": list(state_update),
                            "source": "voice",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    logger.info("[CollabHandler] Appended voice transcription for player_id=%s len=%d",
                              self.player_id, len(text))

        except Exception as e:
            logger.error("[CollabHandler] Error handling voice transcription: %s", e, exc_info=True)

    async def handle_voice_session_start(self, data: Dict[str, Any]) -> None:
        """Handle the start of a new voice recording session.

        Resets tracking so that new transcriptions start fresh,
        respecting any edits the user made to the textarea.

        Args:
            data: Message data (not currently used)
        """
        if not self.player_id:
            logger.warning("[CollabHandler] voice_session_start received but player not registered")
            return

        self.session.reset_voice_tracking(self.player_id)
        logger.info("[CollabHandler] Voice session started for player %s (%s)",
                   self.player_name, self.player_id)

    async def _broadcast_to_others(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connections except this one.

        Args:
            message: Message to broadcast
        """
        state = self.broadcaster._get_state(self.session.session_id)
        for conn in state.player_connections:
            if conn.websocket != self.websocket:
                try:
                    await conn.websocket.send_json(message)
                except Exception as exc:
                    logger.warning("[CollabHandler] Failed to broadcast to player: %s", exc)

    async def _broadcast_to_all(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to ALL connections including self.

        Used for voice transcription where sender needs to see their own partial.

        Args:
            message: Message to broadcast
        """
        state = self.broadcaster._get_state(self.session.session_id)
        for conn in state.player_connections:
            try:
                await conn.websocket.send_json(message)
            except Exception as exc:
                logger.warning("[CollabHandler] Failed to broadcast to player: %s", exc)

    async def _broadcast_player_list(self) -> None:
        """Broadcast the current player list to all clients."""
        players_payload = self.session.get_all_players()
        await self.broadcaster.broadcast_campaign_update(
            self.session.session_id,
            "player_list",
            {
                "sessionId": self.session.session_id,
                "players": players_payload,
            }
        )

    async def handle_message(self, raw_message: str) -> None:
        """Route incoming message to appropriate handler.

        Args:
            raw_message: Raw JSON message string
        """
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type")

            logger.debug("[CollabHandler] Received %s from session=%s", msg_type, self.session.session_id)

            # Route to appropriate handler
            handlers = {
                "register": self.handle_register,
                "reset_document": self.handle_reset_document,
                "dm_submit_turn": self.handle_dm_submit_turn,
                "yjs_update": self.handle_yjs_update,
                "awareness_update": self.handle_awareness_update,
                "request_state": self.handle_request_state,
                # Voice transcription (text from STT, routed by player_id)
                "voice_transcription": self.handle_voice_transcription,
                # Voice session management
                "voice_session_start": self.handle_voice_session_start,
            }

            handler = handlers.get(msg_type)
            if handler:
                await handler(data)
            else:
                logger.info("[CollabHandler] Unknown message type: %s", msg_type)

        except json.JSONDecodeError as e:
            logger.error("[CollabHandler] Invalid JSON: %s", e)
        except WebSocketDisconnect:
            # Client disconnected during message processing - re-raise for main loop to handle
            logger.debug("[CollabHandler] Client disconnected during message processing")
            raise
        except Exception as e:
            logger.error("[CollabHandler] Error processing message: %s", e, exc_info=True)
