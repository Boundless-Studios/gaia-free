"""Schema for campaign state response."""

from typing import Optional, Dict, Any, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from gaia.models.campaign_state_db import CampaignState


class CampaignStateResponse(BaseModel):
    """Response model for campaign state."""
    state_id: str
    campaign_id: str
    current_turn: int
    last_turn_started_at: Optional[str]
    last_turn_completed_at: Optional[str]
    is_processing: bool
    active_turn: Optional[Dict[str, Any]]
    version: int

    @staticmethod
    def from_model(state: "CampaignState") -> "CampaignStateResponse":
        return CampaignStateResponse(
            state_id=str(state.state_id),
            campaign_id=str(state.campaign_id),
            current_turn=state.current_turn,
            last_turn_started_at=state.last_turn_started_at.isoformat() if state.last_turn_started_at else None,
            last_turn_completed_at=state.last_turn_completed_at.isoformat() if state.last_turn_completed_at else None,
            is_processing=state.is_processing,
            active_turn=state.active_turn,
            version=state.version,
        )
