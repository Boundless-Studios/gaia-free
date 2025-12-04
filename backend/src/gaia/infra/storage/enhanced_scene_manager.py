"""Enhanced scene manager for storing and retrieving SceneInfo objects.

Supports dual storage backends:
- filesystem: Legacy JSON file storage (for backwards compatibility)
- database: PostgreSQL via SceneRepository (preferred for new campaigns)

Storage mode is determined by campaign's scene_storage_mode setting.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from gaia.models.scene_info import SceneInfo
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.infra.storage.scene_repository import SceneRepository

logger = logging.getLogger(__name__)


class EnhancedSceneManager:
    """Manager for storing and retrieving SceneInfo objects with proper persistence.

    Supports dual storage backends controlled by campaign's scene_storage_mode:
    - "filesystem": Legacy JSON file storage (default for existing campaigns)
    - "database": PostgreSQL via SceneRepository (default for new campaigns)
    """

    def __init__(self, campaign_id: str = "default"):
        """Initialize the enhanced scene manager.

        Args:
            campaign_id: Campaign identifier
        """
        self.campaign_id = campaign_id
        self.environment_name = os.getenv('ENVIRONMENT_NAME', 'default')

        # Resolve canonical campaign data path via campaign manager
        self._campaign_manager = SimpleCampaignManager()
        self._campaign_data = None
        self._campaign_uuid: Optional[uuid.UUID] = None

        # Try to load campaign data to determine storage mode
        try:
            self._campaign_data = self._campaign_manager.load_campaign(campaign_id)
            if self._campaign_data:
                # Try to get campaign UUID from database
                campaign_uuid_str = self._campaign_data.custom_data.get("campaign_uuid")
                if campaign_uuid_str:
                    self._campaign_uuid = uuid.UUID(campaign_uuid_str)
        except Exception as e:
            logger.debug(f"Could not load campaign data: {e}")

        # Determine storage mode
        if self._campaign_data:
            self._storage_mode = self._campaign_data.get_scene_storage_mode()
        else:
            # No campaign data means legacy campaign, use filesystem
            self._storage_mode = "filesystem"

        # Initialize database repository if using database mode
        self._repository: Optional[SceneRepository] = None
        if self._storage_mode == "database":
            self._repository = SceneRepository()
            logger.info(f"🎭 Using database storage for campaign: {campaign_id}")

        # Always set up filesystem path for fallback and legacy support
        data_path = self._campaign_manager.get_campaign_data_path(campaign_id)

        if data_path is None:
            # Fallback to legacy path if campaign not registered yet
            campaign_storage = os.getenv('CAMPAIGN_STORAGE_PATH')
            if not campaign_storage:
                raise ValueError(
                    "CAMPAIGN_STORAGE_PATH environment variable is not set. "
                    "Please set it to your campaign storage directory."
                )

            base_path = os.path.join(campaign_storage, 'campaigns', self.environment_name, campaign_id)
            data_path = os.path.join(base_path, 'data')
        else:
            data_path = str(data_path)

        self.scenes_dir = os.path.join(data_path, 'scenes')

        # Ensure directory exists for filesystem storage
        if self._storage_mode == "filesystem":
            os.makedirs(self.scenes_dir, exist_ok=True)

        # Cache for recently accessed scenes
        self._scene_cache: Dict[str, SceneInfo] = {}

        logger.info(f"🎭 Enhanced Scene Manager initialized for campaign: {campaign_id} (storage: {self._storage_mode})")

    def _run_async(self, coro):
        """Run an async coroutine from sync context.

        Args:
            coro: Async coroutine to run

        Returns:
            Result of the coroutine
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            # No running loop, we can use asyncio.run
            return asyncio.run(coro)

    def create_scene(self, scene_info: SceneInfo) -> str:
        """Create and store a new scene. This should only be used for new scenes.

        Args:
            scene_info: SceneInfo object to create

        Returns:
            The scene_id of the created scene

        Raises:
            ValueError: If scene already exists
        """
        # Ensure scene has an ID
        if not scene_info.scene_id:
            scene_info.scene_id = self._generate_scene_id()

        # Use database storage if configured
        if self._storage_mode == "database" and self._repository and self._campaign_uuid:
            try:
                scene_id = self._run_async(
                    self._repository.create_scene(scene_info, self._campaign_uuid)
                )
                self._scene_cache[scene_info.scene_id] = scene_info
                logger.info(f"Created scene {scene_id} in database")
                return scene_id
            except ValueError:
                raise
            except Exception as e:
                logger.error(f"Database create failed, falling back to filesystem: {e}")
                # Fall through to filesystem storage

        # Filesystem storage (legacy or fallback)
        return self._create_scene_filesystem(scene_info)

    def _create_scene_filesystem(self, scene_info: SceneInfo) -> str:
        """Create scene using filesystem storage.

        Args:
            scene_info: SceneInfo object to create

        Returns:
            The scene_id of the created scene

        Raises:
            ValueError: If scene already exists
        """
        # Ensure directory exists
        os.makedirs(self.scenes_dir, exist_ok=True)

        # Check if scene already exists
        existing_path = os.path.join(self.scenes_dir, f"{scene_info.scene_id}.json")
        if os.path.exists(existing_path):
            raise ValueError(f"Scene {scene_info.scene_id} already exists. Use update_scene for modifications.")

        # Convert to dict for storage
        scene_data = scene_info.to_dict()

        # Add metadata
        scene_data["_metadata"] = {
            "version": "1.0",
            "stored_at": datetime.now().isoformat(),
            "campaign_id": self.campaign_id
        }

        # Store to file
        filepath = os.path.join(self.scenes_dir, f"{scene_info.scene_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(scene_data, f, indent=2, ensure_ascii=False)

        # Update cache
        self._scene_cache[scene_info.scene_id] = scene_info

        return scene_info.scene_id

    def update_scene(self, scene_id: str, updates: Dict[str, Any]) -> bool:
        """Update only the mutable fields of an existing scene.

        Args:
            scene_id: Scene identifier
            updates: Dictionary of fields to update

        Returns:
            True if successful, False otherwise

        Note:
            Only the following fields can be updated:
            - outcomes, objectives_completed, objectives_added
            - npcs_added, npcs_removed, description_updates
            - completion_status, duration_turns, last_updated
            - npcs_present (snapshot), in_combat (bool), combat_data (dict)
        """
        # Define allowed update fields
        allowed_fields = {
            'outcomes', 'objectives_completed', 'objectives_added',
            'npcs_added', 'npcs_removed', 'description_updates',
            'completion_status', 'duration_turns', 'npcs_present',
            'in_combat', 'combat_data', 'turn_order', 'current_turn_index',
            'npc_display_names', 'entity_display_names'
        }

        # Filter updates to only allowed fields
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            logger.warning(f"No valid update fields provided for scene {scene_id}")
            return False

        # Try database update first if configured
        if self._storage_mode == "database" and self._repository:
            try:
                # Map npc_display_names to entity_display_names for database
                db_updates = dict(filtered_updates)
                if 'npc_display_names' in db_updates:
                    entity_names = db_updates.pop('npc_display_names')
                    db_updates['entity_display_names'] = entity_names

                result = self._run_async(
                    self._repository.update_scene(scene_id, db_updates)
                )
                if result:
                    # Invalidate cache
                    self._scene_cache.pop(scene_id, None)
                    logger.info(f"Updated scene {scene_id} in database")
                    return True
                # Scene not found in DB, try filesystem
            except ValueError:
                raise
            except Exception as e:
                logger.error(f"Database update failed, trying filesystem: {e}")

        # Filesystem update (legacy or fallback)
        return self._update_scene_filesystem(scene_id, filtered_updates)

    def _update_scene_filesystem(self, scene_id: str, filtered_updates: Dict[str, Any]) -> bool:
        """Update scene using filesystem storage.

        Args:
            scene_id: Scene identifier
            filtered_updates: Pre-filtered dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        # Get existing scene
        scene = self.get_scene(scene_id)
        if not scene:
            logger.warning(f"Cannot update - scene not found: {scene_id}")
            return False

        # Apply updates
        for field, value in filtered_updates.items():
            if hasattr(scene, field):
                if field in ['outcomes', 'objectives_completed', 'objectives_added',
                           'npcs_added', 'npcs_removed', 'description_updates']:
                    # For list fields, extend rather than replace
                    current_list = getattr(scene, field)
                    if isinstance(value, list):
                        current_list.extend(value)
                    else:
                        current_list.append(value)
                elif field == 'npc_display_names':
                    if scene.metadata is None:
                        scene.metadata = {}
                    existing_map = scene.metadata.setdefault('npc_display_names', {})
                    if isinstance(existing_map, dict) and isinstance(value, dict):
                        existing_map.update(value)
                    elif isinstance(value, dict):
                        scene.metadata['npc_display_names'] = dict(value)
                elif field in ['npcs_present', 'in_combat', 'combat_data', 'completion_status',
                             'duration_turns', 'turn_order', 'current_turn_index', 'entity_display_names']:
                    # Replace snapshot/flags directly
                    setattr(scene, field, value)
                else:
                    # Default: replace value
                    setattr(scene, field, value)

        # Update last_updated timestamp
        scene.last_updated = datetime.now()

        # Store the updated scene
        self._store_scene_internal(scene)

        return True

    def _store_scene_internal(self, scene_info: SceneInfo) -> None:
        """Internal method to store a scene without creation checks.

        Args:
            scene_info: SceneInfo object to store
        """
        # Convert to dict for storage
        scene_data = scene_info.to_dict()

        # Add metadata
        scene_data["_metadata"] = {
            "version": "1.0",
            "stored_at": datetime.now().isoformat(),
            "campaign_id": self.campaign_id
        }

        # Store to file
        filepath = os.path.join(self.scenes_dir, f"{scene_info.scene_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(scene_data, f, indent=2, ensure_ascii=False)

        # Update cache
        self._scene_cache[scene_info.scene_id] = scene_info

    def get_scene(self, scene_id: str) -> Optional[SceneInfo]:
        """Retrieve a specific scene by ID.

        Args:
            scene_id: Scene identifier

        Returns:
            SceneInfo object or None if not found
        """
        # Check cache first
        if scene_id in self._scene_cache:
            return self._scene_cache[scene_id]

        # Try database first if configured
        if self._storage_mode == "database" and self._repository:
            try:
                scene_info = self._run_async(
                    self._repository.get_scene(scene_id)
                )
                if scene_info:
                    self._scene_cache[scene_id] = scene_info
                    return scene_info
                # Not found in DB, try filesystem as fallback
            except Exception as e:
                logger.debug(f"Database get failed, trying filesystem: {e}")

        # Filesystem fallback
        return self._get_scene_filesystem(scene_id)

    def _get_scene_filesystem(self, scene_id: str) -> Optional[SceneInfo]:
        """Retrieve scene from filesystem storage.

        Args:
            scene_id: Scene identifier

        Returns:
            SceneInfo object or None if not found
        """
        filepath = os.path.join(self.scenes_dir, f"{scene_id}.json")

        if not os.path.exists(filepath):
            logger.warning(f"Scene not found: {scene_id}")
            return None

        try:
            with open(filepath, 'r') as f:
                scene_data = json.load(f)

            # Remove metadata before creating SceneInfo
            scene_data.pop("_metadata", None)

            # Create SceneInfo object
            scene_info = SceneInfo.from_dict(scene_data)

            # Update cache
            self._scene_cache[scene_id] = scene_info

            return scene_info

        except Exception as e:
            logger.error(f"Error loading scene {scene_id}: {e}")
            return None

    def get_recent_scenes(self, limit: int = 5) -> List[SceneInfo]:
        """Get the most recent scenes.

        Args:
            limit: Maximum number of scenes to return

        Returns:
            List of SceneInfo objects, most recent first
        """
        # Try database first if configured
        if self._storage_mode == "database" and self._repository and self._campaign_uuid:
            try:
                scenes = self._run_async(
                    self._repository.get_recent_scenes(self._campaign_uuid, limit)
                )
                if scenes:
                    return scenes
                # Empty result, try filesystem as fallback
            except Exception as e:
                logger.debug(f"Database get_recent_scenes failed, trying filesystem: {e}")

        # Filesystem fallback
        return self._get_recent_scenes_filesystem(limit)

    def _get_recent_scenes_filesystem(self, limit: int = 5) -> List[SceneInfo]:
        """Get recent scenes from filesystem storage.

        Args:
            limit: Maximum number of scenes to return

        Returns:
            List of SceneInfo objects, most recent first
        """
        scenes = []

        try:
            if not os.path.exists(self.scenes_dir):
                return []

            # Load all scenes
            for filename in os.listdir(self.scenes_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.scenes_dir, filename)

                    try:
                        with open(filepath, 'r') as f:
                            scene_data = json.load(f)

                        # Remove metadata
                        scene_data.pop("_metadata", None)

                        # Create SceneInfo object
                        scene_info = SceneInfo.from_dict(scene_data)
                        scenes.append(scene_info)

                    except Exception as e:
                        logger.warning(f"Error loading scene from {filepath}: {e}")
                        continue

            # Sort by timestamp (most recent first) - use scene_id as tiebreaker
            scenes.sort(key=lambda x: (x.timestamp, x.scene_id), reverse=True)

            # Return limited number of scenes
            return scenes[:limit]

        except Exception as e:
            logger.error(f"Error retrieving recent scenes: {e}")
            return []

    def get_scenes_by_location(self, location_id: str, limit: int = 10) -> List[SceneInfo]:
        """Get all scenes that occurred at a specific location.

        Args:
            location_id: Location identifier
            limit: Maximum number of scenes to return

        Returns:
            List of SceneInfo objects at the specified location
        """
        # Try database first if configured
        if self._storage_mode == "database" and self._repository and self._campaign_uuid:
            try:
                scenes = self._run_async(
                    self._repository.get_scenes_by_location(
                        self._campaign_uuid, location_id, limit
                    )
                )
                if scenes:
                    return scenes
                # Empty result, try filesystem as fallback
            except Exception as e:
                logger.debug(f"Database get_scenes_by_location failed, trying filesystem: {e}")

        # Filesystem fallback
        return self._get_scenes_by_location_filesystem(location_id, limit)

    def _get_scenes_by_location_filesystem(
        self, location_id: str, limit: int = 10
    ) -> List[SceneInfo]:
        """Get scenes by location from filesystem storage.

        Args:
            location_id: Location identifier
            limit: Maximum number of scenes to return

        Returns:
            List of SceneInfo objects at the specified location
        """
        matching_scenes = []

        try:
            if not os.path.exists(self.scenes_dir):
                return []

            for filename in os.listdir(self.scenes_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.scenes_dir, filename)

                    with open(filepath, 'r') as f:
                        scene_data = json.load(f)

                    # Check if location matches
                    if scene_data.get("location_id") == location_id:
                        scene_data.pop("_metadata", None)
                        scene_info = SceneInfo.from_dict(scene_data)
                        matching_scenes.append(scene_info)

                        if len(matching_scenes) >= limit:
                            break

            # Sort by timestamp (most recent first)
            matching_scenes.sort(key=lambda x: x.timestamp, reverse=True)

            return matching_scenes

        except Exception as e:
            logger.error(f"Error retrieving scenes by location: {e}")
            return []

    def get_scene_context_for_agents(self, num_scenes: int = 3) -> str:
        """Get formatted scene context for agent consumption.

        Args:
            num_scenes: Number of recent scenes to include

        Returns:
            Formatted string with scene context
        """
        recent_scenes = self.get_recent_scenes(num_scenes)

        if not recent_scenes:
            return "No previous scenes available."

        context_parts = ["**Recent Scene Context:**\n"]

        for i, scene in enumerate(recent_scenes, 1):
            context_parts.append(f"\n--- Scene {i} ({scene.scene_type}) ---")
            context_parts.append(f"Title: {scene.title}")
            context_parts.append(f"Location: {scene.location_id}")

            if scene.description:
                context_parts.append(f"Description: {scene.description}")

            if scene.objectives:
                context_parts.append(f"Objectives: {', '.join(scene.objectives)}")

            if scene.npcs_involved:
                context_parts.append(f"NPCs: {', '.join(scene.npcs_involved)}")

            if scene.outcomes:
                context_parts.append(f"Outcomes: {', '.join(scene.outcomes)}")

        return "\n".join(context_parts)

    def get_scene_summary(self, scene_id: str) -> Dict[str, Any]:
        """Get a summary of a scene for structured data.

        Args:
            scene_id: Scene identifier

        Returns:
            Dictionary with scene summary
        """
        scene = self.get_scene(scene_id)

        if not scene:
            return {"error": f"Scene {scene_id} not found"}

        # Compute dynamic NPC presence if not explicitly set
        npcs_present = []
        try:
            if hasattr(scene, 'npcs_present') and scene.npcs_present:
                npcs_present = list(dict.fromkeys(scene.npcs_present))
            else:
                base = list(getattr(scene, 'npcs_involved', []) or [])
                added = list(getattr(scene, 'npcs_added', []) or [])
                removed = set(getattr(scene, 'npcs_removed', []) or [])
                merged = [n for n in base + added if n and n not in removed]
                npcs_present = list(dict.fromkeys(merged))
        except Exception:
            # Fallback to involved if any error occurs
            npcs_present = list(getattr(scene, 'npcs_involved', []) or [])

        # Convert participants to dicts for serialization
        participants = getattr(scene, 'participants', [])
        participants_list = []
        participant_display_by_id: Dict[str, str] = {}
        if participants:
            for p in participants:
                if hasattr(p, 'to_dict'):
                    participant_dict = p.to_dict()
                    participants_list.append(participant_dict)
                    char_id = participant_dict.get("character_id")
                    display = participant_dict.get("display_name")
                    if char_id and display:
                        participant_display_by_id[char_id] = display
                elif isinstance(p, dict):
                    participants_list.append(p)
                    char_id = p.get("character_id")
                    display = p.get("display_name") or p.get("name")
                    if char_id and display:
                        participant_display_by_id[char_id] = display

        metadata_display = {}
        if getattr(scene, "metadata", None):
            metadata_display = scene.metadata.get("npc_display_names", {}) or {}

        def friendly_name(identifier: str) -> str:
            if not identifier:
                return "Unknown NPC"
            value = identifier
            lowered = value.lower()
            if lowered.startswith(("npc:", "npc_profile:", "pc:")):
                value = value.split(":", 1)[1]
            cleaned = value.replace("_", " ").strip()
            return cleaned.title() if cleaned else "Unknown NPC"

        npc_display_map: Dict[str, str] = {}
        npcs_display = []
        for npc_id in npcs_present:
            display = participant_display_by_id.get(npc_id) or metadata_display.get(npc_id)
            if not display and isinstance(npc_id, str):
                display = friendly_name(npc_id)
            if display:
                npc_display_map[npc_id] = display
                npcs_display.append(display)

        return {
            "scene_id": scene.scene_id,
            "title": scene.title,
            "scene_type": scene.scene_type,
            "location": scene.location_id,
            "npcs_present": npcs_present,
            "npcs_present_display": npcs_display,
            "npc_display_names": npc_display_map,
            "pcs_present": getattr(scene, 'pcs_present', []),
            "participants": participants_list,
            "objectives": scene.objectives,
            "outcomes": scene.outcomes,
            "in_combat": getattr(scene, 'in_combat', False),
            "combat_data": getattr(scene, 'combat_data', None),
            "timestamp": scene.timestamp.isoformat()
        }

    def update_scene_outcomes(self, scene_id: str, outcomes: List[str]) -> bool:
        """Update the outcomes of an existing scene.

        Args:
            scene_id: Scene identifier
            outcomes: List of outcomes to add

        Returns:
            True if successful, False otherwise
        """
        return self.update_scene(scene_id, {'outcomes': outcomes})

    def _generate_scene_id(self) -> str:
        """Generate a unique scene ID.

        Returns:
            Unique scene identifier
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Count existing scenes for numbering
        try:
            existing_count = len([f for f in os.listdir(self.scenes_dir) if f.endswith('.json')])
        except:
            existing_count = 0

        scene_number = existing_count + 1

        return f"scene_{scene_number:03d}_{timestamp}"

    @property
    def storage_mode(self) -> str:
        """Get the current storage mode.

        Returns:
            "database" or "filesystem"
        """
        return self._storage_mode

    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the current storage configuration.

        Returns:
            Dictionary with storage mode, backend availability, and paths
        """
        return {
            "storage_mode": self._storage_mode,
            "campaign_id": self.campaign_id,
            "campaign_uuid": str(self._campaign_uuid) if self._campaign_uuid else None,
            "database_available": self._repository is not None,
            "filesystem_path": self.scenes_dir,
            "filesystem_exists": os.path.exists(self.scenes_dir),
        }
