"""Schema for turn event response."""

from typing import Optional, Dict, Any, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from gaia.models.turn_event_db import TurnEvent


class TurnEventResponse(BaseModel):
    """Response model for turn events."""
    event_id: str
    campaign_id: str
    turn_number: int
    event_index: int
    type: str
    role: str
    content: Optional[Dict[str, Any]]
    event_metadata: Dict[str, Any]
    created_at: str

    @staticmethod
    def from_model(event: "TurnEvent") -> "TurnEventResponse":
        return TurnEventResponse(
            event_id=str(event.event_id),
            campaign_id=str(event.campaign_id),
            turn_number=event.turn_number,
            event_index=event.event_index,
            type=event.type,
            role=event.role,
            content=event.content,
            event_metadata=event.event_metadata,
            created_at=event.created_at.isoformat(),
        )
