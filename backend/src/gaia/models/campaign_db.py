"""SQLAlchemy model for campaign persistence in PostgreSQL."""

from __future__ import annotations

import uuid
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from db.src.base import BaseModel

if TYPE_CHECKING:
    from gaia.models.campaign_state_db import CampaignState
    from gaia.models.turn_event_db import TurnEvent


class Campaign(BaseModel):
    """SQLAlchemy model for campaigns stored in PostgreSQL.

    Maps to game.campaigns table. Core fact table that links filesystem
    campaign IDs to database UUIDs.
    """

    __tablename__ = "campaigns"
    __table_args__ = {"schema": "game"}

    # Primary key
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # External identifier (filesystem campaign_id)
    external_campaign_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Environment (dev/staging/prod) - NO default, must be explicit
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Optional metadata
    name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # Soft active/inactive flag
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Relationships
    state: Mapped[Optional["CampaignState"]] = relationship(
        "CampaignState",
        back_populates="campaign",
        uselist=False,
        cascade="all, delete-orphan",
    )

    turn_events: Mapped[List["TurnEvent"]] = relationship(
        "TurnEvent",
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return (
            f"<Campaign(campaign_id={self.campaign_id}, "
            f"external_campaign_id='{self.external_campaign_id}', "
            f"environment='{self.environment}')>"
        )
