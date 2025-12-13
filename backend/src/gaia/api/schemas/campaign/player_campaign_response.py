"""Schema for player campaign response."""

from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel

from gaia.api.schemas.chat import StructuredGameData
from gaia.api.schemas.campaign.player_campaign_message import PlayerCampaignMessage


class PlayerCampaignResponse(BaseModel):
    """Response for player campaign view."""
    success: bool = True
    campaign_id: str
    session_id: str
    name: Optional[str] = None
    timestamp: datetime
    activated: bool = False
    needs_response: bool = False
    structured_data: Optional[StructuredGameData] = None
    messages: List[PlayerCampaignMessage] = []
    message_count: int = 0
    current_turn: int = 0  # Current turn number from DB turn_events
