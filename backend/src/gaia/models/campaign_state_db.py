"""SQLAlchemy model for campaign state persistence in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from db.src.base import BaseModel

if TYPE_CHECKING:
    from gaia.models.campaign_db import Campaign


class CampaignState(BaseModel):
    """SQLAlchemy model for campaign state stored in PostgreSQL.

    Maps to game.campaign_state table. Tracks turn state and processing
    status for each campaign. One row per campaign.
    """

    __tablename__ = "campaign_state"
    __table_args__ = {"schema": "game"}

    # Primary key
    state_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to campaigns
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game.campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Turn counter
    current_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Turn timing
    last_turn_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )
    last_turn_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    # Active turn state: {turn_number, input_payload, is_processing}
    active_turn: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # Optimistic concurrency version
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationship back to campaign
    campaign: Mapped["Campaign"] = relationship(
        "Campaign",
        back_populates="state",
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignState(state_id={self.state_id}, "
            f"campaign_id={self.campaign_id}, "
            f"current_turn={self.current_turn}, "
            f"is_processing={self.is_processing})>"
        )

    @property
    def is_processing(self) -> bool:
        """Check if a turn is currently being processed."""
        if self.active_turn is None:
            return False
        return self.active_turn.get("is_processing", False)

    @property
    def active_turn_number(self) -> Optional[int]:
        """Get the turn number being processed, if any."""
        if self.active_turn is None:
            return None
        return self.active_turn.get("turn_number")

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for API responses."""
        return {
            "state_id": str(self.state_id),
            "campaign_id": str(self.campaign_id),
            "current_turn": self.current_turn,
            "last_turn_started_at": (
                self.last_turn_started_at.isoformat()
                if self.last_turn_started_at
                else None
            ),
            "last_turn_completed_at": (
                self.last_turn_completed_at.isoformat()
                if self.last_turn_completed_at
                else None
            ),
            "active_turn": self.active_turn,
            "is_processing": self.is_processing,
            "version": self.version,
        }
