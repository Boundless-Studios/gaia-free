"""
Simple Campaign Manager V2 - Uses new directory structure: campaigns/ID - Name/logs/ and /data/
"""
import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import re
import shutil

from gaia.utils.singleton import SingletonMeta
from gaia_private.session.session_storage import SessionStorage
from gaia.infra.storage.campaign_store import get_campaign_store
from gaia.mechanics.character.character_manager import CharacterManager
from gaia.models import CampaignData, GameStyle, GameTheme

logger = logging.getLogger(__name__)


class SimpleCampaignManager(metaclass=SingletonMeta):
    """Simple campaign manager that stores campaigns in their own directories."""
    
    @staticmethod
    def _parse_timestamp(value: Optional[Any]) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            parsed = value
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except Exception:  # noqa: BLE001
                return None
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            if candidate.endswith("Z"):
                candidate = candidate[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(candidate)
            except Exception:  # noqa: BLE001
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    @classmethod
    def _max_timestamp(cls, *values: Optional[Any]) -> Optional[datetime]:
        parsed = [cls._parse_timestamp(v) for v in values]
        parsed = [p for p in parsed if p is not None]
        if not parsed:
            return None
        return max(parsed)

    def __init__(self, base_path: Optional[str] = None):
        """Initialize the campaign manager.
        
        Args:
            base_path: Base directory where all campaigns are stored (optional)
        """
        # Initialize shared session storage helper (handles legacy layout too)
        self.storage = SessionStorage(base_path, ensure_legacy_dirs=True)
        self.environment_name = self.storage.environment
        # New-layout sessions live directly under storage.base_path.
        # Legacy-layout sessions live under storage.legacy_base.
        # Use explicit fields to avoid confusing the two.
        self.base_path = self.storage.base_path
        self.legacy_base_path = self.storage.legacy_base
        self._store = get_campaign_store(self.storage)
        
        # Simple cache to avoid duplicate loads
        self._history_cache = {}
        self._cache_timestamp = {}
        self._character_managers: Dict[str, CharacterManager] = {}
        self._active_campaigns: Dict[str, CampaignData] = {}

    def _update_metadata(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        if not updates:
            return {}
        try:
            self.storage.save_metadata(campaign_id, updates)
        except FileNotFoundError:
            metadata_path = self.storage.metadata_path(campaign_id)
            if metadata_path:
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                self.storage.save_metadata(campaign_id, updates)

        store_payload: Dict[str, Any] = {}
        if self._store:
            existing = self._store.read_json("metadata", f"{campaign_id}.json")
            if not isinstance(existing, dict):
                existing = {}
            existing.update(updates)
            existing["campaign_id"] = campaign_id
            self._store.write_json(existing, "metadata", f"{campaign_id}.json")
            store_payload = existing
        return store_payload

    def mark_campaign_loaded(self, campaign_id: str) -> None:
        # Normalize campaign ID to bare campaign_<number> format
        match = re.match(r"(campaign_\d+)", campaign_id.strip() if campaign_id else "")
        normalized_id = match.group(1) if match else campaign_id

        now_iso = datetime.now(timezone.utc).isoformat()
        existing_store = self._store.read_json("metadata", f"{normalized_id}.json") if self._store else {}
        if not isinstance(existing_store, dict):
            existing_store = {}
        try:
            local_md = self.storage.load_metadata(normalized_id)
            if isinstance(local_md, dict):
                existing_store.update(local_md)
        except FileNotFoundError:
            pass

        last_messaged = existing_store.get("last_messaged_at") or existing_store.get("last_played")
        last_played_dt = self._max_timestamp(last_messaged, now_iso)
        updates = {
            "last_loaded_at": now_iso,
            "updated_at": now_iso,
        }
        if last_played_dt:
            updates["last_played"] = last_played_dt.isoformat()
        self._update_metadata(normalized_id, updates)
    
    def _get_campaign_dir(
        self,
        campaign_id: str,
        name: Optional[str] = None,
        *,
        create: bool = False,
    ) -> Optional[Path]:
        """Resolve the directory path for a campaign."""
        path = self.storage.resolve_session_dir(campaign_id, create=create)
        if path and path.parent == self.storage.base_path and name:
            # Persist display name metadata for new layout directories.
            self.storage.save_metadata(
                campaign_id,
                {
                    "name": name,
                },
            )
        return path
    
    def _parse_campaign_dirname(self, dirname: str) -> tuple[str, Optional[str]]:
        """Parse campaign ID and name from directory name.
        
        Args:
            dirname: e.g. "campaign_1" or "campaign_2 - The Lost Mine"
            
        Returns:
            Tuple of (campaign_id, campaign_name)
        """
        # Try to match pattern "campaign_X - Name"
        match = re.match(r'(campaign_\d+)(?:\s*-\s*(.+))?', dirname)
        if match:
            campaign_id = match.group(1)
            campaign_name = match.group(2)
            return campaign_id, campaign_name
        
        # Handle legacy "default" campaigns - should not happen anymore
        if dirname.startswith("default - "):
            # Extract name after "default - "
            campaign_name = dirname.replace("default - ", "")
            # Generate a proper campaign ID
            return self.get_next_campaign_id(), campaign_name
        
        # Fallback for directories that don't match pattern
        # Treat the whole dirname as campaign_id with no name
        return dirname, None
    
    def _find_campaign_dir(self, campaign_id: str) -> Optional[Path]:
        """Find the directory for a given campaign ID.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Path to campaign directory or None if not found
        """
        return self.storage.resolve_session_dir(campaign_id)
    
    def get_next_campaign_id(self) -> str:
        """Get the next sequential campaign ID.
        
        Returns:
            String like "campaign_1", "campaign_2", etc.
        """
        existing_result = self.list_campaigns()
        existing = existing_result["campaigns"]
        
        # Extract numbers from existing campaign IDs
        numbers = []
        for campaign in existing:
            match = re.match(r'campaign_(\d+)', campaign['id'])
            if match:
                numbers.append(int(match.group(1)))
        
        # Find the next number
        next_num = max(numbers) + 1 if numbers else 1
        campaign_id = f"campaign_{next_num}"
        
        logger.info(f"🆕 Generated next campaign ID: {campaign_id} for environment: {self.environment_name}")
        return campaign_id
    
    def list_campaigns(self, sort_by: str = "last_played", ascending: bool = False, 
                      limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """List all campaigns with pagination and sorting.
        
        Args:
            sort_by: Field to sort by ("last_played", "name", "message_count")
            ascending: Sort in ascending order if True
            limit: Maximum number of campaigns to return
            offset: Number of campaigns to skip
            
        Returns:
            Dict with campaigns list and total count
        """
        campaigns: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        metadata_entries = self._store.list_json_prefix("metadata") if self._store else []
        for entry in metadata_entries:
            session_id = Path(entry).stem
            if session_id in seen_ids:
                continue
            try:
                md = self._store.read_json("metadata", entry) if self._store else None
                if not isinstance(md, dict):
                    md = {}
                display_name = md.get("name") or md.get("title") or session_id
                last_messaged = md.get("last_messaged_at") or md.get("last_played") or md.get("updated_at")
                last_loaded = md.get("last_loaded_at")
                last_played_dt = self._max_timestamp(last_messaged, last_loaded, md.get("last_played"))
                if last_played_dt is None:
                    last_played_dt = datetime.now()
                message_count = int(md.get("message_count", 0))
                campaign_dir = self._find_campaign_dir(session_id)
                directory_name = campaign_dir.name if campaign_dir else session_id
                campaigns.append(
                    {
                        "id": session_id,
                        "name": display_name,
                        "message_count": message_count,
                        "last_played": last_played_dt.isoformat(),
                        "last_played_ts": last_played_dt.timestamp(),
                        "last_messaged_at": last_messaged,
                        "last_loaded_at": last_loaded,
                        "directory": directory_name,
                    }
                )
                seen_ids.add(session_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error parsing campaign metadata for %s: %s", session_id, exc)

        for session_id, campaign_dir, is_legacy in self.storage.iter_session_dirs():
            if session_id in seen_ids:
                continue

            try:
                log_file = campaign_dir / "logs" / "chat_history.json"
                if not log_file.exists():
                    log_file = campaign_dir / "chat_history.json"

                message_count = 0
                last_modified = datetime.fromtimestamp(campaign_dir.stat().st_mtime, tz=timezone.utc)

                last_message_ts = None
                if log_file.exists():
                    with open(log_file, "r", encoding="utf-8") as fh:
                        messages = json.load(fh)
                        if isinstance(messages, list):
                            message_count = len(messages)
                            if messages:
                                last_message_ts = messages[-1].get("timestamp")
                    last_modified = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)

                metadata = self.storage.load_metadata(session_id)

                # Skip campaigns with corrupted metadata AND no chat history
                # (likely partially deleted or corrupted campaigns)
                if not metadata and not is_legacy and message_count == 0:
                    logger.warning(
                        f"⚠️ Skipping campaign {session_id} - corrupted metadata and no chat history (likely deleted)"
                    )
                    continue

                if metadata:
                    display_name = (
                        metadata.get("name")
                        or metadata.get("display_name")
                        or session_id
                    )
                    last_loaded = metadata.get("last_loaded_at")
                    legacy_last_played = metadata.get("last_played")
                elif is_legacy:
                    _, campaign_name = self._parse_campaign_dirname(campaign_dir.name)
                    display_name = campaign_name or session_id
                    last_loaded = None
                    legacy_last_played = None
                else:
                    display_name = session_id
                    last_loaded = None
                    legacy_last_played = None

                last_played_dt = self._max_timestamp(last_message_ts, last_loaded, legacy_last_played, last_modified.isoformat())
                if last_played_dt is None:
                    last_played_dt = last_modified

                campaigns.append(
                    {
                        "id": session_id,
                        "name": display_name,
                        "message_count": message_count,
                        "last_played": last_played_dt.isoformat(),
                        "last_played_ts": last_played_dt.timestamp(),
                        "last_messaged_at": last_message_ts,
                        "last_loaded_at": last_loaded,
                        "directory": campaign_dir.name,
                    }
                )
                seen_ids.add(session_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("❌ Error reading campaign %s: %s", campaign_dir, exc)
                continue

        # Sort campaigns
        if sort_by == "last_played":
            campaigns.sort(key=lambda x: (x.get("last_played_ts", 0), x["id"]), reverse=not ascending)
        elif sort_by == "name":
            campaigns.sort(key=lambda x: x["name"].lower(), reverse=not ascending)
        elif sort_by == "message_count":
            campaigns.sort(key=lambda x: (x["message_count"], x["id"]), reverse=not ascending)
        else:
            campaigns.sort(key=lambda x: x["id"], reverse=not ascending)
        
        # Apply pagination
        total_count = len(campaigns)
        campaigns = campaigns[offset:offset + limit]
        
        # Remove helper fields before returning
        for campaign in campaigns:
            campaign.pop('last_played_ts', None)
        
        logger.info(f"📋 Found {total_count} campaigns, returning {len(campaigns)} after pagination (offset: {offset}, limit: {limit})")
        return {
            "campaigns": campaigns,
            "total_count": total_count
        }

    def create_campaign(
        self,
        session_id: str,
        title: str = "New Campaign",
        description: str = "",
        game_style: str = "balanced",
    ) -> Dict[str, Any]:
        """Create and persist a new campaign using the simple storage layout."""
        try:
            style_enum = GameStyle(game_style.lower())
        except ValueError:
            style_enum = GameStyle.BALANCED

        campaign_data = CampaignData(
            campaign_id=session_id,
            title=title,
            description=description,
            game_style=style_enum,
            game_theme=GameTheme.FANTASY,
        )

        # Set scene storage mode to database for new campaigns
        campaign_data.set_scene_storage_mode("database")
        # Generate UUID for database scene storage (required by EnhancedSceneManager)
        campaign_data.custom_data["campaign_uuid"] = str(uuid.uuid4())

        self.storage.resolve_session_dir(session_id, create=True)

        data_saved = self.save_campaign_data(session_id, campaign_data)
        if not data_saved:
            return {
                "campaign_id": session_id,
                "title": title,
                "description": description,
                "game_style": game_style,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
            }

        self.save_campaign(session_id, [], name=title)

        self._update_metadata(
            session_id,
            {
                "title": title,
                "name": title,
                "description": description,
                "game_style": style_enum.value,
            },
        )

        self.get_character_manager(session_id)

        return {
            "campaign_id": session_id,
            "title": title,
            "description": description,
            "game_style": game_style,
            "created_at": campaign_data.created_at.isoformat(),
            "success": True,
        }

    def load_campaign(self, campaign_id: str):
        """Load campaign from disk.
        
        Args:
            campaign_id: Campaign identifier
        
        Returns:
            CampaignData object or None if not found
        """
        from gaia.models.campaign import CampaignData

        cached = self._active_campaigns.get(campaign_id)
        if cached:
            return cached

        # Try local first
        campaign_dir = self._find_campaign_dir(campaign_id)
        if campaign_dir:
            metadata_file = campaign_dir / "data" / "campaign_data.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        campaign_data = CampaignData.from_dict(metadata)
                        self._active_campaigns[campaign_id] = campaign_data
                        logger.info(f"📖 Loaded campaign {campaign_id} metadata with current_scene_id: {campaign_data.current_scene_id}")
                        return campaign_data
                except Exception as e:
                    logger.error(f"❌ Error loading campaign metadata: {e}")
        
        # Fallback to unified store (GCS/local hybrid)
        payload = self._store.read_json(campaign_id, "data/campaign_data.json") if self._store else None
        if isinstance(payload, dict) and payload:
            try:
                campaign_data = CampaignData.from_dict(payload)
                self._active_campaigns[campaign_id] = campaign_data
                return campaign_data
            except Exception as exc:  # noqa: BLE001
                logger.warning("Invalid campaign_data for %s from store: %s", campaign_id, exc)
        
        # Create basic campaign data from directory info
        fallback_title = campaign_dir.name if campaign_dir else campaign_id
        campaign_data = CampaignData(
            campaign_id=campaign_id,
            title=fallback_title,
            description='',
            character_ids=[]
        )
        return campaign_data
    
    def save_campaign_data(self, campaign_id: str, campaign_data) -> bool:
        """Save campaign data to disk.
        
        Args:
            campaign_id: Campaign identifier
            campaign_data: CampaignData object to save
            
        Returns:
            True if saved successfully
        """
        try:
            # Find the campaign directory, creating if necessary for new layout
            campaign_dir = self._find_campaign_dir(campaign_id)
            if not campaign_dir:
                campaign_dir = self.storage.resolve_session_dir(campaign_id, create=True)
            if not campaign_dir:
                logger.warning(f"⚠️ Campaign {campaign_id} not found for data save")
                return False
            
            # Create data directory if it doesn't exist
            data_dir = campaign_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Save campaign data to file
            metadata_file = data_dir / "campaign_data.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(campaign_data.to_dict(), f, indent=2, ensure_ascii=False, default=str)
            # Mirror via unified store (local + GCS)
            if self._store:
                try:
                    self._store.write_json(campaign_data.to_dict(), campaign_id, "data/campaign_data.json")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Campaign data store mirror failed for %s: %s", campaign_id, exc)
            
            logger.info(f"💾 Saved campaign data for {campaign_id} with current_scene_id: {campaign_data.current_scene_id}")
            self._active_campaigns[campaign_id] = campaign_data
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving campaign data for {campaign_id}: {e}")
            return False

    def get_character_manager(self, campaign_id: str) -> CharacterManager:
        """Return the CharacterManager associated with this campaign."""
        if campaign_id not in self._character_managers:
            self._character_managers[campaign_id] = CharacterManager(campaign_id)
        return self._character_managers[campaign_id]
    
    def load_campaign_history(self, campaign_id: str, allow_empty: bool = True) -> List[Dict[str, Any]]:
        """Load campaign chat history from disk.

        Args:
            campaign_id: Campaign identifier
            allow_empty: If False, raises exception if no history found for existing campaign

        Returns:
            List of message dictionaries

        Raises:
            FileNotFoundError: If allow_empty=False and no history file exists
            ValueError: If history file exists but is corrupted/unreadable
        """
        # Check cache first (with 1-second expiry to avoid stale data)
        import time
        current_time = time.time()
        if campaign_id in self._history_cache:
            cache_age = current_time - self._cache_timestamp.get(campaign_id, 0)
            if cache_age < 1.0:  # 1 second cache
                logger.debug(f"📦 Using cached history for {campaign_id} (age: {cache_age:.3f}s)")
                return self._history_cache[campaign_id]

        # Local path attempt
        campaign_dir = self._find_campaign_dir(campaign_id)
        if campaign_dir:
            log_file = campaign_dir / "logs" / "chat_history.json"
            if not log_file.exists():
                log_file = campaign_dir / "chat_history.json"
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                        if not isinstance(messages, list):
                            raise ValueError(f"Expected list, got {type(messages)}")
                        self._history_cache[campaign_id] = messages
                        self._cache_timestamp[campaign_id] = current_time
                        return messages
                except json.JSONDecodeError as e:
                    # CRITICAL: Don't silently return [] - this corrupts data downstream
                    logger.error(f"❌ CRITICAL: Corrupted JSON in {log_file}: {e}")
                    raise ValueError(f"Campaign {campaign_id} has corrupted history: {e}")
                except Exception as e:
                    logger.error(f"❌ Error loading campaign {campaign_id}: {e}")
                    raise ValueError(f"Failed to load campaign {campaign_id} history: {e}")

        # Object store fallback (via unified store)
        if self._store:
            payload = self._store.read_json(campaign_id, "logs/chat_history.json")
            if isinstance(payload, list):
                self._history_cache[campaign_id] = payload
                self._cache_timestamp[campaign_id] = current_time
                return payload
            elif isinstance(payload, dict):
                # Some older histories may be wrapped
                messages = payload.get("messages") if isinstance(payload, dict) else None
                if isinstance(messages, list):
                    self._history_cache[campaign_id] = messages
                    self._cache_timestamp[campaign_id] = current_time
                    return messages

        # No history found - this is only OK for truly new campaigns
        if not allow_empty and campaign_dir and campaign_dir.exists():
            raise FileNotFoundError(f"Campaign {campaign_id} exists but has no history file")

        logger.info(f"🆕 Campaign {campaign_id} has no history yet")
        return []
    
    def save_campaign(self, campaign_id: str, messages: List[Dict[str, Any]],
                     name: Optional[str] = None, force: bool = False) -> bool:
        """Save campaign history to disk with data loss protection.

        Args:
            campaign_id: Campaign identifier
            messages: List of message dictionaries
            name: Optional campaign name
            force: If True, bypass safety checks (use with caution)

        Returns:
            True if saved successfully
        """
        try:
            # Ensure session directory exists (new layout) or reuse legacy path
            campaign_dir = self._get_campaign_dir(campaign_id, name, create=True)
            if not campaign_dir:
                logger.warning("⚠️ Campaign %s could not resolve storage directory", campaign_id)
                return False

            # Ensure required subdirectories exist
            logs_dir = self.storage.ensure_subdir(campaign_id, "logs")
            data_dir = self.storage.ensure_subdir(campaign_id, "data")
            log_file = logs_dir / "chat_history.json"

            # DATA LOSS PROTECTION: Check existing file before overwriting
            new_count = len(messages) if isinstance(messages, list) else 0
            existing_count = 0

            if log_file.exists() and not force:
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, list):
                            existing_count = len(existing_data)
                        elif isinstance(existing_data, dict) and "messages" in existing_data:
                            existing_count = len(existing_data.get("messages", []))
                except Exception as read_err:
                    logger.warning(f"⚠️ Could not read existing history for safety check: {read_err}")

                # Safety check: refuse to save if we'd lose more than 50% of messages
                # Only applies when existing file has > 10 messages (avoid false positives for new campaigns)
                if existing_count > 10 and new_count < existing_count * 0.5:
                    logger.error(
                        f"🛡️ DATA LOSS PREVENTION: Refusing to save {campaign_id}! "
                        f"Would reduce messages from {existing_count} to {new_count}. "
                        f"Use force=True to override."
                    )
                    return False

                # Create backup before overwriting if we have significant existing data
                if existing_count > 5:
                    backup_file = logs_dir / f"chat_history.backup.json"
                    try:
                        shutil.copy2(log_file, backup_file)
                        logger.debug(f"📦 Created backup: {backup_file}")
                    except Exception as backup_err:
                        logger.warning(f"⚠️ Could not create backup: {backup_err}")

            now_iso = datetime.now().isoformat()
            last_message_ts = None
            if isinstance(messages, list) and messages:
                candidate = messages[-1]
                if isinstance(candidate, dict):
                    last_message_ts = candidate.get("timestamp") or candidate.get("time")
            if not last_message_ts:
                last_message_ts = now_iso

            message_count = new_count
            metadata_updates: Dict[str, Any] = {
                "updated_at": now_iso,
                "message_count": message_count,
                "last_messaged_at": last_message_ts,
                "last_played": last_message_ts,
            }
            if name:
                metadata_updates["name"] = name
            self._update_metadata(campaign_id, metadata_updates)

            # Add timestamps and message_ids if missing (preserve existing values)
            import uuid as uuid_mod
            for msg in messages:
                if 'timestamp' not in msg:
                    msg['timestamp'] = datetime.now().isoformat()
                if 'message_id' not in msg:
                    msg['message_id'] = f"msg_{uuid_mod.uuid4().hex[:12]}"

            # Save to logs directory
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)

            if existing_count > 0:
                logger.info(f"💾 Saved campaign {campaign_id}: {existing_count} -> {new_count} messages")

            # Mirror via hybrid store (to GCS when enabled)
            if self._store:
                self._store.write_json(messages, campaign_id, "logs/chat_history.json")

            # Invalidate cache after save
            if campaign_id in self._history_cache:
                del self._history_cache[campaign_id]
                del self._cache_timestamp[campaign_id]

            return True

        except Exception as e:
            logger.error(f"❌ Error saving campaign {campaign_id}: {e}")
            return False

    def append_message(self, campaign_id: str, message: Dict[str, Any]) -> bool:
        """Append a single message to campaign history (append-only, no full rewrite).

        This is the safe way to add messages - it reads the current file,
        appends the new message, and writes back. This prevents data loss
        from stale in-memory state.

        Args:
            campaign_id: Campaign identifier
            message: Message dict with role, content, timestamp, etc.

        Returns:
            True if appended successfully
        """
        import uuid as uuid_mod

        try:
            campaign_dir = self._find_campaign_dir(campaign_id)
            if not campaign_dir:
                logger.error(f"❌ Cannot append: campaign {campaign_id} not found")
                return False

            logs_dir = campaign_dir / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = logs_dir / "chat_history.json"

            # Read current history directly from disk (not cache)
            messages = []
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                        if not isinstance(messages, list):
                            logger.warning(f"⚠️ History was not a list, starting fresh")
                            messages = []
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Corrupted history file, cannot append: {e}")
                    return False

            # Add timestamp and message_id if missing
            if 'timestamp' not in message:
                message['timestamp'] = datetime.now().isoformat()
            if 'message_id' not in message:
                message['message_id'] = f"msg_{uuid_mod.uuid4().hex[:12]}"

            # Append the new message
            messages.append(message)

            # Write back
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)

            # Mirror to object store if enabled
            if self._store:
                self._store.write_json(messages, campaign_id, "logs/chat_history.json")

            # Update cache
            self._history_cache[campaign_id] = messages
            self._cache_timestamp[campaign_id] = __import__('time').time()

            logger.debug(f"📝 Appended message to {campaign_id}, total: {len(messages)}")
            return True

        except Exception as e:
            logger.error(f"❌ Error appending message to {campaign_id}: {e}")
            return False

    def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            True if deleted successfully
        """
        try:
            campaign_dir = self._find_campaign_dir(campaign_id)
            if campaign_dir and campaign_dir.exists():
                # Remove the entire directory
                shutil.rmtree(campaign_dir)
                logger.info(f"🗑️ Deleted campaign {campaign_id}")
                return True
            
            logger.warning(f"⚠️ Campaign {campaign_id} not found for deletion")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error deleting campaign {campaign_id}: {e}")
            return False
    
    def rename_campaign(self, campaign_id: str, new_name: str) -> bool:
        """Rename a campaign.
        
        Args:
            campaign_id: Campaign identifier
            new_name: New name for the campaign
            
        Returns:
            True if renamed successfully
        """
        try:
            campaign_dir = self._find_campaign_dir(campaign_id)
            if not campaign_dir:
                logger.warning(f"⚠️ Campaign {campaign_id} not found for renaming")
                return False

            if campaign_dir.parent == self.storage.base_path:
                # New layout: update metadata instead of renaming directory
                now_iso = datetime.now().isoformat()
                self._update_metadata(
                    campaign_id,
                    {
                        "title": new_name,
                        "name": new_name,
                        "updated_at": now_iso,
                    },
                )
                logger.info("🏷️ Updated campaign metadata title for %s", campaign_id)
                return True

            # Legacy layout keeps directory names with suffix.
            safe_name = re.sub(r"[^\w\s-]", "", new_name)
            safe_name = re.sub(r"[-\s]+", " ", safe_name).strip()
            new_dir = campaign_dir.parent / f"{campaign_id} - {safe_name}"
            if new_dir == campaign_dir:
                return True

            campaign_dir.rename(new_dir)
            logger.info("🏷️ Renamed legacy campaign directory to: %s", new_dir.name)
            return True
            
        except Exception as e:
            logger.error(f"❌ Error renaming campaign {campaign_id}: {e}")
            return False
    
    def get_campaign_info(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Campaign info dict or None if not found
        """
        campaigns_result = self.list_campaigns()
        campaigns = campaigns_result["campaigns"]
        for campaign in campaigns:
            if campaign['id'] == campaign_id:
                return campaign
        return None
    
    def get_campaign_data_path(self, campaign_id: str) -> Optional[Path]:
        """Get the data directory path for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Path to campaign data directory or None if campaign doesn't exist
        """
        try:
            return self.storage.ensure_subdir(campaign_id, "data")
        except FileNotFoundError:
            return None
    
    def get_campaign_characters_path(self, campaign_id: str) -> Optional[Path]:
        """Get the characters directory path for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Path to campaign characters directory or None if campaign doesn't exist
        """
        try:
            return self.storage.ensure_subdir(campaign_id, "data/characters")
        except FileNotFoundError:
            return None
    
    # Turn management methods
    def save_turn(self, campaign_id: str, turn_data: Dict[str, Any]) -> bool:
        """Save a turn to the campaign's turn history.
        
        Args:
            campaign_id: Campaign identifier
            turn_data: Turn data dictionary (should include turn_id)
            
        Returns:
            True if saved successfully
        """
        try:
            turns_dir = self.storage.ensure_turns_dir(campaign_id)
            
            # Get turn_id from data
            turn_id = turn_data.get("turn_id")
            if not turn_id:
                logger.error("❌ Turn data missing turn_id")
                return False
            
            # Save turn to individual file
            turn_file = turns_dir / f"{turn_id}.json"
            with open(turn_file, 'w', encoding='utf-8') as f:
                json.dump(turn_data, f, indent=2, ensure_ascii=False)
            if self._store:
                try:
                    self._store.write_json(turn_data, campaign_id, f"data/turns/{turn_id}.json")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Turn store mirror failed for %s/%s: %s", campaign_id, turn_id, exc)
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving turn for campaign {campaign_id}: {e}")
            return False
    
    def load_turn(self, campaign_id: str, turn_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific turn from campaign history.
        
        Args:
            campaign_id: Campaign identifier
            turn_id: Turn identifier
            
        Returns:
            Turn data dictionary or None if not found
        """
        try:
            campaign_dir = self.storage.resolve_session_dir(campaign_id)
            if campaign_dir:
                turn_file = campaign_dir / "data" / "turns" / f"{turn_id}.json"
                if turn_file.exists():
                    with open(turn_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            # Object store fallback via unified store
            payload = self._store.read_json(campaign_id, f"data/turns/{turn_id}.json")
            if isinstance(payload, dict):
                return payload
                
        except Exception as e:
            logger.error(f"❌ Error loading turn {turn_id} for campaign {campaign_id}: {e}")
            return None
    
    def load_campaign_turns(self, campaign_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load all turns for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            limit: Optional limit on number of turns to load (most recent)
            
        Returns:
            List of turn data dictionaries, sorted by turn_number
        """
        try:
            turns: List[Dict[str, Any]] = []
            campaign_dir = self.storage.resolve_session_dir(campaign_id)
            if campaign_dir:
                turns_dir = campaign_dir / "data" / "turns"
                if turns_dir.exists():
                    for turn_file in turns_dir.glob("*.json"):
                        try:
                            with open(turn_file, 'r', encoding='utf-8') as f:
                                turn_data = json.load(f)
                                turns.append(turn_data)
                        except Exception as e:
                            logger.warning(f"⚠️ Error loading turn file {turn_file}: {e}")
            elif True:
                # Listing via unified store
                files = self._store.list_json_prefix(campaign_id, "data/turns")
                for base in files:
                    try:
                        payload = self._store.read_json(campaign_id, f"data/turns/{base}")
                        if isinstance(payload, dict):
                            turns.append(payload)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("⚠️ Error reading turn %s from GCS: %s", base, exc)
            
            # Sort by turn_number
            turns.sort(key=lambda x: x.get("turn_number", 0))
            
            # Apply limit if specified
            if limit and limit > 0:
                turns = turns[-limit:]
            
            return turns
            
        except Exception as e:
            logger.error(f"❌ Error loading turns for campaign {campaign_id}: {e}")
            return []
    
    def get_next_turn_number(self, campaign_id: str) -> int:
        """Get the next turn number for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Next turn number (1 if no turns exist)
        """
        try:
            turns = self.load_campaign_turns(campaign_id)
            if not turns:
                return 1
            
            # Get the highest turn number and add 1
            max_turn = max(turn.get("turn_number", 0) for turn in turns)
            return max_turn + 1
            
        except Exception as e:
            logger.error(f"❌ Error getting next turn number for campaign {campaign_id}: {e}")
            return 1
    
    def get_current_turn(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get the current (most recent) turn for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Current turn data or None if no turns exist
        """
        turns = self.load_campaign_turns(campaign_id, limit=1)
        return turns[0] if turns else None
