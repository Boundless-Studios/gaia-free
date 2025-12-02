"""Storage helper for client-delivered audio artifacts."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from gaia.infra.audio.voice_and_tts_config import (
    AUDIO_TEMP_DIR,
    get_client_audio_config,
)
from gaia.utils.google_auth_helpers import get_default_credentials

logger = logging.getLogger(__name__)

try:
    from google.cloud import storage  # type: ignore
    from google.auth.exceptions import DefaultCredentialsError  # type: ignore
    _GCS_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    storage = None
    DefaultCredentialsError = Exception  # type: ignore
    _GCS_AVAILABLE = False

try:
    from mutagen import File as MutagenFile  # type: ignore
except Exception:  # pragma: no cover - import guard
    MutagenFile = None


@dataclass
class AudioArtifact:
    """Lightweight container describing an audio artifact."""

    id: str
    session_id: str
    url: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    duration_sec: Optional[float]
    storage_path: str
    bucket: Optional[str]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "success": True,
            "id": self.id,
            "session_id": self.session_id,
            "url": self.url,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration_sec": self.duration_sec,
            "storage_path": self.storage_path,
            "bucket": self.bucket,
        }


class AudioArtifactStore:
    """Persist synthesized audio so browsers can play it."""

    def __init__(self) -> None:
        config = get_client_audio_config()
        self.enabled: bool = bool(config.get("enabled"))
        self.bucket_name: str = config.get("bucket", "")
        self.base_path: str = config.get("base_path", "media/audio").strip("/")
        fallback_root = Path(AUDIO_TEMP_DIR) / "client_audio"
        configured_root_value = config.get("local_root") or fallback_root
        configured_root = Path(configured_root_value).expanduser()
        self.local_root = self._prepare_local_root(configured_root, fallback_root)
        self.url_ttl_seconds: int = int(config.get("url_ttl_seconds", 900))

        self._client = None
        self._bucket = None

        if self.bucket_name and _GCS_AVAILABLE:
            try:
                # Check for credentials first before initializing client (avoids 30s timeout)
                try:
                    credentials, project = get_default_credentials(timeout_seconds=1.0)
                except DefaultCredentialsError:
                    raise
                except Exception as exc:
                    raise DefaultCredentialsError(f"Failed to obtain credentials: {exc}") from exc

                self._client = storage.Client(credentials=credentials, project=project)
                self._bucket = self._client.bucket(self.bucket_name)
                logger.info("Client audio artifacts will upload to bucket '%s'", self.bucket_name)
            except DefaultCredentialsError as exc:  # pragma: no cover - runtime only
                logger.warning("Client audio bucket configured but credentials unavailable: %s", exc)
                self._client = None
                self._bucket = None
            except Exception as exc:  # pragma: no cover - runtime only
                logger.error("Failed to initialize GCS client: %s", exc)
                self._client = None
                self._bucket = None
        elif self.bucket_name and not _GCS_AVAILABLE:
            logger.warning(
                "google-cloud-storage not installed; falling back to local audio storage"
            )

    @property
    def uses_gcs(self) -> bool:
        return self._bucket is not None

    def _blob_path(self, session_id: str, filename: str) -> str:
        base = self.base_path
        return f"{session_id}/{base}/{filename}" if base else f"{session_id}/{filename}"

    def _calculate_duration(self, file_path: Path) -> Optional[float]:
        if not MutagenFile:  # pragma: no cover - optional dependency guard
            return None
        try:
            audio = MutagenFile(str(file_path))
            if audio and getattr(audio, "info", None):
                return float(getattr(audio.info, "length", 0.0)) or None
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("Failed to read audio duration: %s", exc)
        return None

    def _prepare_local_root(self, configured_root: Path, fallback_root: Path) -> Path:
        """Ensure the local root exists and is writable; fall back if needed."""
        for candidate in (configured_root, fallback_root):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                if os.access(candidate, os.W_OK | os.X_OK):
                    if candidate != configured_root:
                        logger.warning(
                            "Client audio path %s not writable; using fallback %s",
                            configured_root,
                            candidate,
                        )
                    return candidate.resolve()
            except PermissionError as exc:  # pragma: no cover - environment specific
                logger.warning(
                    "Unable to initialize client audio path %s: %s", candidate, exc
                )

        raise RuntimeError(
            f"Client audio storage path '{configured_root}' is not writable and "
            f"fallback '{fallback_root}' could not be used"
        )

    def persist_audio(
        self,
        *,
        session_id: str,
        audio_bytes: bytes,
        mime_type: str = "audio/mpeg",
        skip_gcs_upload: bool = False,
    ) -> AudioArtifact:
        if not self.enabled:
            raise RuntimeError("Client audio disabled; cannot persist artifact")

        artifact_id = uuid.uuid4().hex
        extension = "mp3" if mime_type == "audio/mpeg" else mime_type.split("/")[-1]
        extension = extension.lstrip(".") or "bin"
        filename = f"{artifact_id}.{extension}"
        session_dir = self.local_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        file_path = session_dir / filename
        file_path.write_bytes(audio_bytes)
        size_bytes = file_path.stat().st_size
        duration_sec = self._calculate_duration(file_path)
        created_at = datetime.utcnow()

        storage_path = self._blob_path(session_id, filename)
        # Always expose backend proxy URL so clients fetch via API
        # The backend handler will resolve to local or GCS as needed.
        url = f"/api/media/audio/{session_id}/{filename}"
        bucket = None

        # Skip GCS upload for progressive chunks - they use local URLs for speed
        # Full artifacts can still upload to GCS if needed
        if self.uses_gcs and not skip_gcs_upload:
            try:
                blob = self._bucket.blob(storage_path)  # type: ignore[union-attr]
                blob.upload_from_filename(str(file_path), content_type=mime_type)
                bucket = self.bucket_name
                # Remove local file after successful upload; backend will stream from GCS
                file_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.error("Failed to upload audio artifact to GCS: %s", exc)

        logger.debug(
            "[AUDIO][persist] artifact_id=%s session=%s bytes=%d gcs_uploaded=%s url=%s",
            artifact_id,
            session_id,
            size_bytes,
            self.uses_gcs and not skip_gcs_upload,
            url,
        )

        return AudioArtifact(
            id=artifact_id,
            session_id=session_id,
            url=url,
            mime_type=mime_type,
            size_bytes=size_bytes,
            created_at=created_at,
            duration_sec=duration_sec,
            storage_path=storage_path,
            bucket=bucket,
        )

    def resolve_local_path(self, session_id: str, filename: str) -> Path:
        return (self.local_root / session_id / filename).resolve()

    def read_artifact_bytes(self, session_id: str, filename: str) -> bytes:
        storage_path = self._blob_path(session_id, filename)

        if self.uses_gcs:
            blob = self._bucket.blob(storage_path)  # type: ignore[union-attr]
            if not blob.exists():
                raise FileNotFoundError(storage_path)
            return blob.download_as_bytes()

        local_path = self.resolve_local_path(session_id, filename)
        if not local_path.exists():
            raise FileNotFoundError(str(local_path))
        return local_path.read_bytes()

    def list_gcs_artifacts(self, prefix: Optional[str] = None):
        if not self.uses_gcs:
            return []
        actual_prefix = prefix or ""
        return self._bucket.list_blobs(prefix=actual_prefix)


audio_artifact_store = AudioArtifactStore()

__all__ = [
    "AudioArtifact",
    "AudioArtifactStore",
    "audio_artifact_store",
]
