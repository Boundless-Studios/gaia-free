"""Storage helper for generated image artifacts (portraits, scenes, etc)."""

from __future__ import annotations

import logging
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class ImageStorageType(str, Enum):
    """Supported storage types for image artifacts.

    Each type corresponds to a subdirectory where images are stored.
    The value is the singular form used in code, and `directory` property
    returns the plural form used for filesystem paths.

    Note: This is distinct from ImageType (location_ambiance, background_detail,
    moment_focus) which identifies scene image subtypes within a visual narrator set.
    """
    PORTRAIT = "portrait"
    SCENE = "scene"
    SCENE_BACKGROUND = "scene_background"
    MOMENT = "moment"
    CHARACTER = "character"
    ITEM = "item"
    BEAST = "beast"

    @property
    def directory(self) -> str:
        """Return the directory name (plural form) for this storage type."""
        return f"{self.value}s"

    @classmethod
    def all_types(cls) -> List[str]:
        """Return all storage type values."""
        return [t.value for t in cls]

    @classmethod
    def all_directories(cls) -> List[str]:
        """Return all directory names (plural forms)."""
        return [t.directory for t in cls]

try:
    from google.cloud import storage  # type: ignore
    from google.auth.exceptions import DefaultCredentialsError  # type: ignore
    _GCS_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    storage = None
    DefaultCredentialsError = Exception  # type: ignore
    _GCS_AVAILABLE = False

from gaia.utils.google_auth_helpers import get_default_credentials


@dataclass
class ImageArtifact:
    """Lightweight container describing an image artifact."""

    id: str
    session_id: str
    url: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    storage_path: str
    bucket: Optional[str]
    image_type: str  # "portrait", "scene", etc.

    def to_payload(self) -> Dict[str, Any]:
        return {
            "success": True,
            "id": self.id,
            "session_id": self.session_id,
            "url": self.url,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "storage_path": self.storage_path,
            "bucket": self.bucket,
            "image_type": self.image_type,
        }


def get_client_image_config() -> Dict[str, Any]:
    """Get image storage configuration from environment."""
    # Use dedicated image bucket (falls back to audio bucket for backward compatibility)
    bucket = os.getenv("IMAGE_STORAGE_BUCKET") or os.getenv("CLIENT_AUDIO_BUCKET", "")
    local_root = os.getenv("IMAGE_STORAGE_PATH", "/tmp/gaia_images")

    return {
        "enabled": True,  # Always enabled
        "bucket": bucket,
        "base_path": "media/images",
        "local_root": local_root,
        "url_ttl_seconds": 900,  # 15 minutes for signed URLs
    }


