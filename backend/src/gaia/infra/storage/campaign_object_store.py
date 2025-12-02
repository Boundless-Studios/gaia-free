"""
Campaign object storage abstraction for Cloud Run.

Provides a thin wrapper over Google Cloud Storage to persist campaign data
and metadata when running in stateless environments. Falls back to disabled
mode when not configured.
"""
from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

try:  # Optional import; guarded for local development
    from google.cloud import storage  # type: ignore
    _GCS_AVAILABLE = True
except Exception:  # pragma: no cover - environment specific
    storage = None  # type: ignore
    _GCS_AVAILABLE = False


def _env_name() -> str:
    return os.getenv("ENVIRONMENT_NAME") or os.getenv("ENV") or "default"


def _should_enable_gcs() -> bool:
    backend = (os.getenv("CAMPAIGN_STORAGE_BACKEND") or "auto").strip().lower()
    bucket = os.getenv("CAMPAIGN_STORAGE_BUCKET", "").strip()
    if not bucket:
        return False
    if backend == "gcs":
        return True
    if backend == "auto":
        # Prefer GCS automatically on Cloud Run
        return os.getenv("K_SERVICE") is not None
    return False


@dataclass
class _GCSConfig:
    bucket_name: str
    prefix: str  # e.g. "campaigns/stg/"


