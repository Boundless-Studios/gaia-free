"""Helpers for presenting scene character presence consistently."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from gaia.models.character.enums import CharacterRole
from gaia.models.scene_info import SceneInfo
from gaia.models.scene_participant import SceneParticipant


@dataclass
class ScenePresenceView:
    """Structured view over NPC presence for downstream consumers."""

    npc_entries: List[Dict[str, Any]]
    npc_display_names: Dict[str, str]
    active_character_entries: List[Dict[str, str]]


class CharacterPresenceFormatter:
    """Compile canonical NPC presence information for orchestration layers."""

    @staticmethod
    def format(
        scene_summary: Optional[Dict[str, Any]],
        scene_info: Optional[SceneInfo],
        hostile_indicators: Iterable[Any],
    ) -> ScenePresenceView:
        """Build a deterministic presence view from scene data."""
        participant_hostility, participant_display = CharacterPresenceFormatter._collect_participant_context(
            scene_summary, scene_info
        )

        display_map: Dict[str, str] = {}
        if scene_summary:
            display_map.update(scene_summary.get("npc_display_names", {}) or {})
        if scene_info and getattr(scene_info, "metadata", None):
            display_map.update(scene_info.metadata.get("npc_display_names", {}) or {})

        hostile_lookup = CharacterPresenceFormatter._build_hostile_lookup(
            hostile_indicators, participant_hostility.keys()
        )

        npc_ids = CharacterPresenceFormatter._collect_npc_ids(scene_summary, scene_info)

        npc_entries: List[Dict[str, Any]] = []
        active_entries: List[Dict[str, str]] = []
        seen: set[str] = set()

        for identifier in npc_ids:
            if not identifier:
                continue
            npc_id = str(identifier)
            if npc_id in seen:
                continue
            seen.add(npc_id)

            display_name = CharacterPresenceFormatter.friendly_name(
                npc_id,
                {
                    **display_map,
                    **participant_display,
                },
            )

            lower_display = display_name.lower()
            is_hostile = (
                participant_hostility.get(npc_id, False)
                or participant_hostility.get(lower_display, False)
                or npc_id in hostile_lookup
                or lower_display in hostile_lookup
            )

            display_map.setdefault(npc_id, display_name)

            npc_entries.append(
                {
                    "character_id": npc_id,
                    "name": display_name,
                    "type": "enemy" if is_hostile else "npc",
                    "hostile": is_hostile,
                }
            )
            active_entries.append({"character_id": npc_id, "name": display_name})

        return ScenePresenceView(
            npc_entries=npc_entries,
            npc_display_names=display_map,
            active_character_entries=active_entries,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def friendly_name(
        identifier: Any,
        lookup: Optional[Dict[str, str]] = None,
    ) -> str:
        """Convert npc identifiers into human-readable names."""
        if identifier is None:
            return "Unknown NPC"
        identifier_str = str(identifier)
        if lookup:
            display = lookup.get(identifier_str)
            if display:
                return display
        lowered = identifier_str.lower()
        if lowered.startswith(("npc:", "npc_profile:", "pc:")):
            identifier_str = identifier_str.split(":", 1)[1]
        cleaned = identifier_str.replace("_", " ").strip()
        return cleaned.title() if cleaned else "Unknown NPC"

    @staticmethod
    def _collect_participant_context(
        scene_summary: Optional[Dict[str, Any]],
        scene_info: Optional[SceneInfo],
    ) -> Tuple[Dict[str, bool], Dict[str, str]]:
        participant_hostility: Dict[str, bool] = {}
        participant_display: Dict[str, str] = {}

        participants: Sequence[Any] = ()
        if scene_info and getattr(scene_info, "participants", None):
            participants = scene_info.participants
        elif scene_summary:
            participants = scene_summary.get("participants", []) or []

        for participant in participants:
            char_id, display_name, role = CharacterPresenceFormatter._parse_participant(participant)
            if not display_name and char_id:
                display_name = CharacterPresenceFormatter.friendly_name(char_id)
            if char_id:
                participant_display[char_id] = display_name
            if display_name:
                participant_display.setdefault(display_name.lower(), display_name)

            is_hostile = CharacterPresenceFormatter._role_implies_hostility(role)
            if char_id:
                participant_hostility[char_id] = is_hostile
            if display_name:
                participant_hostility.setdefault(display_name.lower(), is_hostile)

        return participant_hostility, participant_display

    @staticmethod
    def _parse_participant(participant: Any) -> Tuple[Optional[str], str, Optional[CharacterRole]]:
        """Normalize participant data from SceneInfo or dicts."""
        if isinstance(participant, SceneParticipant):
            return participant.character_id, participant.display_name or "", participant.role

        if isinstance(participant, dict):
            char_id = participant.get("character_id")
            display_name = participant.get("display_name") or participant.get("name") or ""
            role_value = participant.get("role")
            role = CharacterPresenceFormatter._coerce_role(role_value)
            return char_id, display_name, role

        return None, "", None

    @staticmethod
    def _coerce_role(value: Any) -> Optional[CharacterRole]:
        if isinstance(value, CharacterRole):
            return value
        if isinstance(value, str):
            try:
                return CharacterRole(value)
            except ValueError:
                try:
                    return CharacterRole[value.upper()]
                except KeyError:
                    return None
        return None

    @staticmethod
    def _role_implies_hostility(role: Optional[CharacterRole]) -> bool:
        if not role:
            return False
        return role == CharacterRole.NPC_COMBATANT

    @staticmethod
    def _collect_npc_ids(
        scene_summary: Optional[Dict[str, Any]],
        scene_info: Optional[SceneInfo],
    ) -> List[Any]:
        if scene_summary:
            npcs = scene_summary.get("npcs_present")
            if isinstance(npcs, list):
                return npcs
        if scene_info:
            return list(scene_info.npcs_present or [])
        return []

    @staticmethod
    def _build_hostile_lookup(
        indicators: Iterable[Any],
        participant_keys: Iterable[str],
    ) -> set[str]:
        hostile_lookup: set[str] = set()
        for value in indicators or []:
            if not value:
                continue
            hostile_lookup.add(str(value))
            if isinstance(value, str):
                hostile_lookup.add(value.lower())
        # Include participant keys lower-cased for quick comparisons
        for key in participant_keys:
            if isinstance(key, str):
                hostile_lookup.add(key)
                hostile_lookup.add(key.lower())
        return hostile_lookup
