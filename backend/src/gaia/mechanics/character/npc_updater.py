"""NPC updater for managing lightweight NPC profiles."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from gaia.mechanics.character.id_utils import slugify
from gaia.models.character.enums import CharacterCapability, CharacterRole
from gaia.models.character.npc_profile import NpcProfile
from gaia.mechanics.character.npc_profile_storage import NpcProfileStorage

logger = logging.getLogger(__name__)


class NpcUpdater:
    """Maintain NPC narrative profiles prior to full character promotion."""

    def __init__(self, profile_store: Optional[object] = None) -> None:
        self.profile_store = profile_store or NpcProfileStorage()

    # ------------------------------------------------------------------
    # Profile lifecycle helpers
    # ------------------------------------------------------------------
    def set_profile_store(self, profile_store: object) -> None:
        self.profile_store = profile_store

    def ensure_profile(self, name: str, role: CharacterRole = CharacterRole.NPC_SUPPORT) -> NpcProfile:
        profile = self._load_profile_by_name(name)
        if profile:
            return profile
        npc_id = self._generate_profile_id(name)
        profile = NpcProfile(
            npc_id=npc_id,
            display_name=name,
            role=role,
        )
        self._persist_profile(profile)
        return profile

    def update_from_structured(self, name: str, structured_data: Dict[str, Any]) -> NpcProfile:
        profile = self.ensure_profile(name)
        profile.description = structured_data.get("description", profile.description)
        tags = structured_data.get("tags")
        if isinstance(tags, list):
            profile.tags = [str(tag) for tag in tags]
        relationships = structured_data.get("relationships")
        if isinstance(relationships, dict):
            profile.relationships.update({str(k): str(v) for k, v in relationships.items()})
        notes = structured_data.get("notes")
        if isinstance(notes, list):
            profile.notes.extend([str(note) for note in notes if str(note) not in profile.notes])
        profile.mark_updated()
        self._persist_profile(profile)
        return profile

    def promote_to_character(self, profile: NpcProfile) -> None:
        profile.has_full_sheet = True
        profile.capabilities |= CharacterCapability.COMBAT | CharacterCapability.INVENTORY
        profile.mark_updated()
        self._persist_profile(profile)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_profile_by_name(self, name: str) -> Optional[NpcProfile]:
        if not self.profile_store:
            return None
        profile_data = self.profile_store.get_profile_by_name(name)  # type: ignore[attr-defined]
        if not profile_data:
            return None
        if isinstance(profile_data, NpcProfile):
            return profile_data
        if isinstance(profile_data, dict):
            return NpcProfile.from_dict(profile_data)
        return None

    def _persist_profile(self, profile: NpcProfile) -> None:
        if not self.profile_store:
            return
        if hasattr(self.profile_store, "save_profile"):
            self.profile_store.save_profile(profile)  # type: ignore[attr-defined]
        elif hasattr(self.profile_store, "save_profile_dict"):
            self.profile_store.save_profile_dict(profile.to_dict())  # type: ignore[attr-defined]
        else:
            logger.debug("Profile store lacks save_profile interface; profile not persisted")

    def _generate_profile_id(self, name: str) -> str:
        slug = slugify(name) or "npc_profile"
        return f"npc_profile:{slug}"
