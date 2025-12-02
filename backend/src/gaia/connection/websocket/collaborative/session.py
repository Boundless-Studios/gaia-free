"""CollaborativeSession manages a Yjs document and players for a session."""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass
from pycrdt import Doc, Text

logger = logging.getLogger(__name__)


@dataclass
class PlayerInfo:
    """Information about a registered player."""
    name: str
    last_heartbeat: datetime
    disconnected_at: Optional[datetime] = None


class CollaborativeSession:
    """Manages collaborative document state and player roster for a session."""

    def __init__(self, session_id: str):
        """Initialize a collaborative session.

        Args:
            session_id: Unique identifier for this collaborative session
        """
        self.session_id = session_id
        self.doc = Doc()
        self.players: Dict[str, PlayerInfo] = {}  # {player_id: PlayerInfo}
        self.player_counter = 0  # Counter for auto-assigning player numbers
        logger.info("[CollabSession] Initialized session=%s", session_id)

    def register_player(self, player_id: str, player_name: Optional[str] = None) -> tuple[str, bool]:
        """Register a player in the session.

        Args:
            player_id: Unique player identifier
            player_name: Optional player name (auto-assigned if None)

        Returns:
            Tuple of (assigned_name, is_new_player)
        """
        now = datetime.now()

        if player_id in self.players:
            # Player reconnecting - clear disconnected_at and update heartbeat
            player_info = self.players[player_id]
            player_info.disconnected_at = None
            player_info.last_heartbeat = now

            # Update player name if provided and different
            name_changed = False
            if player_name and player_name != player_info.name:
                old_name = player_info.name
                # Update the label in the document
                if self.rename_player_label(old_name, player_name):
                    player_info.name = player_name
                    name_changed = True
                    logger.info("[CollabSession] Player %s renamed to %s on reconnection",
                               old_name, player_name)

            logger.info("[CollabSession] Player %s (%s) reconnected (total: %d)",
                       player_info.name, player_id, len(self.players))
            return player_info.name, name_changed

        # Auto-assign player number if no name provided
        if not player_name:
            self.player_counter += 1
            player_name = f"Player {self.player_counter}"
            logger.debug("[CollabSession] Auto-assigned name %s to player %s", player_name, player_id)

        # Create new player info
        self.players[player_id] = PlayerInfo(
            name=player_name,
            last_heartbeat=now
        )
        logger.info("[CollabSession] Registered NEW player %s (%s) in session=%s (total: %d, all_players: %s)",
                   player_name, player_id, self.session_id, len(self.players), list(self.players.keys()))

        return player_name, True

    def unregister_player(self, player_id: str) -> Optional[str]:
        """Unregister a player from the session.

        Args:
            player_id: Player to unregister

        Returns:
            Player name if they were registered, None otherwise
        """
        player_info = self.players.pop(player_id, None)
        if player_info:
            logger.info("[CollabSession] Unregistered player %s from session=%s",
                       player_info.name, self.session_id)
            return player_info.name
        return None

    def get_player_name(self, player_id: str) -> Optional[str]:
        """Get the name of a registered player.

        Args:
            player_id: Player identifier

        Returns:
            Player name or None if not registered
        """
        player_info = self.players.get(player_id)
        return player_info.name if player_info else None

    def get_all_players(self) -> List[Dict[str, str]]:
        """Get all currently connected players (excludes disconnected seats)."""
        return [
            {"id": pid, "name": pinfo.name}
            for pid, pinfo in self.players.items()
            if pinfo.disconnected_at is None
        ]

    def get_state_update(self) -> bytes:
        """Get the current document state as a Yjs update.

        Returns:
            Serialized Yjs update bytes
        """
        return self.doc.get_update()

    def has_text_content(self) -> bool:
        """Check if the document has any actual text content.

        Returns:
            True if document contains non-empty text
        """
        try:
            text_obj = self.doc.get('codemirror', type=Text)
            return bool(str(text_obj).strip())
        except Exception:
            return False

    def apply_update(self, update: bytes) -> None:
        """Apply a Yjs update to the server-side document.

        CRITICAL: This keeps the server-side YJS doc in sync with frontend edits.
        Without this, keyboard typing would be overwritten by voice transcription
        because append_to_player_section reads from a stale server-side doc.

        Args:
            update: Serialized Yjs update bytes from a client
        """
        try:
            self.doc.apply_update(update)
            logger.debug("[CollabSession] Applied YJS update (%d bytes) to session=%s",
                        len(update), self.session_id)
        except Exception as e:
            logger.error("[CollabSession] Failed to apply YJS update: %s", e)

    def build_template(self) -> str:
        """Create the default collaborative document layout from connected players.

        Returns:
            Template string with player labels
        """
        labels = [
            f"[{pinfo.name}]:"
            for pinfo in self.players.values()
            if pinfo.name and pinfo.name.upper() != 'DM'  # Exclude DM from player labels
        ]
        return "\n\n".join(labels)

    def initialize_document_with_player(self, player_name: str) -> bool:
        """Initialize or append a player's name label to the document.

        Args:
            player_name: Name of the player to add

        Returns:
            True if document was modified, False otherwise
        """
        ytext = self.doc.get("codemirror", type=Text)
        name_label = f"[{player_name}]:"

        if len(ytext) == 0:
            # First player - initialize document
            ytext += name_label
            logger.debug("[CollabSession] Initialized document with first player: %s", player_name)
            return True
        else:
            # Subsequent player - append their name label if not exists
            current_text = str(ytext)
            if name_label not in current_text:
                ytext += f"\n\n{name_label}"
                logger.debug("[CollabSession] Appended player %s to document", player_name)
                return True

        return False

    def rename_player_label(self, old_name: str, new_name: str) -> bool:
        """Rename a player's label in the document.

        Args:
            old_name: Current player name in the document
            new_name: New player name to use

        Returns:
            True if label was renamed, False otherwise
        """
        text_obj = self.doc.get('codemirror', type=Text)
        full_text = str(text_obj)
        old_label = f"[{old_name}]:"
        new_label = f"[{new_name}]:"
        label_start = full_text.find(old_label)

        if label_start == -1:
            logger.warning("[CollabSession] Cannot rename - old label not found: %s", old_label)
            return False

        # Replace the label
        label_end = label_start + len(old_label)
        with self.doc.transaction():
            del text_obj[label_start:label_end]
            text_obj[label_start:label_start] = new_label

        logger.info("[CollabSession] Renamed player label from %s to %s", old_label, new_label)
        return True

    @staticmethod
    def _merge_with_dedup(base: str, incoming: str) -> str:
        """Merge text while avoiding duplicated phrases between base and incoming."""
        incoming = incoming or ""
        if not base:
            return incoming
        if not incoming:
            return base

        if incoming.startswith(base):
            return incoming
        if incoming in base:
            return base

        overlap = min(len(base), len(incoming))
        while overlap and not base.endswith(incoming[:overlap]):
            overlap -= 1

        if overlap:
            return base + incoming[overlap:]
        return f"{base} {incoming}"

    @staticmethod
    def _strip_prefix(text: str, prefix: str) -> str:
        """Remove a prefix (or first occurrence) while trimming whitespace."""
        if not prefix or not text:
            return text
        if text.startswith(prefix):
            return text[len(prefix):].lstrip()
        if prefix in text:
            return text.replace(prefix, "", 1).strip()
        return text

    def clear_player_section(self, player_id: str) -> int:
        """Clear only a specific player's content section (keeping their label).

        Args:
            player_id: Player whose section should be cleared

        Returns:
            Number of characters cleared
        """
        player_info = self.players.get(player_id)
        if not player_info:
            logger.warning("[CollabSession] Cannot clear section for unknown player=%s", player_id)
            return 0

        text_obj = self.doc.get('codemirror', type=Text)
        full_text = str(text_obj)
        player_label = f"[{player_info.name}]:"
        label_start = full_text.find(player_label)

        if label_start == -1:
            logger.warning("[CollabSession] Player label not found: %s", player_label)
            return 0

        content_start = label_start + len(player_label)

        # Find next player label or end of document
        next_label_pos = full_text.find("\n[", content_start)
        content_end = next_label_pos if next_label_pos != -1 else len(full_text)

        # Delete only this player's content (keep the label)
        delete_length = content_end - content_start
        if delete_length > 0:
            with self.doc.transaction():
                del text_obj[content_start:content_end]
            logger.info("[CollabSession] Cleared %d chars for player=%s", delete_length, player_info.name)
            return delete_length

        return 0

    def clear_all_player_sections(self) -> int:
        """Clear all player content sections (keeping labels).

        Returns:
            Total number of characters cleared
        """
        logger.info("[CollabSession] Clearing all player sections in session=%s", self.session_id)

        text_obj = self.doc.get('codemirror', type=Text)
        full_text = str(text_obj)

        # Find all player label positions
        player_positions = []
        for player_id, player_info in self.players.items():
            player_label = f"[{player_info.name}]:"
            label_start = full_text.find(player_label)
            if label_start != -1:
                player_positions.append((label_start, player_info.name, player_label))

        # Sort by position (descending) to delete from end to start
        player_positions.sort(reverse=True)

        total_cleared = 0
        with self.doc.transaction():
            # Clear each player's section
            for label_start, player_name, player_label in player_positions:
                content_start = label_start + len(player_label)

                # Find next player label or end of document
                next_label_pos = full_text.find("\n[", content_start)
                content_end = next_label_pos if next_label_pos != -1 else len(full_text)

                # Delete this player's content (keep the label)
                delete_length = content_end - content_start
                if delete_length > 0:
                    del text_obj[content_start:content_end]
                    total_cleared += delete_length
                    logger.debug("[CollabSession] Cleared %d chars for player %s", delete_length, player_name)

                    # Update full_text for next iteration
                    full_text = full_text[:content_start] + full_text[content_end:]

        logger.info("[CollabSession] Cleared %d total chars from %d players",
                   total_cleared, len(player_positions))
        return total_cleared

    def remove_player_and_label(self, player_id: str) -> bool:
        """Remove a player's label and content from the document.

        Args:
            player_id: Player to remove

        Returns:
            True if player was removed, False otherwise
        """
        player_info = self.players.get(player_id)
        if not player_info:
            logger.warning("[CollabSession] Cannot remove unknown player=%s", player_id)
            return False

        text_obj = self.doc.get('codemirror', type=Text)
        full_text = str(text_obj)
        player_label = f"[{player_info.name}]:"
        label_start = full_text.find(player_label)

        if label_start == -1:
            logger.warning("[CollabSession] Player label not found for removal: %s", player_label)
            # Still remove from players dict even if label not found
            del self.players[player_id]
            return True

        # Find end of this player's section (start of next label or end of doc)
        next_label_pos = full_text.find("\n[", label_start + len(player_label))
        section_end = next_label_pos if next_label_pos != -1 else len(full_text)

        # Remove leading newlines before the label if this isn't the first label
        delete_start = label_start
        if label_start > 0 and full_text[label_start - 1] == '\n':
            # Check if there's a double newline before
            if label_start > 1 and full_text[label_start - 2] == '\n':
                delete_start = label_start - 2
            else:
                delete_start = label_start - 1

        # Delete the entire section including label
        delete_length = section_end - delete_start
        if delete_length > 0:
            with self.doc.transaction():
                del text_obj[delete_start:section_end]
            logger.info("[CollabSession] Removed %d chars (label + content) for player %s",
                       delete_length, player_info.name)

        # Remove from players dict
        del self.players[player_id]
        logger.info("[CollabSession] Removed player %s (%s) from session=%s (remaining: %d)",
                   player_info.name, player_id, self.session_id, len(self.players))
        return True

    def append_to_player_section(self, player_id: str, text: str) -> bool:
        """Append text to a player's content section.

        Pure append: STT service already converts ElevenLabs cumulative text to delta.
        We just append whatever we receive. No deduplication logic needed.

        Args:
            player_id: Player identifier (from connection registration)
            text: Text to append (already a delta from STT service)

        Returns:
            True if document was modified, False otherwise
        """
        player_info = self.players.get(player_id)
        if not player_info:
            logger.warning("[CollabSession] Cannot append for unknown player_id=%s", player_id)
            return False

        final_text = text.strip()
        if not final_text:
            logger.debug("[CollabSession] Empty text, nothing to append for player_id=%s", player_id)
            return False

        text_obj = self.doc.get('codemirror', type=Text)
        full_text = str(text_obj)
        player_label = f"[{player_info.name}]:"
        label_start = full_text.find(player_label)

        if label_start == -1:
            logger.warning("[CollabSession] Player label not found for player_id=%s name=%s",
                          player_id, player_info.name)
            return False

        content_start = label_start + len(player_label)

        # Find next player label or end of document
        next_label_pos = full_text.find("\n[", content_start)
        content_end = next_label_pos if next_label_pos != -1 else len(full_text)

        # Get current content in the section
        current_content = full_text[content_start:content_end].strip()

        # Pure append: add space separator if there's existing content
        if current_content:
            new_content = f"{current_content} {final_text}"
        else:
            new_content = final_text

        # Update the document
        with self.doc.transaction():
            if content_end > content_start:
                del text_obj[content_start:content_end]
            text_obj[content_start:content_start] = new_content

        logger.info("[CollabSession] Appended %d chars to player_id=%s (total now: %d)",
                   len(final_text), player_id, len(new_content))
        return True

    def reset_voice_tracking(self, player_id: str) -> None:
        """Reset voice transcription tracking for a player starting a new session.

        No-op: With pure append architecture, no tracking to reset.
        Kept for backward compatibility with frontend.

        Args:
            player_id: Player identifier
        """
        logger.debug("[CollabSession] Voice session start for player_id=%s (no tracking needed)", player_id)

    def cleanup_stale_players(self, grace_period_seconds: int = 10) -> List[str]:
        """Remove players who have been disconnected longer than grace period.

        This only removes players from the roster, NOT their content from the document.
        This preserves player input even if they temporarily disconnect, allowing them
        to continue where they left off when they reconnect.

        Args:
            grace_period_seconds: How long to wait before removing disconnected players

        Returns:
            List of player IDs that were removed from the roster
        """
        now = datetime.now()
        removed_players = []

        # Find players to remove (can't modify dict during iteration)
        stale_player_ids = []
        for player_id, player_info in self.players.items():
            if player_info.disconnected_at:
                elapsed = (now - player_info.disconnected_at).total_seconds()
                if elapsed > grace_period_seconds:
                    stale_player_ids.append(player_id)
                    logger.debug("[CollabSession] Player %s (%s) stale: disconnected %d seconds ago",
                               player_info.name, player_id, int(elapsed))

        # Remove stale players from roster ONLY (preserve their document content)
        # This allows players to reconnect and continue where they left off
        for player_id in stale_player_ids:
            player_info = self.players.pop(player_id, None)
            if player_info:
                removed_players.append(player_id)
                logger.info("[CollabSession] Removed stale player %s (%s) from roster (content preserved)",
                           player_info.name, player_id)

        if removed_players:
            logger.info("[CollabSession] Cleaned up %d stale players from session=%s (content preserved)",
                       len(removed_players), self.session_id)

        return removed_players
