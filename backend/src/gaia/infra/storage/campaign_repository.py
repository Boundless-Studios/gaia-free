"""Repository layer for campaign database operations.

Provides a clean interface for CRUD operations on campaigns, campaign state,
and turn events, abstracting database implementation details from business logic.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from db.src.connection import db_manager
from gaia.models.campaign_db import Campaign
from gaia.models.campaign_state_db import CampaignState
from gaia.models.turn_event_db import TurnEvent, TurnEventType, TurnEventRole

logger = logging.getLogger(__name__)


class CampaignRepository:
    """Repository for campaign database operations.

    Handles conversion between external campaign IDs and database models,
    manages transactions, and provides query methods.
    """

    def __init__(self):
        """Initialize repository with database manager."""
        self.db_manager = db_manager

    # =========================================================================
    # Campaign CRUD
    # =========================================================================

    async def get_or_create_campaign(
        self,
        external_campaign_id: str,
        environment: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Campaign:
        """Get existing campaign or create new one.

        Args:
            external_campaign_id: Filesystem campaign identifier
            environment: Environment (dev/staging/prod)
            name: Optional display name
            description: Optional description
            owner_id: Optional owner user ID

        Returns:
            Campaign model instance
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Try to find existing campaign
                stmt = select(Campaign).where(
                    Campaign.external_campaign_id == external_campaign_id
                )
                result = await session.execute(stmt)
                campaign = result.scalar_one_or_none()

                if campaign:
                    logger.debug(
                        f"Found existing campaign: {external_campaign_id} -> {campaign.campaign_id}"
                    )
                    return campaign

                # Create new campaign with state
                campaign = Campaign(
                    external_campaign_id=external_campaign_id,
                    environment=environment,
                    name=name,
                    description=description,
                    owner_id=owner_id,
                )

                # Create initial state
                state = CampaignState(
                    campaign_id=campaign.campaign_id,
                    current_turn=0,
                )
                campaign.state = state

                session.add(campaign)
                await session.commit()
                await session.refresh(campaign)

                logger.info(
                    f"Created campaign: {external_campaign_id} -> {campaign.campaign_id}"
                )
                return campaign

        except SQLAlchemyError as e:
            logger.error(f"Error getting/creating campaign {external_campaign_id}: {e}")
            raise

    async def get_campaign_by_external_id(
        self, external_campaign_id: str
    ) -> Optional[Campaign]:
        """Get campaign by external (filesystem) ID.

        Args:
            external_campaign_id: Filesystem campaign identifier

        Returns:
            Campaign if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(Campaign)
                    .where(Campaign.external_campaign_id == external_campaign_id)
                    .options(selectinload(Campaign.state))
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error getting campaign {external_campaign_id}: {e}")
            raise

    async def get_campaign_uuid(self, external_campaign_id: str) -> Optional[uuid.UUID]:
        """Get campaign UUID by external ID.

        Args:
            external_campaign_id: Filesystem campaign identifier

        Returns:
            Campaign UUID if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = select(Campaign.campaign_id).where(
                    Campaign.external_campaign_id == external_campaign_id
                )
                result = await session.execute(stmt)
                row = result.first()
                return row[0] if row else None

        except SQLAlchemyError as e:
            logger.error(f"Error getting campaign UUID {external_campaign_id}: {e}")
            raise

    # =========================================================================
    # Campaign State Operations
    # =========================================================================

    async def get_campaign_state(
        self, external_campaign_id: str
    ) -> Optional[CampaignState]:
        """Get campaign state by external ID.

        Args:
            external_campaign_id: Filesystem campaign identifier

        Returns:
            CampaignState if found, None otherwise
        """
        try:
            async with self.db_manager.get_async_session() as session:
                stmt = (
                    select(CampaignState)
                    .join(Campaign)
                    .where(Campaign.external_campaign_id == external_campaign_id)
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error getting campaign state {external_campaign_id}: {e}")
            raise

    async def update_campaign_state(
        self,
        external_campaign_id: str,
        current_turn: Optional[int] = None,
        last_turn_started_at: Optional[datetime] = None,
        last_turn_completed_at: Optional[datetime] = None,
        active_turn: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update campaign state fields.

        Uses optimistic concurrency via version field.

        Args:
            external_campaign_id: Filesystem campaign identifier
            current_turn: New turn number
            last_turn_started_at: Turn start timestamp
            last_turn_completed_at: Turn completion timestamp
            active_turn: Active turn state dict

        Returns:
            True if updated, False if campaign not found
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Get campaign UUID
                campaign_stmt = select(Campaign.campaign_id).where(
                    Campaign.external_campaign_id == external_campaign_id
                )
                campaign_result = await session.execute(campaign_stmt)
                campaign_row = campaign_result.first()

                if not campaign_row:
                    logger.warning(f"Campaign not found: {external_campaign_id}")
                    return False

                campaign_id = campaign_row[0]

                # Build update values
                values: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

                if current_turn is not None:
                    values["current_turn"] = current_turn
                if last_turn_started_at is not None:
                    values["last_turn_started_at"] = last_turn_started_at
                if last_turn_completed_at is not None:
                    values["last_turn_completed_at"] = last_turn_completed_at
                if active_turn is not None:
                    values["active_turn"] = active_turn

                # Increment version for optimistic concurrency
                values["version"] = CampaignState.version + 1

                stmt = (
                    update(CampaignState)
                    .where(CampaignState.campaign_id == campaign_id)
                    .values(**values)
                )
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.debug(
                        f"Updated campaign state: {external_campaign_id}, "
                        f"turn={current_turn}, active_turn={active_turn}"
                    )
                    return True

                return False

        except SQLAlchemyError as e:
            logger.error(f"Error updating campaign state {external_campaign_id}: {e}")
            raise

    async def start_turn(
        self,
        external_campaign_id: str,
        turn_number: int,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a turn as started.

        Args:
            external_campaign_id: Filesystem campaign identifier
            turn_number: Turn number being started
            input_payload: Optional input data for the turn

        Returns:
            True if updated successfully
        """
        return await self.update_campaign_state(
            external_campaign_id=external_campaign_id,
            current_turn=turn_number,
            last_turn_started_at=datetime.now(timezone.utc),
            active_turn={
                "turn_number": turn_number,
                "input_payload": input_payload,
                "is_processing": True,
            },
        )

    async def complete_turn(
        self,
        external_campaign_id: str,
        turn_number: int,
    ) -> bool:
        """Mark a turn as completed.

        Args:
            external_campaign_id: Filesystem campaign identifier
            turn_number: Turn number being completed

        Returns:
            True if updated successfully
        """
        return await self.update_campaign_state(
            external_campaign_id=external_campaign_id,
            last_turn_completed_at=datetime.now(timezone.utc),
            active_turn={
                "turn_number": turn_number,
                "is_processing": False,
            },
        )

    # =========================================================================
    # Turn Event Operations
    # =========================================================================

    async def add_turn_event(
        self,
        external_campaign_id: str,
        turn_number: int,
        event_index: int,
        event_type: str,
        role: str,
        content: Optional[Dict[str, Any]] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[TurnEvent]:
        """Add a turn event.

        Args:
            external_campaign_id: Filesystem campaign identifier
            turn_number: Turn number
            event_index: Event index within turn
            event_type: Event type (player_input, dm_input, etc.)
            role: Actor role (player, dm, assistant, system)
            content: Event content
            event_metadata: Additional metadata

        Returns:
            Created TurnEvent or None on error
        """
        try:
            # Ensure campaign exists in DB (auto-create if needed)
            campaign = await self.get_or_create_campaign(
                external_campaign_id=external_campaign_id,
                environment="dev",  # Default to dev
            )
            campaign_id = campaign.campaign_id

            async with self.db_manager.get_async_session() as session:

                event = TurnEvent(
                    campaign_id=campaign_id,
                    turn_number=turn_number,
                    event_index=event_index,
                    type=event_type,
                    role=role,
                    content=content,
                    event_metadata=event_metadata or {},
                )

                session.add(event)
                await session.commit()
                await session.refresh(event)

                logger.debug(
                    f"Added turn event: campaign={external_campaign_id}, "
                    f"turn={turn_number}, index={event_index}, type={event_type}"
                )
                return event

        except SQLAlchemyError as e:
            logger.error(f"Error adding turn event: {e}")
            raise

    async def add_turn_input_event(
        self,
        external_campaign_id: str,
        turn_number: int,
        active_player: Optional[Dict[str, Any]],
        observer_inputs: List[Dict[str, Any]],
        dm_input: Optional[Dict[str, Any]],
        combined_prompt: str,
    ) -> Optional[TurnEvent]:
        """Add a turn_input event (combined input for the turn).

        Args:
            external_campaign_id: Filesystem campaign identifier
            turn_number: Turn number
            active_player: Active player input dict
            observer_inputs: List of observer input dicts
            dm_input: DM input dict
            combined_prompt: Combined prompt string

        Returns:
            Created TurnEvent or None
        """
        return await self.add_turn_event(
            external_campaign_id=external_campaign_id,
            turn_number=turn_number,
            event_index=0,  # turn_input is always first
            event_type=TurnEventType.TURN_INPUT,
            role=TurnEventRole.SYSTEM,
            content={
                "active_player": active_player,
                "observer_inputs": observer_inputs,
                "dm_input": dm_input,
                "combined_prompt": combined_prompt,
            },
        )

    async def add_assistant_response_event(
        self,
        external_campaign_id: str,
        turn_number: int,
        content: Dict[str, Any],
        event_index: int = 1,
    ) -> Optional[TurnEvent]:
        """Add an assistant response event (final LLM response).

        Args:
            external_campaign_id: Filesystem campaign identifier
            turn_number: Turn number
            content: Response content
            event_index: Event index (default 1, after turn_input)

        Returns:
            Created TurnEvent or None
        """
        return await self.add_turn_event(
            external_campaign_id=external_campaign_id,
            turn_number=turn_number,
            event_index=event_index,
            event_type=TurnEventType.ASSISTANT,
            role=TurnEventRole.ASSISTANT,
            content=content,
        )

    async def get_turn_events(
        self,
        external_campaign_id: str,
        limit: int = 100,
        offset: int = 0,
        turn_number: Optional[int] = None,
    ) -> List[TurnEvent]:
        """Get turn events for a campaign.

        Args:
            external_campaign_id: Filesystem campaign identifier
            limit: Maximum events to return
            offset: Offset for pagination
            turn_number: Optional filter by turn number

        Returns:
            List of TurnEvent models
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Get campaign UUID
                campaign_id = await self._get_campaign_uuid_in_session(
                    session, external_campaign_id
                )
                if not campaign_id:
                    return []

                conditions = [TurnEvent.campaign_id == campaign_id]
                if turn_number is not None:
                    conditions.append(TurnEvent.turn_number == turn_number)

                stmt = (
                    select(TurnEvent)
                    .where(and_(*conditions))
                    .order_by(TurnEvent.turn_number, TurnEvent.event_index)
                    .offset(offset)
                    .limit(limit)
                )

                result = await session.execute(stmt)
                return list(result.scalars().all())

        except SQLAlchemyError as e:
            logger.error(f"Error getting turn events: {e}")
            raise

    async def get_turn_events_as_dicts(
        self,
        external_campaign_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get turn events as dictionaries for API responses.

        Args:
            external_campaign_id: Filesystem campaign identifier
            limit: Maximum events to return
            offset: Offset for pagination

        Returns:
            List of event dictionaries
        """
        events = await self.get_turn_events(
            external_campaign_id=external_campaign_id,
            limit=limit,
            offset=offset,
        )
        return [event.to_dict() for event in events]

    async def get_next_event_index(
        self,
        external_campaign_id: str,
        turn_number: int,
    ) -> int:
        """Get the next event index for a turn.

        Args:
            external_campaign_id: Filesystem campaign identifier
            turn_number: Turn number

        Returns:
            Next available event index
        """
        try:
            async with self.db_manager.get_async_session() as session:
                campaign_id = await self._get_campaign_uuid_in_session(
                    session, external_campaign_id
                )
                if not campaign_id:
                    return 0

                from sqlalchemy import func

                stmt = select(func.max(TurnEvent.event_index)).where(
                    and_(
                        TurnEvent.campaign_id == campaign_id,
                        TurnEvent.turn_number == turn_number,
                    )
                )
                result = await session.execute(stmt)
                max_index = result.scalar()

                # max_index can be 0 (valid), None (no events), or positive
                return (max_index + 1) if max_index is not None else 0

        except SQLAlchemyError as e:
            logger.error(f"Error getting next event index: {e}")
            return 0

    # =========================================================================
    # Sync Methods (for use from sync contexts)
    # =========================================================================

    def get_or_create_campaign_sync(
        self,
        external_campaign_id: str,
        environment: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Campaign:
        """Synchronous version of get_or_create_campaign."""
        try:
            with self.db_manager.get_sync_session() as session:
                stmt = select(Campaign).where(
                    Campaign.external_campaign_id == external_campaign_id
                )
                result = session.execute(stmt)
                campaign = result.scalar_one_or_none()

                if campaign:
                    return campaign

                campaign = Campaign(
                    external_campaign_id=external_campaign_id,
                    environment=environment,
                    name=name,
                    description=description,
                    owner_id=owner_id,
                )

                state = CampaignState(
                    campaign_id=campaign.campaign_id,
                    current_turn=0,
                )
                campaign.state = state

                session.add(campaign)
                session.commit()
                session.refresh(campaign)

                logger.info(
                    f"Created campaign (sync): {external_campaign_id} -> {campaign.campaign_id}"
                )
                return campaign

        except SQLAlchemyError as e:
            logger.error(f"Error getting/creating campaign (sync) {external_campaign_id}: {e}")
            raise

    def get_campaign_state_sync(
        self, external_campaign_id: str
    ) -> Optional[CampaignState]:
        """Synchronous version of get_campaign_state."""
        try:
            with self.db_manager.get_sync_session() as session:
                stmt = (
                    select(CampaignState)
                    .join(Campaign)
                    .where(Campaign.external_campaign_id == external_campaign_id)
                )
                result = session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"Error getting campaign state (sync) {external_campaign_id}: {e}")
            raise

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_campaign_uuid_in_session(
        self, session: AsyncSession, external_campaign_id: str
    ) -> Optional[uuid.UUID]:
        """Get campaign UUID within an existing session."""
        stmt = select(Campaign.campaign_id).where(
            Campaign.external_campaign_id == external_campaign_id
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else None


# Singleton instance
campaign_repository = CampaignRepository()
