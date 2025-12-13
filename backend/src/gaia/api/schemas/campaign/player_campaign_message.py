"""Schema for player campaign message."""

from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel


class PlayerCampaignMessage(BaseModel):
    """Message in player campaign view."""
    message_id: str
    timestamp: datetime
    role: str
    content: Any  # Can be string or dict
    agent_name: Optional[str] = None
    turn_number: Optional[int] = None  # Turn number from DB turn_events
    response_type: Optional[str] = None  # 'turn_input' or 'final' for frontend turn ordering
