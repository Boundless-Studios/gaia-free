"""Repository layer for scene database operations.

Provides a clean interface for CRUD operations on scenes,
abstracting database implementation details from the business logic.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.src.connection import db_manager
from gaia.models.scene_info import SceneInfo
from gaia.models.scene_db import Scene
from gaia.models.scene_entity_db import SceneEntity

logger = logging.getLogger(__name__)


class SceneRepository:
    """Repository for scene database operations.

    Handles conversion between SceneInfo dataclasses and database models,
    manages transactions, and provides query methods.
    """

    def __init__(self):
        """Initialize repository with database manager."""
        self.db_manager = db_manager

    async def create_scene(
        self, scene_info: SceneInfo, campaign_id: uuid.UUID
    ) -> str:
        """Create a new scene in the database.

        Args:
            scene_info: SceneInfo dataclass containing scene data
            campaign_id: UUID of the campaign this scene belongs to

        Returns:
            scene_id of the created scene

        Raises:
            ValueError: If scene with this ID already exists
            Exception: For database errors
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Check if scene already exists
                existing = await session.get(Scene, scene_info.scene_id)
                if existing and not existing.is_deleted:
                    raise ValueError(
                        f"Scene {scene_info.scene_id} already exists for campaign {campaign_id}"
                    )

                # Convert SceneInfo to Scene model
                scene = Scene.from_scene_info(scene_info, campaign_id)

                # Create SceneEntity records for all participants
                for participant in scene_info.participants:
                    entity = SceneEntity.from_scene_participant(
                        scene_info.scene_id, participant
                    )
                    scene.entities.append(entity)

                # Add and commit
                session.add(scene)
                await session.commit()

                logger.info(
                    f"Created scene {scene_info.scene_id} for campaign {campaign_id} "
                    f"with {len(scene.entities)} entities"
                )
                return scene_info.scene_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating scene {scene_info.scene_id}: {e}")
            raise

    async def get_scene(self, scene_id: str) -> Optional[SceneInfo]:
        """Get a scene by ID.

        Args:
            scene_id: Unique scene identifier

        Returns:
            SceneInfo if found and not deleted, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Load scene with entities
                stmt = (
                    select(Scene)
                    .where(and_(Scene.scene_id == scene_id, Scene.is_deleted == False))
                    .options(selectinload(Scene.entities))
                )
                result = await session.execute(stmt)
                scene = result.scalar_one_or_none()

                if not scene:
                    return None

                # Convert to SceneInfo
                return scene.to_scene_info()

        except Exception as e:
            logger.error(f"Error retrieving scene {scene_id}: {e}")
            raise

    async def update_scene(
        self, scene_id: str, updates: dict
    ) -> bool:
        """Update mutable fields of a scene.

        Only allows updating fields that are designed to change during play.
        Immutable creation fields cannot be updated.

        Args:
            scene_id: Scene to update
            updates: Dictionary of fields to update

        Returns:
            True if updated successfully, False if scene not found

        Raises:
            ValueError: If trying to update immutable fields
        """
        # Define mutable fields (can be updated)
        mutable_fields = {
            "outcomes",
            "npcs_added",
            "npcs_removed",
            "duration_turns",
            "turn_order",
            "current_turn_index",
            "in_combat",
            "combat_data",
            "scene_metadata",
            "last_updated",
        }

        # Check for attempts to update immutable fields
        immutable_attempts = set(updates.keys()) - mutable_fields
        if immutable_attempts:
            raise ValueError(
                f"Cannot update immutable fields: {immutable_attempts}. "
                f"Only these fields can be updated: {mutable_fields}"
            )

        try:
            async with self.db_manager.get_async_session() as session:
                # Load scene
                scene = await session.get(Scene, scene_id)
                if not scene or scene.is_deleted:
                    logger.warning(f"Scene {scene_id} not found or deleted")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(scene, field):
                        setattr(scene, field, value)

                # Update timestamp
                scene.last_updated = datetime.now(timezone.utc)

                await session.commit()
                logger.info(f"Updated scene {scene_id} with fields: {list(updates.keys())}")
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating scene {scene_id}: {e}")
            raise

    async def get_recent_scenes(
        self, campaign_id: uuid.UUID, limit: int = 5
    ) -> List[SceneInfo]:
        """Get recent scenes for a campaign.

        Args:
            campaign_id: Campaign UUID
            limit: Maximum number of scenes to return

        Returns:
            List of SceneInfo, ordered by scene_timestamp descending
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(Scene)
                    .where(
                        and_(
                            Scene.campaign_id == campaign_id,
                            Scene.is_deleted == False,
                        )
                    )
                    .order_by(Scene.scene_timestamp.desc())
                    .limit(limit)
                    .options(selectinload(Scene.entities))
                )

                result = await session.execute(stmt)
                scenes = result.scalars().all()

                return [scene.to_scene_info() for scene in scenes]

        except Exception as e:
            logger.error(f"Error getting recent scenes for campaign {campaign_id}: {e}")
            raise

    async def add_entity_to_scene(
        self,
        scene_id: str,
        entity_id: str,
        entity_type: str,
        role: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Add an entity to a scene.

        Args:
            scene_id: Scene to add entity to
            entity_id: Entity identifier
            entity_type: Type of entity (character, item, quest, etc.)
            role: Optional role (for characters)
            metadata: Optional metadata dict

        Returns:
            True if added successfully, False if scene not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Verify scene exists
                scene = await session.get(Scene, scene_id)
                if not scene or scene.is_deleted:
                    logger.warning(f"Scene {scene_id} not found or deleted")
                    return False

                # Check if entity already exists
                stmt = select(SceneEntity).where(
                    and_(
                        SceneEntity.scene_id == scene_id,
                        SceneEntity.entity_id == entity_id,
                        SceneEntity.entity_type == entity_type,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing entity to mark as present
                    existing.restore()
                    logger.info(f"Restored entity {entity_id} to scene {scene_id}")
                else:
                    # Create new entity association
                    entity = SceneEntity(
                        scene_id=scene_id,
                        entity_id=entity_id,
                        entity_type=entity_type,
                        role=role,
                        is_present=True,
                        entity_metadata=metadata or {},
                    )
                    session.add(entity)
                    logger.info(f"Added entity {entity_id} ({entity_type}) to scene {scene_id}")

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding entity {entity_id} to scene {scene_id}: {e}")
            raise

    async def remove_entity_from_scene(
        self, scene_id: str, entity_id: str
    ) -> bool:
        """Remove an entity from a scene (marks as not present).

        Args:
            scene_id: Scene to remove entity from
            entity_id: Entity identifier

        Returns:
            True if removed successfully, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(SceneEntity).where(
                    and_(
                        SceneEntity.scene_id == scene_id,
                        SceneEntity.entity_id == entity_id,
                    )
                )
                result = await session.execute(stmt)
                entity = result.scalar_one_or_none()

                if not entity:
                    logger.warning(
                        f"Entity {entity_id} not found in scene {scene_id}"
                    )
                    return False

                entity.mark_departed()
                await session.commit()
                logger.info(f"Removed entity {entity_id} from scene {scene_id}")
                return True

        except Exception as e:
            logger.error(f"Error removing entity {entity_id} from scene {scene_id}: {e}")
            raise

    async def soft_delete_scene(self, scene_id: str) -> bool:
        """Soft delete a scene.

        Args:
            scene_id: Scene to delete

        Returns:
            True if deleted successfully, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                scene = await session.get(Scene, scene_id)
                if not scene:
                    logger.warning(f"Scene {scene_id} not found")
                    return False

                scene.soft_delete()
                await session.commit()
                logger.info(f"Soft deleted scene {scene_id}")
                return True

        except Exception as e:
            logger.error(f"Error soft deleting scene {scene_id}: {e}")
            raise

    async def get_entities_in_scene(
        self,
        scene_id: str,
        entity_type: Optional[str] = None,
        present_only: bool = True,
    ) -> List[SceneEntity]:
        """Get entities in a scene, optionally filtered.

        Args:
            scene_id: Scene to query
            entity_type: Optional filter by entity type
            present_only: Only return currently present entities

        Returns:
            List of SceneEntity records
        """
        try:
            async with self.db_manager.get_async_session() as session:
                conditions = [SceneEntity.scene_id == scene_id]

                if entity_type:
                    conditions.append(SceneEntity.entity_type == entity_type)

                if present_only:
                    conditions.append(SceneEntity.is_present == True)

                stmt = select(SceneEntity).where(and_(*conditions))
                result = await session.execute(stmt)
                return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Error getting entities for scene {scene_id}: {e}")
            raise

    # ========== Synchronous methods for use from sync contexts ==========

    def create_scene_sync(
        self, scene_info: SceneInfo, campaign_id: uuid.UUID
    ) -> str:
        """Synchronous version of create_scene for use from sync contexts."""
        try:
            with self.db_manager.get_sync_session() as session:
                # Check if scene already exists
                existing = session.get(Scene, scene_info.scene_id)
                if existing and not existing.is_deleted:
                    raise ValueError(
                        f"Scene {scene_info.scene_id} already exists for campaign {campaign_id}"
                    )

                # Convert SceneInfo to Scene model
                scene = Scene.from_scene_info(scene_info, campaign_id)

                # Create SceneEntity records for all participants
                for participant in scene_info.participants:
                    entity = SceneEntity.from_scene_participant(
                        scene_info.scene_id, participant
                    )
                    scene.entities.append(entity)

                # Add and commit
                session.add(scene)
                session.commit()

                logger.info(
                    f"Created scene {scene_info.scene_id} for campaign {campaign_id} "
                    f"with {len(scene.entities)} entities (sync)"
                )
                return scene_info.scene_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating scene {scene_info.scene_id} (sync): {e}")
            raise

    def get_scene_sync(self, scene_id: str) -> Optional[SceneInfo]:
        """Synchronous version of get_scene for use from sync contexts."""
        try:
            with self.db_manager.get_sync_session() as session:
                # Load scene with entities
                stmt = (
                    select(Scene)
                    .where(and_(Scene.scene_id == scene_id, Scene.is_deleted == False))
                    .options(selectinload(Scene.entities))
                )
                result = session.execute(stmt)
                scene = result.scalar_one_or_none()

                if not scene:
                    return None

                # Convert to SceneInfo
                return scene.to_scene_info()

        except Exception as e:
            logger.error(f"Error retrieving scene {scene_id} (sync): {e}")
            raise

    def update_scene_sync(self, scene_id: str, updates: dict) -> bool:
        """Synchronous version of update_scene for use from sync contexts."""
        # Define mutable fields (can be updated)
        mutable_fields = {
            "outcomes",
            "npcs_added",
            "npcs_removed",
            "duration_turns",
            "turn_order",
            "current_turn_index",
            "in_combat",
            "combat_data",
            "scene_metadata",
            "last_updated",
        }

        # Check for attempts to update immutable fields
        immutable_attempts = set(updates.keys()) - mutable_fields
        if immutable_attempts:
            raise ValueError(
                f"Cannot update immutable fields: {immutable_attempts}. "
                f"Only these fields can be updated: {mutable_fields}"
            )

        try:
            with self.db_manager.get_sync_session() as session:
                # Load scene
                scene = session.get(Scene, scene_id)
                if not scene or scene.is_deleted:
                    logger.warning(f"Scene {scene_id} not found or deleted (sync)")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(scene, field):
                        setattr(scene, field, value)

                # Update timestamp
                scene.last_updated = datetime.now(timezone.utc)

                session.commit()
                logger.info(f"Updated scene {scene_id} with fields: {list(updates.keys())} (sync)")
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating scene {scene_id} (sync): {e}")
            raise

    def get_recent_scenes_sync(
        self, campaign_id: uuid.UUID, limit: int = 5
    ) -> List[SceneInfo]:
        """Synchronous version of get_recent_scenes."""
        try:
            with self.db_manager.get_sync_session() as session:
                stmt = (
                    select(Scene)
                    .where(
                        and_(
                            Scene.campaign_id == campaign_id,
                            Scene.is_deleted == False,
                        )
                    )
                    .order_by(Scene.scene_timestamp.desc())
                    .limit(limit)
                    .options(selectinload(Scene.entities))
                )

                result = session.execute(stmt)
                scenes = result.scalars().all()

                return [scene.to_scene_info() for scene in scenes]

        except Exception as e:
            logger.error(f"Error getting recent scenes for campaign {campaign_id} (sync): {e}")
            raise

    def add_participant_sync(
        self,
        scene_id: str,
        character_id: str,
        display_name: str,
        role: str = "dm_controlled_npc",
        is_original: bool = False,
    ) -> bool:
        """Add a participant (character) to a scene by creating a SceneEntity record.

        This is the proper way to add NPCs/PCs to a scene when using database storage.
        The npcs_present/npcs_added lists are computed dynamically from SceneEntity records.

        Args:
            scene_id: Scene identifier
            character_id: Character identifier (e.g., "npc:bartender")
            display_name: Display name for the character
            role: Character role (e.g., "player", "dm_controlled_npc", "enemy")
            is_original: Whether character was present at scene creation

        Returns:
            True if successful, False if scene not found
        """
        try:
            with self.db_manager.get_sync_session() as session:
                # Load scene
                scene = session.get(Scene, scene_id)
                if not scene or scene.is_deleted:
                    logger.warning(f"Scene {scene_id} not found or deleted (sync)")
                    return False

                # Check if entity already exists
                existing = session.execute(
                    select(SceneEntity).where(
                        and_(
                            SceneEntity.scene_id == scene_id,
                            SceneEntity.entity_id == character_id,
                            SceneEntity.entity_type == "character",
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing entity
                    existing.is_present = True
                    existing.left_at = None
                    existing.role = role
                    existing.entity_metadata = {
                        **(existing.entity_metadata or {}),
                        "display_name": display_name,
                    }
                    logger.info(f"Updated existing participant {character_id} in scene {scene_id}")
                else:
                    # Create new entity
                    entity = SceneEntity(
                        scene_id=scene_id,
                        entity_id=character_id,
                        entity_type="character",
                        is_present=True,
                        role=role,
                        entity_metadata={
                            "is_original": is_original,
                            "display_name": display_name,
                        },
                    )
                    session.add(entity)
                    logger.info(f"Added participant {character_id} to scene {scene_id}")

                scene.last_updated = datetime.now(timezone.utc)
                session.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding participant {character_id} to scene {scene_id} (sync): {e}")
            raise