class CampaignObjectStore:
    """GCS-backed object store for campaign data and metadata."""

    def __init__(self) -> None:
        self.enabled = False
        self._client: Optional[storage.Client] = None  # type: ignore[name-defined]
        self._bucket = None
        self._cfg: Optional[_GCSConfig] = None

        logger.debug("🔍 DEBUG: CampaignObjectStore.__init__ - Initializing...")
        logger.debug("🔍 DEBUG: _GCS_AVAILABLE=%s", _GCS_AVAILABLE)
        logger.debug("🔍 DEBUG: _should_enable_gcs()=%s", _should_enable_gcs())

        if not _should_enable_gcs() or not _GCS_AVAILABLE:
            if os.getenv("CAMPAIGN_STORAGE_BUCKET") and not _GCS_AVAILABLE:
                logger.debug("CampaignObjectStore: google-cloud-storage not installed; disabled")
            else:
                logger.debug("🔍 DEBUG: GCS not enabled - should_enable=%s, available=%s",
                           _should_enable_gcs(), _GCS_AVAILABLE)
            return

        bucket_name = os.getenv("CAMPAIGN_STORAGE_BUCKET", "").strip()
        prefix = f"campaigns/{_env_name()}/"
        logger.debug("🔍 DEBUG: Attempting to connect to GCS bucket=%s prefix=%s", bucket_name, prefix)
        try:
            self._client = storage.Client()  # type: ignore[name-defined]
            self._bucket = self._client.bucket(bucket_name)
            self._cfg = _GCSConfig(bucket_name=bucket_name, prefix=prefix)
            self.enabled = True
            logger.info("CampaignObjectStore enabled (bucket=%s prefix=%s)", bucket_name, prefix)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to initialize GCS client for campaign storage: %s", exc)
            logger.error("🔍 DEBUG: GCS initialization error details: %s", exc, exc_info=True)
            self.enabled = False
            self._client = None
            self._bucket = None
            self._cfg = None

    # -------------------------- path helpers -------------------------- #
    def _key(self, *parts: str) -> str:
        assert self._cfg is not None
        suffix = "/".join(p.strip("/") for p in parts if p)
        return f"{self._cfg.prefix}{suffix}" if suffix else self._cfg.prefix

    # ------------------------ listing & discovery --------------------- #
    def list_metadata(self) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """Yield (session_id, metadata_dict) from metadata/*.json objects.

        This is the canonical, efficient way to list campaigns in GCS.
        """
        if not self.enabled or not self._bucket:
            return
        prefix = self._key("metadata/")
        try:
            for blob in self._bucket.list_blobs(prefix=prefix):
                name = blob.name
                if not name.endswith(".json"):
                    continue
                session_id = os.path.splitext(os.path.basename(name))[0]
                try:
                    raw = blob.download_as_text(encoding="utf-8")
                    payload = json.loads(raw)
                except Exception:  # noqa: BLE001
                    payload = {}
                yield session_id, payload if isinstance(payload, dict) else {}
        except Exception as exc:  # noqa: BLE001
            logger.error("GCS list_metadata failed: %s", exc)

    # ------------------------ json read / write ----------------------- #
    def read_json(self, *relative_parts: str) -> Optional[Any]:
        if not self.enabled or not self._bucket:
            logger.debug("🔍 DEBUG: read_json skipped - enabled=%s, has_bucket=%s",
                       self.enabled, self._bucket is not None)
            return None
        key = self._key(*relative_parts)
        logger.debug("🔍 DEBUG: Reading from GCS key: %s", key)
        try:
            blob = self._bucket.get_blob(key)
            if not blob:
                logger.debug("🔍 DEBUG: Blob not found in GCS: %s", key)
                return None
            data = json.loads(blob.download_as_text(encoding="utf-8"))
            logger.debug("🔍 DEBUG: Successfully read from GCS: %s", key)
            return data
        except Exception as exc:  # noqa: BLE001
            logger.warning("GCS read_json failed for %s: %s", key, exc)
            logger.warning("🔍 DEBUG: GCS read error details: %s", exc, exc_info=True)
            return None

    def write_json(self, payload: Any, *relative_parts: str) -> bool:
        if not self.enabled or not self._bucket:
            return False
        key = self._key(*relative_parts)
        try:
            blob = self._bucket.blob(key)
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=False, indent=2),
                content_type="application/json",
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("GCS write_json failed for %s: %s", key, exc)
            return False

    # ------------------------ file helpers ---------------------------- #
    def upload_file(self, local_path: str, *relative_parts: str) -> bool:
        if not self.enabled or not self._bucket:
            return False
        key = self._key(*relative_parts)
        try:
            blob = self._bucket.blob(key)
            blob.upload_from_filename(local_path)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("GCS upload_file failed for %s: %s", key, exc)
            return False


    # ------------------------ listing by prefix ----------------------- #
    def list_json_prefix(self, *relative_parts: str) -> list[str]:
        """Return object names (basename) for JSON files under a prefix."""
        if not self.enabled or not self._bucket:
            return []
        prefix = self._key(*relative_parts)
        if not prefix.endswith("/"):
            prefix += "/"
        results: list[str] = []
        try:
            for blob in self._bucket.list_blobs(prefix=prefix):
                name = blob.name
                if not name.endswith(".json"):
                    continue
                base = os.path.basename(name)
                results.append(base)
        except Exception as exc:  # noqa: BLE001
            logger.error("GCS list_json_prefix failed for %s: %s", prefix, exc)
        return results

    def download_file(self, local_path: str, *relative_parts: str) -> bool:
        if not self.enabled or not self._bucket:
            return False
        key = self._key(*relative_parts)
        try:
            blob = self._bucket.get_blob(key)
            if not blob:
                return False
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            blob.download_to_filename(local_path)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("GCS download_file failed for %s: %s", key, exc)
            return False


_store_singleton: Optional[CampaignObjectStore] = None


def get_campaign_object_store() -> CampaignObjectStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = CampaignObjectStore()
    return _store_singleton


@dataclass
class PregeneratedFetchResult:
    payload: Optional[Any]
    source: str
    local_mtime: Optional[float]
    checked_remote: bool


@dataclass
class PregeneratedWriteResult:
    local_success: bool
    remote_success: Optional[bool]


