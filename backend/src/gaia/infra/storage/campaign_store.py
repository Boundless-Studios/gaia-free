"""
Unified campaign storage interface with local and GCS backends.

This module provides a simple abstraction for reading/writing JSON payloads
under a session-aware directory layout. It supports three effective modes:

- Local only (works in dev/CI without cloud credentials)
- GCS only (stateless environments mounting nothing writable)
- Hybrid (local write-through + GCS mirror and read fallback)

The public factory `get_campaign_store(session_storage)` returns a hybrid
store that prefers local where available and mirrors to GCS when configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
import json
import os
import shutil
import logging

from gaia_private.session.session_storage import SessionStorage
from gaia.infra.storage.campaign_object_store import get_campaign_object_store

logger = logging.getLogger(__name__)


class CampaignStore:
    """Abstract storage API for campaign/session artifacts."""

    def read_json(self, *relative_parts: str) -> Optional[Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def write_json(self, payload: Any, *relative_parts: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def list_json_prefix(self, *relative_parts: str) -> list[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def upload_file(self, local_path: str, *relative_parts: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def download_file(self, local_path: str, *relative_parts: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def delete(self, *relative_parts: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def enabled(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class LocalCampaignStore(CampaignStore):
    """Filesystem-backed store using SessionStorage path resolution."""

    storage: SessionStorage

    @property
    def enabled(self) -> bool:
        return True

    # ---------------- internal helpers ---------------- #
    def _resolve(self, *parts: str, for_write: bool = False) -> Optional[Path]:
        if not parts:
            return None
        # Special-case metadata path: ("metadata", "campaign_1.json")
        if parts[0] == "metadata" and len(parts) >= 2:
            base = os.path.basename(parts[1])
            session_id = os.path.splitext(base)[0]
            return self.storage.metadata_path(session_id)

        # Session-scoped path: ("campaign_1", "logs/chat_history.json")
        session_id = parts[0]
        rel = "/".join(parts[1:]) if len(parts) > 1 else ""
        session_dir = self.storage.resolve_session_dir(session_id, create=for_write)
        if not session_dir:
            return None
        if not rel:
            return session_dir
        dst = session_dir / rel
        if for_write:
            dst.parent.mkdir(parents=True, exist_ok=True)
        return dst

    # ---------------- API ---------------- #
    def read_json(self, *relative_parts: str) -> Optional[Any]:
        path = self._resolve(*relative_parts, for_write=False)
        if not path or not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LocalCampaignStore read_json failed for %s: %s", path, exc)
            return None

    def write_json(self, payload: Any, *relative_parts: str) -> bool:
        path = self._resolve(*relative_parts, for_write=True)
        if not path:
            return False
        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LocalCampaignStore write_json failed for %s: %s", path, exc)
            return False

    def list_json_prefix(self, *relative_parts: str) -> list[str]:
        if relative_parts and relative_parts[0] == "metadata":
            names: list[str] = []
            try:
                for session_id, _, _ in self.storage.iter_session_dirs():
                    meta_path = self.storage.metadata_path(session_id)
                    if meta_path and meta_path.exists():
                        names.append(f"{session_id}.json")
            except Exception as exc:  # noqa: BLE001
                logger.warning("LocalCampaignStore list_json_prefix metadata failed: %s", exc)
            return names

        path = self._resolve(*relative_parts, for_write=False)
        if not path or not path.exists() or not path.is_dir():
            return []
        try:
            return [p.name for p in path.glob("*.json") if p.is_file()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("LocalCampaignStore list_json_prefix failed for %s: %s", path, exc)
            return []

    def upload_file(self, local_path: str, *relative_parts: str) -> bool:
        dest = self._resolve(*relative_parts, for_write=True)
        if not dest:
            return False
        try:
            src = Path(local_path).resolve()
            dest_path = dest.resolve()
            if src == dest_path:
                return True
            shutil.copy2(local_path, dest)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LocalCampaignStore upload_file failed for %s -> %s: %s", local_path, dest, exc)
            return False

    def download_file(self, local_path: str, *relative_parts: str) -> bool:
        src = self._resolve(*relative_parts, for_write=False)
        if not src or not src.exists():
            return False
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            shutil.copy2(src, local_path)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LocalCampaignStore download_file failed for %s -> %s: %s", src, local_path, exc)
            return False

    def delete(self, *relative_parts: str) -> bool:
        path = self._resolve(*relative_parts, for_write=False)
        if not path or not path.exists():
            return True
        try:
            path.unlink()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LocalCampaignStore delete failed for %s: %s", path, exc)
            return False


class GCSCampaignStore(CampaignStore):
    """Thin wrapper around CampaignObjectStore to conform to CampaignStore API."""

    def __init__(self) -> None:
        self._obj = get_campaign_object_store()

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._obj, "enabled", False))

    def read_json(self, *relative_parts: str) -> Optional[Any]:
        if not self.enabled:
            return None
        return self._obj.read_json(*relative_parts)

    def write_json(self, payload: Any, *relative_parts: str) -> bool:
        if not self.enabled:
            return False
        return self._obj.write_json(payload, *relative_parts)

    def list_json_prefix(self, *relative_parts: str) -> list[str]:
        if not self.enabled:
            return []
        return self._obj.list_json_prefix(*relative_parts)

    def upload_file(self, local_path: str, *relative_parts: str) -> bool:
        if not self.enabled:
            return False
        return self._obj.upload_file(local_path, *relative_parts)

    def download_file(self, local_path: str, *relative_parts: str) -> bool:
        if not self.enabled:
            return False
        return self._obj.download_file(local_path, *relative_parts)

    def delete(self, *relative_parts: str) -> bool:
        # CampaignObjectStore does not currently support delete; treat as success.
        return True


class HybridCampaignStore(CampaignStore):
    """Combines local filesystem and GCS with sensible defaults.

    - Reads prefer local; fall back to GCS if local is missing.
    - Writes go to local; mirror to GCS when enabled.
    - Listings prefer local; fall back to GCS if local path missing.
    """

    def __init__(self, local: LocalCampaignStore, gcs: GCSCampaignStore) -> None:
        self._local = local
        self._gcs = gcs

    @property
    def enabled(self) -> bool:
        # Always enabled (at least local)
        return True

    def read_json(self, *relative_parts: str) -> Optional[Any]:
        payload = self._local.read_json(*relative_parts)
        if payload is not None:
            return payload
        if self._gcs.enabled:
            return self._gcs.read_json(*relative_parts)
        return None

    def write_json(self, payload: Any, *relative_parts: str) -> bool:
        ok = self._local.write_json(payload, *relative_parts)
        if self._gcs.enabled:
            # Best effort mirror
            try:
                self._gcs.write_json(payload, *relative_parts)
            except Exception as exc:  # noqa: BLE001
                logger.warning("HybridCampaignStore: GCS mirror write failed for %s: %s", "/".join(relative_parts), exc)
        return ok

    def list_json_prefix(self, *relative_parts: str) -> list[str]:
        names: set[str] = set(self._local.list_json_prefix(*relative_parts))
        if self._gcs.enabled:
            try:
                names.update(self._gcs.list_json_prefix(*relative_parts))
            except Exception:  # noqa: BLE001
                logger.debug("HybridCampaignStore: GCS list failure for %s", "/".join(relative_parts))
        return sorted(names)

    def upload_file(self, local_path: str, *relative_parts: str) -> bool:
        ok = self._local.upload_file(local_path, *relative_parts)
        if self._gcs.enabled:
            try:
                self._gcs.upload_file(local_path, *relative_parts)
            except Exception as exc:  # noqa: BLE001
                logger.warning("HybridCampaignStore: GCS mirror upload failed for %s: %s", "/".join(relative_parts), exc)
        return ok

    def download_file(self, local_path: str, *relative_parts: str) -> bool:
        # Prefer local copy if present; otherwise attempt GCS then leave a local copy.
        if self._local.download_file(local_path, *relative_parts):
            return True
        if self._gcs.enabled:
            return self._gcs.download_file(local_path, *relative_parts)
        return False

    def delete(self, *relative_parts: str) -> bool:
        ok = self._local.delete(*relative_parts)
        if self._gcs.enabled:
            try:
                self._gcs.delete(*relative_parts)
            except Exception:  # noqa: BLE001
                logger.debug("HybridCampaignStore: GCS delete ignored for %s", "/".join(relative_parts))
        return ok


def get_campaign_store(session_storage: SessionStorage) -> CampaignStore:
    """Return a hybrid store using the provided SessionStorage for local paths."""
    return HybridCampaignStore(LocalCampaignStore(session_storage), GCSCampaignStore())
