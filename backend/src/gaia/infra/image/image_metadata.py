"""
Simple image metadata storage system for preserving prompts and other metadata.
Stores metadata within campaign folders for better organization.
"""
import json
import os
import shutil
import logging
import mimetypes
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from gaia_private.session.session_storage import SessionStorage
from gaia.infra.storage.campaign_object_store import get_campaign_object_store
from gaia.infra.image.image_artifact_store import image_artifact_store

logger = logging.getLogger(__name__)

class ImageMetadataManager:
    """Manages metadata for generated images within campaign folders."""
    
    def __init__(self, campaigns_dir: str = None):
        # Resolve campaign storage using SessionStorage so we support new + legacy layouts.
        self.storage = SessionStorage(ensure_legacy_dirs=True)
        self.object_store = get_campaign_object_store()

        # Location where image binaries live (legacy/global)
        self.image_root = Path(os.path.expanduser(os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images')))
        self.image_root.mkdir(parents=True, exist_ok=True)

        # Legacy metadata dir for migration
        self.legacy_metadata_dir = self.image_root / "metadata"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_metadata_from_store(self, campaign_id: str, base_name: str) -> Optional[Dict]:
        if not getattr(self.object_store, "enabled", False):
            return None
        try:
            return self.object_store.read_json(
                campaign_id,
                f"media/images/metadata/{base_name}.json",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to read image metadata from store for %s/%s: %s", campaign_id, base_name, exc)
            return None

    def _ensure_local_image(self, campaign_id: str, metadata: Dict) -> Dict:
        filename = metadata.get('storage_filename') or metadata.get('filename')
        if not filename:
            return metadata

        storage_filename = metadata.get("storage_filename") or filename
        metadata['storage_filename'] = storage_filename
        metadata['filename'] = storage_filename

        storage_path_raw = metadata.get("storage_path")
        container_path: Optional[Path] = None

        if storage_path_raw:
            storage_rel = Path(storage_path_raw)
            base_path = Path(image_artifact_store.base_path) if getattr(image_artifact_store, 'base_path', None) else None
            try:
                rel = storage_rel.relative_to(base_path) if base_path else storage_rel
            except ValueError:
                rel = storage_rel
            container_path = (image_artifact_store.local_root / rel).resolve()

        if container_path is None or not container_path.exists():
            image_type = (metadata.get('type') or 'scene').lower().rstrip('s')
            type_dir = f"{image_type}s"
            candidate = (image_artifact_store.local_root / Path(campaign_id) / type_dir / storage_filename).resolve()
            if candidate.exists():
                container_path = candidate
            else:
                session_relative = (image_artifact_store.local_root / Path(campaign_id) / storage_filename).resolve()
                if session_relative.exists():
                    container_path = session_relative
                else:
                    legacy_candidate = (image_artifact_store.local_root / storage_filename).resolve()
                    container_path = candidate
                    if legacy_candidate.exists():
                        try:
                            container_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(legacy_candidate), str(container_path))
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Failed to relocate legacy image %s to %s: %s", legacy_candidate, container_path, exc)
                            container_path = legacy_candidate
                    else:
                        container_path = session_relative

        if not container_path.exists():
            # Prefer any path recorded in metadata as a source of truth
            candidates = [
                metadata.get('local_path'),
            ]
            for raw in candidates:
                if not raw:
                    continue
                candidate = Path(os.path.expanduser(str(raw)))
                if not candidate.exists() or not candidate.is_file():
                    continue
                try:
                    shutil.copy2(candidate, container_path)
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to copy image %s from %s: %s", filename, candidate, exc)

        # NOTE: We no longer download from GCS to local storage automatically.
        # Images are served directly from GCS via the API routes.
        # Local storage is only used for images that haven't been migrated yet.

        if container_path.exists():
            container_resolved = container_path.resolve()
            metadata['local_path'] = str(container_resolved)
            try:
                metadata['size'] = container_resolved.stat().st_size
            except OSError:  # pragma: no cover - transient filesystem issue
                metadata.pop('size', None)
        else:
            # Preserve any previously recorded valid path
            raw = metadata.get('local_path')
            if raw:
                candidate = Path(os.path.expanduser(str(raw)))
                if candidate.exists():
                    metadata['local_path'] = str(candidate.resolve())

        if not metadata.get("storage_path") and metadata.get("storage_filename"):
            image_type = metadata.get("type", "scene") or "scene"
            metadata["storage_path"] = image_artifact_store._blob_path(
                campaign_id,
                metadata["storage_filename"],
                image_type,
            )

        # Remove legacy duplicate fields to keep metadata slim
        metadata.pop('session_media_path', None)
        metadata.pop('absolute_path', None)
        metadata.pop('path', None)
        metadata.pop('container_path', None)

        return metadata
    
    def save_metadata(self, image_filename: str, metadata: Dict, campaign_id: str = "default") -> bool:
        """Save metadata for an image within a campaign folder."""
        try:
            campaign_dir = self.storage.resolve_session_dir(campaign_id, create=True)
            if campaign_dir is None:
                return False
            
            # Create image_metadata subfolder in campaign
            metadata_dir = campaign_dir / "image_metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)

            legacy_abs = self.image_root / image_filename
            try:
                artifact_path = image_artifact_store.resolve_local_path(
                    campaign_id,
                    metadata.get("storage_filename") or Path(image_filename).name,
                )
            except Exception:  # pragma: no cover - defensive
                artifact_path = legacy_abs

            # Create metadata filename (same name as image but .json)
            base_name = Path(image_filename).stem
            metadata_file = metadata_dir / f"{base_name}.json"

            # Add required fields
            metadata = dict(metadata)
            metadata.setdefault('storage_filename', Path(image_filename).name)
            metadata['campaign_id'] = campaign_id
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now().isoformat()
            artifact = None
            preferred_local = None
            storage_filename = metadata.get("storage_filename") or Path(image_filename).name
            try:
                preferred_local = image_artifact_store.resolve_local_path(campaign_id, storage_filename)
            except Exception:  # pragma: no cover - defensive
                preferred_local = None

            container_path = preferred_local if preferred_local and preferred_local.exists() else None
            if not container_path and artifact_path.exists():
                container_path = artifact_path
            if not container_path and legacy_abs.exists():
                container_path = legacy_abs
            if container_path:
                container_resolved = container_path.resolve()
                metadata['local_path'] = str(container_resolved)
                try:
                    metadata['size'] = container_resolved.stat().st_size
                except OSError:  # pragma: no cover - transient filesystem issue
                    metadata.pop('size', None)
            else:
                metadata['local_path'] = str(legacy_abs.resolve())

            if not metadata.get("storage_path"):
                image_type = metadata.get("type", "scene") or "scene"
                metadata["storage_path"] = image_artifact_store._blob_path(
                    campaign_id,
                    metadata["storage_filename"],
                    image_type,
                )

            if not metadata.get("storage_path"):
                image_type = metadata.get("type", "scene") or "scene"
                metadata["storage_path"] = image_artifact_store._blob_path(
                    campaign_id,
                    metadata["storage_filename"],
                    image_type,
                )

            should_persist_to_media_bucket = (
                container_path is not None
                and container_path.exists()
                and container_path.is_file()
                and image_artifact_store.uses_gcs
                and (
                    metadata.get("bucket") != image_artifact_store.bucket_name
                    or not metadata.get("storage_path")
                )
            )

            if should_persist_to_media_bucket:
                try:
                    mime_type = metadata.get("mime_type") or mimetypes.guess_type(image_filename)[0] or "image/png"
                    artifact = image_artifact_store.persist_image(
                        session_id=campaign_id,
                        image_bytes=container_path.read_bytes(),
                        image_type=metadata.get("type", "scene"),
                        mime_type=mime_type,
                        filename=image_filename,
                    )
                    metadata["bucket"] = artifact.bucket
                    metadata["storage_path"] = artifact.storage_path
                    metadata["proxy_url"] = artifact.url
                    metadata["gcs_uploaded"] = artifact.bucket is not None
                    metadata["storage_filename"] = Path(artifact.storage_path).name
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to persist image %s to media bucket: %s", image_filename, exc)
                    artifact = None

            # Ensure proxy URL is set for clients
            # Priority: 1) existing proxy_url from caller, 2) artifact url, 3) generate from storage_path
            if not metadata.get("proxy_url"):
                if artifact:
                    metadata["image_url"] = artifact.url
                    metadata["proxy_url"] = artifact.url
                else:
                    # Generate proxy_url matching artifact store format: /api/images/{storage_path}
                    # This matches the URL format from image_artifact_store.py:180
                    storage_path = metadata.get("storage_path", f"{campaign_id}/{metadata['storage_filename']}")
                    metadata["proxy_url"] = f"/api/images/{storage_path}"

            # Remove legacy duplicate fields to keep records small
            metadata.pop('session_media_path', None)
            metadata.pop('absolute_path', None)
            metadata.pop('path', None)
            metadata.pop('container_path', None)
            # Save metadata locally
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Mirror metadata and binary to store (GCS when enabled)
            try:
                if getattr(self.object_store, "enabled", False):
                    self.object_store.write_json(
                        metadata,
                        campaign_id,
                        f"media/images/metadata/{base_name}.json",
                    )
                    if legacy_abs.exists() and not image_artifact_store.uses_gcs:
                        self.object_store.upload_file(
                            str(legacy_abs),
                            campaign_id,
                            f"media/images/{image_filename}",
                        )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Image store mirror failed for %s: %s", image_filename, exc)

            return True
        except Exception as e:
            logger.error("Error saving metadata: %s", e)
            return False
    
    def get_metadata(self, image_filename: str, campaign_id: Optional[str] = None) -> Optional[Dict]:
        """Get metadata for an image from a specific campaign or search all campaigns."""
        try:
            base_name = Path(image_filename).stem
            
            # If campaign_id is specified, look only in that campaign
            if campaign_id:
                campaign_dir = self.storage.resolve_session_dir(campaign_id)
                if campaign_dir:
                    metadata_file = campaign_dir / "image_metadata" / f"{base_name}.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        return self._ensure_local_image(campaign_id, metadata)
                store_payload = self._load_metadata_from_store(campaign_id, base_name)
                if store_payload:
                    return self._ensure_local_image(campaign_id, store_payload)
            else:
                searched: set[str] = set()
                for session_id, campaign_dir, _ in self.storage.iter_session_dirs():
                    searched.add(session_id)
                    metadata_file = campaign_dir / "image_metadata" / f"{base_name}.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        return self._ensure_local_image(session_id, metadata)

                if getattr(self.object_store, "enabled", False):
                    try:
                        for remote_session, _ in self.object_store.list_metadata():
                            if remote_session in searched:
                                continue
                            payload = self._load_metadata_from_store(remote_session, base_name)
                            if payload:
                                return self._ensure_local_image(remote_session, payload)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Error listing metadata from store: %s", exc)
            
            # Check legacy location
            legacy_file = self.legacy_metadata_dir / f"{base_name}.json"
            if legacy_file.exists():
                with open(legacy_file, 'r') as f:
                    return json.load(f)
                    
            return None
        except Exception as e:
            logger.error("Error reading metadata: %s", e)
            return None
    
    def list_campaign_images(self, campaign_id: str) -> List[Dict]:
        """List all images and metadata for a specific campaign."""
        metadata_list: List[Dict] = []
        seen: set[str] = set()
        try:
            # Don't create campaign directory if it doesn't exist - just return empty list
            campaign_dir = self.storage.resolve_session_dir(campaign_id, create=False)
            metadata_dir = None
            if campaign_dir and campaign_dir.exists():
                metadata_dir = campaign_dir / "image_metadata"
                if metadata_dir.exists():
                    for metadata_file in metadata_dir.glob("*.json"):
                        try:
                            with open(metadata_file, 'r') as f:
                                metadata = json.load(f)
                            metadata = self._ensure_local_image(campaign_id, metadata)
                            image_path_raw = metadata.get('local_path')
                            if image_path_raw:
                                image_path = Path(os.path.expanduser(image_path_raw))
                                if image_path.exists():
                                    metadata['local_path'] = str(image_path.resolve())
                                    metadata['size'] = image_path.stat().st_size
                            metadata_list.append(metadata)
                            seen.add(metadata_file.stem)
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Error reading metadata file %s: %s", metadata_file, exc)

            if getattr(self.object_store, "enabled", False):
                try:
                    for name in self.object_store.list_json_prefix(campaign_id, "media/images/metadata"):
                        base = Path(name).stem
                        if base in seen:
                            continue
                        payload = self._load_metadata_from_store(campaign_id, base)
                        if not isinstance(payload, dict):
                            continue
                        metadata = self._ensure_local_image(campaign_id, payload)
                        image_path_raw = metadata.get('local_path')
                        if image_path_raw:
                            image_path = Path(os.path.expanduser(image_path_raw))
                            if image_path.exists():
                                metadata['local_path'] = str(image_path.resolve())
                                metadata.setdefault('size', image_path.stat().st_size)
                        metadata_list.append(metadata)
                        seen.add(base)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Error listing campaign images from store: %s", exc)

            metadata_list.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True,
            )
        except Exception as exc:
            logger.error("Error listing campaign images: %s", exc)
        
        return metadata_list
    
    def list_all_metadata(self) -> List[Dict]:
        """List all available metadata across all campaigns."""
        metadata_list: List[Dict] = []
        try:
            session_ids: set[str] = set()
            for session_id, _, _ in self.storage.iter_session_dirs():
                session_ids.add(session_id)
            if getattr(self.object_store, "enabled", False):
                try:
                    for session_id, _ in self.object_store.list_metadata():
                        session_ids.add(session_id)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Error listing metadata ids from store: %s", exc)

            for session_id in session_ids:
                metadata_list.extend(self.list_campaign_images(session_id))

            metadata_list.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True,
            )
        except Exception as exc:
            logger.error("Error listing all metadata: %s", exc)
        
        return metadata_list

# Global instance
_metadata_manager = None
_metadata_manager_image_root = None  # Track current IMAGE_STORAGE_PATH to reset on change

def get_metadata_manager() -> ImageMetadataManager:
    """Get the global metadata manager instance.

    Resets the singleton if `IMAGE_STORAGE_PATH` changed since last access to
    keep absolute paths consistent in test environments that override it per test.
    """
    global _metadata_manager, _metadata_manager_image_root

    current_root = os.path.expanduser(os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images'))
    if _metadata_manager is None or _metadata_manager_image_root != current_root:
        _metadata_manager = ImageMetadataManager()
        _metadata_manager_image_root = current_root
    return _metadata_manager
