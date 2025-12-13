"""Repository layer for character database operations.

Provides clean interface for CRUD operations on characters, profiles, NPCs,
and user associations, abstracting database implementation details.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.src.connection import db_manager
from gaia.models.character.character_profile import CharacterProfile as CharacterProfileDataclass
from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.npc_profile import NpcProfile as NpcProfileDataclass
from gaia.models.character_db import CharacterProfile
from gaia.models.character_instance_db import CharacterCampaignInstance
from gaia.models.npc_profile_db import NpcProfile
from gaia.models.character_user_db import CharacterUser

logger = logging.getLogger(__name__)


class CharacterRepository:
    """Repository for character database operations.

    Handles conversion between dataclasses and database models,
    manages transactions, and provides query methods.
    """

    def __init__(self):
        """Initialize repository with database manager."""
        self.db_manager = db_manager

    # ========== Character Profile Operations (Async) ==========

    async def create_profile(
        self,
        profile: CharacterProfileDataclass,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> uuid.UUID:
        """Create a new character profile.

        Args:
            profile: CharacterProfile dataclass
            user_id: User who owns this character (None for system)
            user_email: Email of owning user

        Returns:
            UUID of created character profile

        Raises:
            ValueError: If character with external_id already exists
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Check if external ID already exists
                stmt = select(CharacterProfile).where(
                    CharacterProfile.external_character_id == profile.character_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing and not existing.is_deleted:
                    raise ValueError(
                        f"Character profile with ID {profile.character_id} already exists"
                    )

                # Create profile from dataclass
                db_profile = CharacterProfile.from_dataclass(
                    profile,
                    created_by_user_id=user_id,
                    created_by_email=user_email,
                )

                session.add(db_profile)

                # Create user association if user_id provided
                if user_id:
                    user_assoc = CharacterUser(
                        character_id=db_profile.character_id,
                        user_id=user_id,
                        user_email=user_email,
                        role="owner",
                    )
                    session.add(user_assoc)

                await session.commit()
                await session.refresh(db_profile)

                logger.info(
                    f"Created character profile {profile.character_id} "
                    f"(UUID: {db_profile.character_id}) for user {user_id or 'system'}"
                )
                return db_profile.character_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating character profile: {e}")
            raise

    async def get_profile(
        self, external_character_id: str
    ) -> Optional[CharacterProfileDataclass]:
        """Get character profile by external ID.

        Args:
            external_character_id: External character ID

        Returns:
            CharacterProfile dataclass if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterProfile).where(
                    and_(
                        CharacterProfile.external_character_id == external_character_id,
                        CharacterProfile.is_deleted == False,
                    )
                )
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile:
                    return None

                return profile.to_dataclass()

        except Exception as e:
            logger.error(f"Error retrieving character profile {external_character_id}: {e}")
            raise

    async def get_profile_by_uuid(self, character_id: uuid.UUID) -> Optional[CharacterProfile]:
        """Get character profile ORM model by UUID.

        Args:
            character_id: Character UUID

        Returns:
            CharacterProfile ORM model if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                profile = await session.get(CharacterProfile, character_id)
                if profile and not profile.is_deleted:
                    return profile
                return None

        except Exception as e:
            logger.error(f"Error retrieving character profile by UUID {character_id}: {e}")
            raise

    async def update_profile(self, external_character_id: str, updates: dict) -> bool:
        """Update mutable fields of a character profile.

        Args:
            external_character_id: Character to update
            updates: Dictionary of fields to update

        Returns:
            True if updated, False if not found
        """
        # Define mutable fields
        mutable_fields = {
            "voice_id",
            "voice_settings",
            "voice_archetype",
            "portrait_url",
            "portrait_path",
            "portrait_prompt",
            "additional_images",
            "gender",
            "age_category",
            "build",
            "height_description",
            "facial_expression",
            "facial_features",
            "attire",
            "primary_weapon",
            "distinguishing_feature",
            "background_setting",
            "pose",
            "backstory",
            "description",
            "appearance",
            "visual_description",
            "personality_traits",
            "bonds",
            "flaws",
            "total_interactions",
        }

        immutable_attempts = set(updates.keys()) - mutable_fields
        if immutable_attempts:
            raise ValueError(
                f"Cannot update immutable fields: {immutable_attempts}. "
                f"Only these fields can be updated: {mutable_fields}"
            )

        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterProfile).where(
                    CharacterProfile.external_character_id == external_character_id
                )
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile or profile.is_deleted:
                    logger.warning(f"Character profile {external_character_id} not found or deleted")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(profile, field):
                        setattr(profile, field, value)

                await session.commit()
                logger.info(f"Updated character profile {external_character_id}")
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating character profile {external_character_id}: {e}")
            raise

    async def list_profiles_by_user(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[CharacterProfileDataclass]:
        """List character profiles owned by a user.

        Args:
            user_id: User ID
            limit: Maximum number of profiles to return
            offset: Number of profiles to skip

        Returns:
            List of CharacterProfile dataclasses
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(CharacterProfile)
                    .join(CharacterUser)
                    .where(
                        and_(
                            CharacterUser.user_id == user_id,
                            CharacterProfile.is_deleted == False,
                        )
                    )
                    .order_by(CharacterProfile.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                profiles = result.scalars().all()

                return [profile.to_dataclass() for profile in profiles]

        except Exception as e:
            logger.error(f"Error listing profiles for user {user_id}: {e}")
            raise

    async def list_system_profiles(
        self, limit: int = 100, offset: int = 0
    ) -> List[CharacterProfileDataclass]:
        """List system-created character profiles.

        Args:
            limit: Maximum number of profiles to return
            offset: Number of profiles to skip

        Returns:
            List of CharacterProfile dataclasses
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(CharacterProfile)
                    .where(
                        and_(
                            CharacterProfile.created_by_user_id == None,
                            CharacterProfile.is_deleted == False,
                        )
                    )
                    .order_by(CharacterProfile.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                profiles = result.scalars().all()

                return [profile.to_dataclass() for profile in profiles]

        except Exception as e:
            logger.error(f"Error listing system profiles: {e}")
            raise

    async def soft_delete_profile(self, external_character_id: str) -> bool:
        """Soft delete a character profile.

        Args:
            external_character_id: Character to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterProfile).where(
                    CharacterProfile.external_character_id == external_character_id
                )
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile:
                    return False

                profile.soft_delete()
                await session.commit()

                logger.info(f"Soft deleted character profile {external_character_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting character profile {external_character_id}: {e}")
            raise

    async def restore_profile(self, external_character_id: str) -> bool:
        """Restore a soft-deleted character profile.

        Args:
            external_character_id: Character to restore

        Returns:
            True if restored, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterProfile).where(
                    CharacterProfile.external_character_id == external_character_id
                )
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile:
                    return False

                profile.restore()
                await session.commit()

                logger.info(f"Restored character profile {external_character_id}")
                return True

        except Exception as e:
            logger.error(f"Error restoring character profile {external_character_id}: {e}")
            raise

    # ========== Campaign Instance Operations (Async) ==========

    async def create_instance(
        self,
        character_info: CharacterInfo,
        character_uuid: uuid.UUID,
        campaign_uuid: uuid.UUID,
    ) -> uuid.UUID:
        """Create a campaign-specific character instance.

        Args:
            character_info: CharacterInfo with campaign state
            character_uuid: UUID of character profile
            campaign_uuid: UUID of campaign

        Returns:
            UUID of created instance

        Raises:
            ValueError: If instance already exists for this character/campaign
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Check for existing instance
                stmt = select(CharacterCampaignInstance).where(
                    and_(
                        CharacterCampaignInstance.character_id == character_uuid,
                        CharacterCampaignInstance.campaign_id == campaign_uuid,
                        CharacterCampaignInstance.is_deleted == False,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    raise ValueError(
                        f"Instance already exists for character {character_uuid} "
                        f"in campaign {campaign_uuid}"
                    )

                # Create instance
                instance = CharacterCampaignInstance.from_character_info(
                    character_info, character_uuid, campaign_uuid
                )

                session.add(instance)
                await session.commit()
                await session.refresh(instance)

                logger.info(
                    f"Created campaign instance for character {character_uuid} "
                    f"in campaign {campaign_uuid}"
                )
                return instance.instance_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating campaign instance: {e}")
            raise

    async def get_instance(
        self, character_uuid: uuid.UUID, campaign_uuid: uuid.UUID
    ) -> Optional[CharacterInfo]:
        """Get character instance in a campaign.

        Args:
            character_uuid: Character UUID
            campaign_uuid: Campaign UUID

        Returns:
            CharacterInfo if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(CharacterCampaignInstance)
                    .where(
                        and_(
                            CharacterCampaignInstance.character_id == character_uuid,
                            CharacterCampaignInstance.campaign_id == campaign_uuid,
                            CharacterCampaignInstance.is_deleted == False,
                        )
                    )
                    .options(selectinload(CharacterCampaignInstance.profile))
                )
                result = await session.execute(stmt)
                instance = result.scalar_one_or_none()

                if not instance:
                    return None

                # Convert to CharacterInfo
                return instance.to_character_info(instance.profile)

        except Exception as e:
            logger.error(
                f"Error retrieving instance for character {character_uuid} "
                f"in campaign {campaign_uuid}: {e}"
            )
            raise

    async def update_instance(self, instance_uuid: uuid.UUID, updates: dict) -> bool:
        """Update campaign instance fields.

        Args:
            instance_uuid: Instance to update
            updates: Dictionary of fields to update

        Returns:
            True if updated, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                instance = await session.get(CharacterCampaignInstance, instance_uuid)

                if not instance or instance.is_deleted:
                    logger.warning(f"Instance {instance_uuid} not found or deleted")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)

                # Update interaction timestamp
                instance.last_interaction = datetime.now(timezone.utc)

                await session.commit()
                logger.info(f"Updated instance {instance_uuid}")
                return True

        except Exception as e:
            logger.error(f"Error updating instance {instance_uuid}: {e}")
            raise

    async def list_instances_for_campaign(
        self, campaign_uuid: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[CharacterInfo]:
        """List all character instances in a campaign.

        Args:
            campaign_uuid: Campaign UUID
            limit: Maximum instances to return
            offset: Number to skip

        Returns:
            List of CharacterInfo dataclasses
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(CharacterCampaignInstance)
                    .where(
                        and_(
                            CharacterCampaignInstance.campaign_id == campaign_uuid,
                            CharacterCampaignInstance.is_deleted == False,
                        )
                    )
                    .options(selectinload(CharacterCampaignInstance.profile))
                    .order_by(CharacterCampaignInstance.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                instances = result.scalars().all()

                return [instance.to_character_info(instance.profile) for instance in instances]

        except Exception as e:
            logger.error(f"Error listing instances for campaign {campaign_uuid}: {e}")
            raise

    async def list_instances_for_character(
        self, character_uuid: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[CharacterInfo]:
        """List all campaign instances for a character.

        Args:
            character_uuid: Character UUID
            limit: Maximum instances to return
            offset: Number to skip

        Returns:
            List of CharacterInfo dataclasses
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(CharacterCampaignInstance)
                    .where(
                        and_(
                            CharacterCampaignInstance.character_id == character_uuid,
                            CharacterCampaignInstance.is_deleted == False,
                        )
                    )
                    .options(selectinload(CharacterCampaignInstance.profile))
                    .order_by(CharacterCampaignInstance.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                instances = result.scalars().all()

                return [instance.to_character_info(instance.profile) for instance in instances]

        except Exception as e:
            logger.error(f"Error listing instances for character {character_uuid}: {e}")
            raise

    async def soft_delete_instance(self, instance_uuid: uuid.UUID) -> bool:
        """Soft delete a campaign instance.

        Args:
            instance_uuid: Instance to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                instance = await session.get(CharacterCampaignInstance, instance_uuid)

                if not instance:
                    return False

                instance.soft_delete()
                await session.commit()

                logger.info(f"Soft deleted instance {instance_uuid}")
                return True

        except Exception as e:
            logger.error(f"Error deleting instance {instance_uuid}: {e}")
            raise

    # ========== NPC Operations (Async) ==========

    async def create_npc(
        self,
        npc: NpcProfileDataclass,
        user_id: str,
        user_email: Optional[str] = None,
        campaign_uuid: Optional[uuid.UUID] = None,
    ) -> uuid.UUID:
        """Create an NPC profile.

        Args:
            npc: NpcProfile dataclass
            user_id: User who owns this NPC
            user_email: Email of owning user
            campaign_uuid: Optional campaign association

        Returns:
            UUID of created NPC profile
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Check if external ID already exists
                stmt = select(NpcProfile).where(
                    NpcProfile.external_npc_id == npc.npc_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing and not existing.is_deleted:
                    raise ValueError(f"NPC with ID {npc.npc_id} already exists")

                db_npc = NpcProfile.from_dataclass(
                    npc, user_id, user_email, campaign_uuid
                )

                session.add(db_npc)
                await session.commit()
                await session.refresh(db_npc)

                logger.info(f"Created NPC {npc.npc_id} (UUID: {db_npc.npc_id}) for user {user_id}")
                return db_npc.npc_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating NPC: {e}")
            raise

    async def get_npc(self, external_npc_id: str) -> Optional[NpcProfileDataclass]:
        """Get NPC profile by external ID.

        Args:
            external_npc_id: External NPC ID

        Returns:
            NpcProfile dataclass if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(NpcProfile).where(
                    and_(
                        NpcProfile.external_npc_id == external_npc_id,
                        NpcProfile.is_deleted == False,
                    )
                )
                result = await session.execute(stmt)
                npc = result.scalar_one_or_none()

                if not npc:
                    return None

                return npc.to_dataclass()

        except Exception as e:
            logger.error(f"Error retrieving NPC {external_npc_id}: {e}")
            raise

    async def update_npc(self, external_npc_id: str, updates: dict) -> bool:
        """Update NPC profile.

        Args:
            external_npc_id: NPC to update
            updates: Dictionary of fields to update

        Returns:
            True if updated, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(NpcProfile).where(
                    NpcProfile.external_npc_id == external_npc_id
                )
                result = await session.execute(stmt)
                npc = result.scalar_one_or_none()

                if not npc or npc.is_deleted:
                    logger.warning(f"NPC {external_npc_id} not found or deleted")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(npc, field):
                        setattr(npc, field, value)

                await session.commit()
                logger.info(f"Updated NPC {external_npc_id}")
                return True

        except Exception as e:
            logger.error(f"Error updating NPC {external_npc_id}: {e}")
            raise

    async def list_npcs_by_user(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[NpcProfileDataclass]:
        """List NPCs created by a user.

        Args:
            user_id: User ID
            limit: Maximum NPCs to return
            offset: Number to skip

        Returns:
            List of NpcProfile dataclasses
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(NpcProfile)
                    .where(
                        and_(
                            NpcProfile.created_by_user_id == user_id,
                            NpcProfile.is_deleted == False,
                        )
                    )
                    .order_by(NpcProfile.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                npcs = result.scalars().all()

                return [npc.to_dataclass() for npc in npcs]

        except Exception as e:
            logger.error(f"Error listing NPCs for user {user_id}: {e}")
            raise

    async def list_npcs_by_campaign(
        self, campaign_uuid: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[NpcProfileDataclass]:
        """List NPCs in a campaign.

        Args:
            campaign_uuid: Campaign UUID
            limit: Maximum NPCs to return
            offset: Number to skip

        Returns:
            List of NpcProfile dataclasses
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(NpcProfile)
                    .where(
                        and_(
                            NpcProfile.campaign_id == campaign_uuid,
                            NpcProfile.is_deleted == False,
                        )
                    )
                    .order_by(NpcProfile.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )

                result = await session.execute(stmt)
                npcs = result.scalars().all()

                return [npc.to_dataclass() for npc in npcs]

        except Exception as e:
            logger.error(f"Error listing NPCs for campaign {campaign_uuid}: {e}")
            raise

    async def soft_delete_npc(self, external_npc_id: str) -> bool:
        """Soft delete an NPC profile.

        Args:
            external_npc_id: NPC to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(NpcProfile).where(
                    NpcProfile.external_npc_id == external_npc_id
                )
                result = await session.execute(stmt)
                npc = result.scalar_one_or_none()

                if not npc:
                    return False

                npc.soft_delete()
                await session.commit()

                logger.info(f"Soft deleted NPC {external_npc_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting NPC {external_npc_id}: {e}")
            raise

    # ========== User Access Operations (Async) ==========

    async def grant_access(
        self,
        character_uuid: uuid.UUID,
        user_id: str,
        user_email: Optional[str] = None,
        role: str = "viewer",
        granted_by: Optional[str] = None,
    ) -> uuid.UUID:
        """Grant user access to a character.

        Args:
            character_uuid: Character UUID
            user_id: User to grant access to
            user_email: Email of user
            role: Access role (owner, viewer, editor)
            granted_by: User who granted access

        Returns:
            UUID of association record
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Check for existing association
                stmt = select(CharacterUser).where(
                    and_(
                        CharacterUser.character_id == character_uuid,
                        CharacterUser.user_id == user_id,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update role
                    existing.role = role
                    existing.granted_by_user_id = granted_by
                    await session.commit()
                    await session.refresh(existing)
                    return existing.association_id

                # Create new association
                assoc = CharacterUser(
                    character_id=character_uuid,
                    user_id=user_id,
                    user_email=user_email,
                    role=role,
                    granted_by_user_id=granted_by,
                )

                session.add(assoc)
                await session.commit()
                await session.refresh(assoc)

                logger.info(f"Granted {role} access to character {character_uuid} for user {user_id}")
                return assoc.association_id

        except Exception as e:
            logger.error(f"Error granting access to character {character_uuid}: {e}")
            raise

    async def revoke_access(self, character_uuid: uuid.UUID, user_id: str) -> bool:
        """Revoke user access to a character.

        Args:
            character_uuid: Character UUID
            user_id: User to revoke access from

        Returns:
            True if revoked, False if not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterUser).where(
                    and_(
                        CharacterUser.character_id == character_uuid,
                        CharacterUser.user_id == user_id,
                    )
                )
                result = await session.execute(stmt)
                assoc = result.scalar_one_or_none()

                if not assoc:
                    return False

                await session.delete(assoc)
                await session.commit()

                logger.info(f"Revoked access to character {character_uuid} for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error revoking access to character {character_uuid}: {e}")
            raise

    async def get_character_owners(self, character_uuid: uuid.UUID) -> List[str]:
        """Get list of user IDs who have access to a character.

        Args:
            character_uuid: Character UUID

        Returns:
            List of user IDs
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterUser.user_id).where(
                    CharacterUser.character_id == character_uuid
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Error getting owners for character {character_uuid}: {e}")
            raise

    async def check_user_access(
        self, character_uuid: uuid.UUID, user_id: str
    ) -> Optional[str]:
        """Check if user has access to a character.

        Args:
            character_uuid: Character UUID
            user_id: User ID

        Returns:
            Access role if user has access, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(CharacterUser.role).where(
                    and_(
                        CharacterUser.character_id == character_uuid,
                        CharacterUser.user_id == user_id,
                    )
                )
                result = await session.execute(stmt)
                role = result.scalar_one_or_none()
                return role

        except Exception as e:
            logger.error(f"Error checking access for character {character_uuid}: {e}")
            raise

    # ========== Sync Versions ==========

    def create_profile_sync(
        self,
        profile: CharacterProfileDataclass,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> uuid.UUID:
        """Synchronous version of create_profile."""
        try:
            with self.db_manager.get_sync_session() as session:
                # Check if external ID already exists
                stmt = select(CharacterProfile).where(
                    CharacterProfile.external_character_id == profile.character_id
                )
                result = session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing and not existing.is_deleted:
                    raise ValueError(
                        f"Character profile with ID {profile.character_id} already exists"
                    )

                # Create profile
                db_profile = CharacterProfile.from_dataclass(
                    profile,
                    created_by_user_id=user_id,
                    created_by_email=user_email,
                )

                session.add(db_profile)

                # Create user association
                if user_id:
                    user_assoc = CharacterUser(
                        character_id=db_profile.character_id,
                        user_id=user_id,
                        user_email=user_email,
                        role="owner",
                    )
                    session.add(user_assoc)

                session.commit()
                session.refresh(db_profile)

                logger.info(
                    f"Created character profile {profile.character_id} "
                    f"(UUID: {db_profile.character_id}) for user {user_id or 'system'}"
                )
                return db_profile.character_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating character profile (sync): {e}")
            raise

    def get_profile_sync(
        self, external_character_id: str
    ) -> Optional[CharacterProfileDataclass]:
        """Synchronous version of get_profile."""
        try:
            with self.db_manager.get_sync_session() as session:
                stmt = select(CharacterProfile).where(
                    and_(
                        CharacterProfile.external_character_id == external_character_id,
                        CharacterProfile.is_deleted == False,
                    )
                )
                result = session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile:
                    return None

                return profile.to_dataclass()

        except Exception as e:
            logger.error(f"Error retrieving character profile (sync) {external_character_id}: {e}")
            raise

    def update_profile_sync(self, external_character_id: str, updates: dict) -> bool:
        """Synchronous version of update_profile."""
        # Define mutable fields (same as async version)
        mutable_fields = {
            "voice_id",
            "voice_settings",
            "voice_archetype",
            "portrait_url",
            "portrait_path",
            "portrait_prompt",
            "additional_images",
            "gender",
            "age_category",
            "build",
            "height_description",
            "facial_expression",
            "facial_features",
            "attire",
            "primary_weapon",
            "distinguishing_feature",
            "background_setting",
            "pose",
            "backstory",
            "description",
            "appearance",
            "visual_description",
            "personality_traits",
            "bonds",
            "flaws",
            "total_interactions",
        }

        immutable_attempts = set(updates.keys()) - mutable_fields
        if immutable_attempts:
            raise ValueError(
                f"Cannot update immutable fields: {immutable_attempts}. "
                f"Only these fields can be updated: {mutable_fields}"
            )

        try:
            with self.db_manager.get_sync_session() as session:
                stmt = select(CharacterProfile).where(
                    CharacterProfile.external_character_id == external_character_id
                )
                result = session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile or profile.is_deleted:
                    logger.warning(f"Character profile {external_character_id} not found or deleted")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(profile, field):
                        setattr(profile, field, value)

                session.commit()
                logger.info(f"Updated character profile (sync) {external_character_id}")
                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating character profile (sync) {external_character_id}: {e}")
            raise

    def create_instance_sync(
        self,
        character_info: CharacterInfo,
        character_uuid: uuid.UUID,
        campaign_uuid: uuid.UUID,
    ) -> uuid.UUID:
        """Synchronous version of create_instance."""
        try:
            with self.db_manager.get_sync_session() as session:
                # Check for existing instance
                stmt = select(CharacterCampaignInstance).where(
                    and_(
                        CharacterCampaignInstance.character_id == character_uuid,
                        CharacterCampaignInstance.campaign_id == campaign_uuid,
                        CharacterCampaignInstance.is_deleted == False,
                    )
                )
                result = session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    raise ValueError(
                        f"Instance already exists for character {character_uuid} "
                        f"in campaign {campaign_uuid}"
                    )

                # Create instance
                instance = CharacterCampaignInstance.from_character_info(
                    character_info, character_uuid, campaign_uuid
                )

                session.add(instance)
                session.commit()
                session.refresh(instance)

                logger.info(
                    f"Created campaign instance (sync) for character {character_uuid} "
                    f"in campaign {campaign_uuid}"
                )
                return instance.instance_id

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating campaign instance (sync): {e}")
            raise

    def get_instance_sync(
        self, character_uuid: uuid.UUID, campaign_uuid: uuid.UUID
    ) -> Optional[CharacterInfo]:
        """Synchronous version of get_instance."""
        try:
            with self.db_manager.get_sync_session() as session:
                stmt = (
                    select(CharacterCampaignInstance)
                    .where(
                        and_(
                            CharacterCampaignInstance.character_id == character_uuid,
                            CharacterCampaignInstance.campaign_id == campaign_uuid,
                            CharacterCampaignInstance.is_deleted == False,
                        )
                    )
                    .options(selectinload(CharacterCampaignInstance.profile))
                )
                result = session.execute(stmt)
                instance = result.scalar_one_or_none()

                if not instance:
                    return None

                return instance.to_character_info(instance.profile)

        except Exception as e:
            logger.error(
                f"Error retrieving instance (sync) for character {character_uuid} "
                f"in campaign {campaign_uuid}: {e}"
            )
            raise

    def update_instance_sync(self, instance_uuid: uuid.UUID, updates: dict) -> bool:
        """Synchronous version of update_instance."""
        try:
            with self.db_manager.get_sync_session() as session:
                instance = session.get(CharacterCampaignInstance, instance_uuid)

                if not instance or instance.is_deleted:
                    logger.warning(f"Instance {instance_uuid} not found or deleted")
                    return False

                # Update fields
                for field, value in updates.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)

                # Update interaction timestamp
                instance.last_interaction = datetime.now(timezone.utc)

                session.commit()
                logger.info(f"Updated instance (sync) {instance_uuid}")
                return True

        except Exception as e:
            logger.error(f"Error updating instance (sync) {instance_uuid}: {e}")
            raise