class ImageArtifactStore:
    """Persist generated images so they survive container restarts."""

    def __init__(self) -> None:
        config = get_client_image_config()
        self.enabled: bool = bool(config.get("enabled"))
        self.bucket_name: str = config.get("bucket", "")
        self.base_path: str = config.get("base_path", "media/images").strip("/")
        self.local_root = Path(config.get("local_root"))
        self.local_root.mkdir(parents=True, exist_ok=True)
        self.url_ttl_seconds: int = int(config.get("url_ttl_seconds", 900))

        self._client = None
        self._bucket = None

        if self.bucket_name and _GCS_AVAILABLE:
            try:
                # Check for credentials first before initializing client (avoids 30s timeout)
                try:
                    credentials, project = get_default_credentials(timeout_seconds=5.0)
                except DefaultCredentialsError:
                    raise
                except Exception as exc:
                    raise DefaultCredentialsError(f"Failed to obtain credentials: {exc}") from exc

                self._client = storage.Client(credentials=credentials, project=project)
                self._bucket = self._client.bucket(self.bucket_name)
                logger.info("Client image artifacts will upload to bucket '%s'", self.bucket_name)
            except DefaultCredentialsError as exc:  # pragma: no cover - runtime only
                logger.warning("Client image bucket configured but credentials unavailable: %s", exc)
                self._client = None
                self._bucket = None
            except Exception as exc:  # pragma: no cover - runtime only
                logger.error("Failed to initialize GCS client for images: %s", exc)
                self._client = None
                self._bucket = None
        elif self.bucket_name and not _GCS_AVAILABLE:
            logger.warning(
                "google-cloud-storage not installed; falling back to local image storage"
            )

    @property
    def uses_gcs(self) -> bool:
        return self._bucket is not None

    def _is_dev_env(self) -> bool:
        """Check if running in development environment.

        Checks multiple environment variables to determine if running in development:
        - ENV: 'prod' or 'stg' indicates production/staging
        - ENVIRONMENT_NAME: 'prod' or 'stg' indicates production/staging
        - ENVIRONMENT: Legacy check for 'development'

        Returns True only if explicitly in development mode.
        Defaults to False (production) for safety.
        """
        # Check ENV (used in Cloud Run configs)
        env = os.getenv('ENV', '').lower()
        if env in ('prod', 'stg', 'production', 'staging'):
            return False

        # Check ENVIRONMENT_NAME (also used in Cloud Run configs)
        env_name = os.getenv('ENVIRONMENT_NAME', '').lower()
        if env_name in ('prod', 'stg', 'production', 'staging'):
            return False

        # Check legacy ENVIRONMENT variable
        environment = os.getenv('ENVIRONMENT', '').lower()
        if environment in ('prod', 'stg', 'production', 'staging'):
            return False
        if environment == 'development':
            return True

        # Default to False (production behavior) for safety
        # This ensures images are stored without hostname prefix unless explicitly in dev
        return False

    def _blob_path(self, session_id: str, filename: str, image_type: str = "portrait") -> str:
        """Construct GCS blob path organized by session and image type.

        In development environments, includes hostname prefix to avoid conflicts
        between developers working on the same staging bucket.

        Args:
            session_id: Campaign/session identifier (e.g., "campaign_99")
            filename: Image filename (e.g., "portrait_XXX.png")
            image_type: Type of image ("portrait", "scene", etc.)

        Returns:
            Dev: media/images/{hostname}/campaign_99/portraits/portrait_XXX.png
            Prod: media/images/campaign_99/portraits/portrait_XXX.png
        """
        base = self.base_path
        type_dir = f"{image_type}s"  # "portraits", "scenes", etc.

        # Include hostname prefix in development to avoid conflicts
        if self._is_dev_env():
            hostname = socket.gethostname().lower().replace('.', '-').replace('_', '-')
            path = f"{base}/{hostname}/{session_id}/{type_dir}/{filename}"
        else:
            path = f"{base}/{session_id}/{type_dir}/{filename}"

        return path if base else f"{session_id}/{type_dir}/{filename}"

    def persist_image(
        self,
        *,
        session_id: str,
        image_bytes: bytes,
        image_type: str = "portrait",
        mime_type: str = "image/png",
        skip_gcs_upload: bool = False,
        filename: Optional[str] = None,
    ) -> ImageArtifact:
        """Persist an image artifact to GCS (and optionally local storage as fallback).

        When GCS is available, images are uploaded directly to GCS without writing to local disk.
        Local storage is only used as a fallback when GCS upload fails or GCS is unavailable.

        Args:
            session_id: Campaign/session identifier
            image_bytes: Raw image data
            image_type: Type of image ("portrait", "scene", etc.)
            mime_type: MIME type (default: image/png)
            skip_gcs_upload: Skip GCS upload (for temporary images)
            filename: Optional explicit filename to persist (kept as-is if provided)

        Returns:
            ImageArtifact with proxy URL
        """
        if not self.enabled:
            raise RuntimeError("Image storage disabled; cannot persist artifact")

        artifact_id = uuid.uuid4().hex
        extension = mime_type.split("/")[-1]
        extension = extension.lstrip(".") or "png"
        chosen_name = None
        if filename:
            provided = Path(filename).name
            if not Path(provided).suffix:
                provided = f"{provided}.{extension}"
            chosen_name = provided
        if not chosen_name:
            chosen_name = f"{image_type}_{artifact_id}.{extension}"

        size_bytes = len(image_bytes)
        created_at = datetime.utcnow()
        storage_path = self._blob_path(session_id, chosen_name, image_type)

        # Always expose backend proxy URL so clients fetch via API
        # Use the /api/images/{path} endpoint which resolves both local and GCS images
        url = f"/api/images/{storage_path}"
        bucket = None
        uploaded_to_gcs = False

        # Try GCS upload first if available
        if self.uses_gcs and not skip_gcs_upload:
            try:
                blob = self._bucket.blob(storage_path)  # type: ignore[union-attr]
                blob.upload_from_string(image_bytes, content_type=mime_type)
                bucket = self.bucket_name
                uploaded_to_gcs = True
                logger.debug(
                    "✅ Uploaded %s to GCS: %s (session=%s, bytes=%d, path=%s)",
                    image_type,
                    chosen_name,
                    session_id,
                    size_bytes,
                    storage_path,
                )
            except Exception as exc:
                logger.error("Failed to upload image artifact to GCS, falling back to local storage: %s", exc)

        # Fall back to local storage if GCS upload failed or was skipped
        if not uploaded_to_gcs:
            session_dir = self.local_root / session_id
            type_dir = session_dir / f"{image_type}s"
            type_dir.mkdir(parents=True, exist_ok=True)
            file_path = type_dir / chosen_name
            file_path.write_bytes(image_bytes)
            logger.debug(
                "💾 Saved %s to local storage: %s (session=%s, bytes=%d)",
                image_type,
                chosen_name,
                session_id,
                size_bytes,
            )

        return ImageArtifact(
            id=artifact_id,
            session_id=session_id,
            url=url,
            mime_type=mime_type,
            size_bytes=size_bytes,
            created_at=created_at,
            storage_path=storage_path,
            bucket=bucket,
            image_type=image_type,
        )

    def resolve_local_path(self, session_id: str, filename: str) -> Path:
        """Resolve local filesystem path for an image."""
        candidates = [
            self.local_root / session_id / filename,
        ]
        # Common type directories (from ImageStorageType enum + legacy "images")
        for type_dir in ImageStorageType.all_directories() + ["images"]:
            candidates.append(self.local_root / session_id / type_dir / filename)

        # Legacy top-level location
        candidates.append(self.local_root / filename)

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                continue
            if resolved.exists():
                return resolved

        return (self.local_root / session_id / filename).resolve()

    def read_artifact_bytes(self, session_id: str, filename: str) -> bytes:
        """Read image bytes from GCS (if available) or local filesystem.

        Tries multiple path patterns for backward compatibility:
        1. New: media/images/campaign_XX/portraits/portrait_XXX.png
        2. Old: campaign_XX/media/images/portrait_XXX.png (legacy path)
        3. Hostname-prefixed: media/images/{hostname}/campaign_XX/portraits/portrait_XXX.png

        Args:
            session_id: Campaign/session identifier
            filename: Image filename

        Returns:
            Raw image bytes

        Raises:
            FileNotFoundError: If image not found in GCS or local storage
        """
        # Try to infer image type from filename, but have fallback list
        inferred_type = filename.split("_")[0] if "_" in filename else "portrait"

        # List of storage types to try in order (inferred first, then all known types)
        types_to_try = [inferred_type] + ImageStorageType.all_types()
        # Remove duplicates while preserving order
        seen = set()
        types_to_try = [x for x in types_to_try if not (x in seen or seen.add(x))]

        # Try GCS first if available
        if self.uses_gcs:
            hostname = socket.gethostname().lower().replace('.', '-').replace('_', '-')

            # Try each image type in priority order
            for image_type in types_to_try:
                type_dir = f"{image_type}s"

                # Try new path structure (prod: media/images/campaign_XX/{type}s/image.png)
                new_path = f"{self.base_path}/{session_id}/{type_dir}/{filename}"
                try:
                    blob = self._bucket.blob(new_path)  # type: ignore[union-attr]
                    if blob.exists():
                        logger.info("Found image in GCS at new path: %s", new_path)
                        return blob.download_as_bytes()
                except Exception as exc:
                    logger.debug("Failed to read image from GCS (new path %s): %s", new_path, exc)

                # Try hostname-prefixed path (dev: media/images/{hostname}/campaign_XX/{type}s/image.png)
                hostname_path = f"{self.base_path}/{hostname}/{session_id}/{type_dir}/{filename}"
                try:
                    blob = self._bucket.blob(hostname_path)  # type: ignore[union-attr]
                    if blob.exists():
                        logger.info("Found image in GCS at hostname-prefixed path: %s", hostname_path)
                        return blob.download_as_bytes()
                except Exception as exc:
                    logger.debug("Failed to read image from GCS (hostname path %s): %s", hostname_path, exc)

            # Try legacy path for backward compatibility (campaign_XX/media/images/image.png)
            legacy_path = f"{session_id}/{self.base_path}/{filename}"
            try:
                blob = self._bucket.blob(legacy_path)  # type: ignore[union-attr]
                if blob.exists():
                    logger.info("Found image in GCS at legacy path: %s", legacy_path)
                    return blob.download_as_bytes()
            except Exception as exc:
                logger.warning("Failed to read image from GCS (legacy path), falling back to local: %s", exc)

        # Fall back to local storage
        local_path = self.resolve_local_path(session_id, filename)
        if not local_path.exists():
            raise FileNotFoundError(
                f"Image not found in GCS or local storage: session={session_id} filename={filename} "
                f"(tried types: {types_to_try})"
            )
        logger.info("Found image in local storage: %s", local_path)
        return local_path.read_bytes()


# Singleton instance
image_artifact_store = ImageArtifactStore()

__all__ = [
    "ImageArtifact",
    "ImageArtifactStore",
    "ImageStorageType",
    "image_artifact_store",
]