class PregeneratedContentStore:
    """Helper for pregenerated campaign/character assets with unified fallback logic."""

    def __init__(self, obj_store: CampaignObjectStore) -> None:
        self._obj_store = obj_store
        base_path = os.getenv("CAMPAIGN_STORAGE_PATH")
        if base_path:
            self._local_root = Path(base_path).expanduser()
        else:
            self._local_root = Path(".")
        self._pregenerated_dir = self._local_root / "pregenerated"

    def local_path(self, filename: str) -> Path:
        return self._pregenerated_dir / filename

    @property
    def gcs_enabled(self) -> bool:
        return getattr(self._obj_store, "enabled", False)

    def local_mtime(self, filename: str) -> Optional[float]:
        path = self.local_path(filename)
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return None

    def _read_local_json(self, filename: str) -> Optional[Any]:
        path = self.local_path(filename)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PregeneratedContentStore: failed to read %s: %s", path, exc)
            return None

    def _write_local_json(self, payload: Any, filename: str) -> bool:
        path = self.local_path(filename)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("PregeneratedContentStore: failed to write %s: %s", path, exc)
            return False

    def fetch_json(
        self,
        filename: str,
        *,
        previous_local_mtime: Optional[float] = None,
        force_local: bool = False,
    ) -> PregeneratedFetchResult:
        logger.debug("🔍 DEBUG: PregeneratedContentStore.fetch_json(%s, force_local=%s)", filename, force_local)

        local_mtime = self.local_mtime(filename)
        remote_enabled = getattr(self._obj_store, "enabled", False)

        logger.debug("🔍 DEBUG: remote_enabled=%s, force_local=%s, local_mtime=%s",
                   remote_enabled, force_local, local_mtime)

        # Check GCS first (unless force_local is True)
        if remote_enabled and not force_local:
            logger.debug("🔍 DEBUG: Checking GCS for %s...", filename)
            payload = self._obj_store.read_json("pregenerated", filename)
            if payload is not None:
                logger.debug("🔍 DEBUG: ✅ Found %s in GCS", filename)
                return PregeneratedFetchResult(
                    payload=payload,
                    source="gcs",
                    local_mtime=local_mtime,
                    checked_remote=True,
                )
            else:
                logger.debug("🔍 DEBUG: ❌ Not found in GCS, will check local", filename)
        elif force_local:
            logger.debug("🔍 DEBUG: Skipping GCS check (force_local=True)")
        else:
            logger.debug("🔍 DEBUG: Skipping GCS check (remote not enabled)")

        if not force_local and previous_local_mtime is not None and local_mtime == previous_local_mtime:
            logger.debug("🔍 DEBUG: Local file unchanged (mtime=%s)", local_mtime)
            return PregeneratedFetchResult(
                payload=None,
                source="unchanged",
                local_mtime=local_mtime,
                checked_remote=remote_enabled,
            )

        logger.debug("🔍 DEBUG: Checking local filesystem for %s...", filename)
        payload = self._read_local_json(filename)
        if payload is not None:
            logger.debug("🔍 DEBUG: ✅ Found %s locally", filename)
            return PregeneratedFetchResult(
                payload=payload,
                source="local",
                local_mtime=local_mtime,
                checked_remote=remote_enabled and not force_local,
            )

        logger.debug("🔍 DEBUG: ❌ Not found locally at %s", self.local_path(filename))
        return PregeneratedFetchResult(
            payload=None,
            source="missing",
            local_mtime=local_mtime,
            checked_remote=remote_enabled and not force_local,
        )

    def read_json(self, filename: str) -> Tuple[Optional[Any], Optional[str]]:
        result = self.fetch_json(filename, force_local=True)
        if result.source in {"gcs", "local"}:
            return result.payload, result.source
        return None, None

    def write_json(self, payload: Any, filename: str) -> PregeneratedWriteResult:
        wrote_local = self._write_local_json(payload, filename)
        remote_result: Optional[bool] = None
        if getattr(self._obj_store, "enabled", False):
            try:
                remote_result = self._obj_store.write_json(payload, "pregenerated", filename)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "PregeneratedContentStore: failed to mirror %s to GCS: %s",
                    filename,
                    exc,
                )
                remote_result = False
        return PregeneratedWriteResult(local_success=wrote_local, remote_success=remote_result)


_pregenerated_store_singleton: Optional[PregeneratedContentStore] = None


def get_pregenerated_content_store() -> PregeneratedContentStore:
    global _pregenerated_store_singleton
    if _pregenerated_store_singleton is None:
        _pregenerated_store_singleton = PregeneratedContentStore(get_campaign_object_store())
    return _pregenerated_store_singleton
