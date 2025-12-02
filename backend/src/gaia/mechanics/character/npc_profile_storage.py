"""Persistence for lightweight NPC profiles."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from gaia.models.character.npc_profile import NpcProfile
from gaia.utils.singleton import SingletonMeta
from gaia_private.session.session_storage import SessionStorage
from gaia.infra.storage.campaign_store import get_campaign_store

logger = logging.getLogger(__name__)


class NpcProfileStorage(metaclass=SingletonMeta):
    """Stores NPC profiles separately from full character sheets with hybrid local+GCS storage."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        if hasattr(self, "_initialized"):
            return

        if base_path is None:
            from os import getenv

            root = getenv("CAMPAIGN_STORAGE_PATH")
            if not root:
                raise ValueError(
                    "CAMPAIGN_STORAGE_PATH is not set; cannot initialize npc profile storage"
                )
            base_path = Path(root)

        self.base_path = Path(base_path)
        self.profiles_path = self.base_path / "npc_profiles"
        self.profiles_path.mkdir(parents=True, exist_ok=True)

        # Initialize unified hybrid storage (local + GCS)
        self._storage = SessionStorage(str(self.base_path), ensure_legacy_dirs=True)
        self._store = get_campaign_store(self._storage)

        self._initialized = True

    def save_profile(self, profile: NpcProfile) -> str:
        profile_data = profile.to_dict()

        # Save to local filesystem
        file_path = self.profiles_path / f"{profile.npc_id}.json"
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(profile_data, handle, indent=2, ensure_ascii=False)
        logger.debug("Saved NPC profile %s", profile.npc_id)

        # Mirror to GCS when enabled
        if self._store:
            try:
                self._store.write_json(profile_data, "shared", f"npc_profiles/{profile.npc_id}.json")
            except Exception as exc:  # noqa: BLE001
                logger.debug("NPC profile store mirror failed for %s: %s", profile.npc_id, exc)

        return profile.npc_id

    def get_profile_by_name(self, name: str) -> Optional[NpcProfile]:
        # Search local profiles first
        for file_path in self.profiles_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if str(data.get("display_name", "")).lower() == name.lower():
                    return NpcProfile.from_dict(data)
            except Exception:
                logger.warning("Failed to read NPC profile %s", file_path, exc_info=True)
                continue

        # Fallback to GCS if not found locally
        if self._store:
            try:
                for json_name in self._store.list_json_prefix("shared", "npc_profiles"):
                    data = self._store.read_json("shared", f"npc_profiles/{json_name}")
                    if data and str(data.get("display_name", "")).lower() == name.lower():
                        logger.debug("Loaded NPC profile %s from store", name)
                        return NpcProfile.from_dict(data)
            except Exception as exc:  # noqa: BLE001
                logger.debug("NPC profile store search failed: %s", exc)

        return None

    def save_profile_dict(self, profile_dict: dict) -> str:
        profile = NpcProfile.from_dict(profile_dict)
        return self.save_profile(profile)

    def load_profile(self, npc_id: str) -> Optional[NpcProfile]:
        """Load an NPC profile by ID.

        Args:
            npc_id: NPC identifier

        Returns:
            NpcProfile or None if not found
        """
        # Try local file first
        file_path = self.profiles_path / f"{npc_id}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                return NpcProfile.from_dict(data)
            except Exception as exc:
                logger.warning("Failed to read NPC profile %s: %s", file_path, exc)

        # Fallback to GCS
        if self._store:
            try:
                data = self._store.read_json("shared", f"npc_profiles/{npc_id}.json")
                if data:
                    logger.debug("Loaded NPC profile %s from store", npc_id)
                    return NpcProfile.from_dict(data)
            except Exception as exc:  # noqa: BLE001
                logger.debug("NPC profile store read failed for %s: %s", npc_id, exc)

        return None

    def list_profiles(self) -> list[NpcProfile]:
        """List all NPC profiles.

        Returns:
            List of NpcProfile objects
        """
        profiles = []
        seen = set()

        # List local profiles
        for file_path in self.profiles_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                profile = NpcProfile.from_dict(data)
                seen.add(profile.npc_id)
                profiles.append(profile)
            except Exception as exc:
                logger.warning("Failed to read NPC profile %s: %s", file_path, exc)

        # Supplement with GCS profiles not found locally
        if self._store:
            try:
                for json_name in self._store.list_json_prefix("shared", "npc_profiles"):
                    npc_id = Path(json_name).stem
                    if npc_id in seen:
                        continue
                    data = self._store.read_json("shared", f"npc_profiles/{json_name}")
                    if data:
                        profile = NpcProfile.from_dict(data)
                        seen.add(profile.npc_id)
                        profiles.append(profile)
            except Exception as exc:  # noqa: BLE001
                logger.debug("NPC profile store listing failed: %s", exc)

        return profiles
