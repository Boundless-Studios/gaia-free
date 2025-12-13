"""SQLAlchemy model for turn event persistence in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from db.src.base import BaseModel

if TYPE_CHECKING:
    from gaia.models.campaign_db import Campaign


class TurnEventType:
    """Constants for turn event types."""

    PLAYER_INPUT = "player_input"
    DM_INPUT = "dm_input"
    TURN_INPUT = "turn_input"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TurnEventRole:
    """Constants for turn event roles."""

    PLAYER = "player"
    DM = "dm"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TurnEvent(BaseModel):
    """SQLAlchemy model for turn events stored in PostgreSQL.

    Maps to game.turn_events table. Lightweight event log for turn inputs
    and responses. Used for chat history on refresh.

    Note: Streaming chunks are NOT stored - only committed inputs and
    final responses. Streaming happens via WebSocket only.
    """

    __tablename__ = "turn_events"
    __table_args__ = {"schema": "game"}

    # Primary key
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to campaigns
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game.campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Turn identification
    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Ordering within turn (0, 1, 2...)
    event_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Event type: player_input, dm_input, turn_input, assistant, system
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Actor role: player, dm, assistant, system
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Structured content (varies by type)
    content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # Extensible metadata
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Creation timestamp (no updated_at - events are immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Override BaseModel's updated_at - events are immutable, no update timestamp needed
    updated_at = None  # type: ignore

    # Relationship back to campaign
    campaign: Mapped["Campaign"] = relationship(
        "Campaign",
        back_populates="turn_events",
    )

    def __repr__(self) -> str:
        return (
            f"<TurnEvent(event_id={self.event_id}, "
            f"turn_number={self.turn_number}, "
            f"event_index={self.event_index}, "
            f"type='{self.type}', "
            f"role='{self.role}')>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for API responses."""
        return {
            "event_id": str(self.event_id),
            "campaign_id": str(self.campaign_id),
            "turn_number": self.turn_number,
            "event_index": self.event_index,
            "type": self.type,
            "role": self.role,
            "content": self.content,
            "event_metadata": self.event_metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def create_player_input(
        cls,
        campaign_id: uuid.UUID,
        turn_number: int,
        event_index: int,
        character_id: str,
        text: str,
        input_type: str = "action",
        user_id: Optional[str] = None,
    ) -> "TurnEvent":
        """Factory method for player input events."""
        return cls(
            campaign_id=campaign_id,
            turn_number=turn_number,
            event_index=event_index,
            type=TurnEventType.PLAYER_INPUT,
            role=TurnEventRole.PLAYER,
            content={
                "character_id": character_id,
                "text": text,
                "input_type": input_type,
                "user_id": user_id,
            },
        )

    @classmethod
    def create_dm_input(
        cls,
        campaign_id: uuid.UUID,
        turn_number: int,
        event_index: int,
        text: str,
        user_id: Optional[str] = None,
        modifications: Optional[str] = None,
    ) -> "TurnEvent":
        """Factory method for DM input events."""
        return cls(
            campaign_id=campaign_id,
            turn_number=turn_number,
            event_index=event_index,
            type=TurnEventType.DM_INPUT,
            role=TurnEventRole.DM,
            content={
                "text": text,
                "user_id": user_id,
                "modifications": modifications,
            },
        )

    @classmethod
    def create_turn_input(
        cls,
        campaign_id: uuid.UUID,
        turn_number: int,
        event_index: int,
        active_player: Optional[Dict[str, Any]],
        observer_inputs: list,
        dm_input: Optional[Dict[str, Any]],
        combined_prompt: str,
    ) -> "TurnEvent":
        """Factory method for combined turn input events."""
        return cls(
            campaign_id=campaign_id,
            turn_number=turn_number,
            event_index=event_index,
            type=TurnEventType.TURN_INPUT,
            role=TurnEventRole.SYSTEM,
            content={
                "active_player": active_player,
                "observer_inputs": observer_inputs,
                "dm_input": dm_input,
                "combined_prompt": combined_prompt,
            },
        )

    @classmethod
    def create_assistant_response(
        cls,
        campaign_id: uuid.UUID,
        turn_number: int,
        event_index: int,
        content: Dict[str, Any],
    ) -> "TurnEvent":
        """Factory method for assistant response events."""
        return cls(
            campaign_id=campaign_id,
            turn_number=turn_number,
            event_index=event_index,
            type=TurnEventType.ASSISTANT,
            role=TurnEventRole.ASSISTANT,
            content=content,
        )

    @classmethod
    def create_system_message(
        cls,
        campaign_id: uuid.UUID,
        turn_number: int,
        event_index: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> "TurnEvent":
        """Factory method for system message events."""
        return cls(
            campaign_id=campaign_id,
            turn_number=turn_number,
            event_index=event_index,
            type=TurnEventType.SYSTEM,
            role=TurnEventRole.SYSTEM,
            content={
                "message": message,
                "context": context or {},
            },
        )
