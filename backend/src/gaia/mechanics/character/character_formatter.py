"""Utilities for presenting character information."""

from __future__ import annotations

from typing import Any, Dict, Optional


class CharacterFormatter:
    """Helpers for formatting and resolving character-facing strings."""

    @staticmethod
    def resolve_display_name(
        character_id: Optional[str],
        *,
        character_manager: Optional[Any] = None,
        scene_summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Resolve the best display name for a character id."""
        if not character_id:
            return "Player"

        if character_id.lower() == "dm":
            return "Dungeon Master"

        character_obj = None
        if character_manager:
            try:
                character_obj = character_manager.get_character(character_id)
            except Exception:
                character_obj = None
        if character_obj and getattr(character_obj, "name", None):
            return str(character_obj.name)

        if isinstance(scene_summary, dict):
            participants = scene_summary.get("participants")
            if isinstance(participants, list):
                for participant in participants:
                    if not isinstance(participant, dict):
                        continue
                    participant_id = (
                        participant.get("character_id")
                        or participant.get("id")
                    )
                    if participant_id == character_id:
                        display_name = participant.get("display_name") or participant.get("name")
                        if display_name:
                            return str(display_name)

        fallback = character_id.split(":", 1)[-1] if ":" in character_id else character_id
        fallback = fallback.replace("_", " ").strip()
        return fallback.title() if fallback else "Player"
