"""Schema for campaign metadata."""

from typing import Optional, Dict
from datetime import datetime

from pydantic import BaseModel


class CampaignMetadata(BaseModel):
    """Metadata about a campaign."""
    campaign_id: str
    title: str
    description: Optional[str] = ""
    created_at: datetime
    last_played: datetime
    game_style: Optional[str] = "balanced"
    tags: Optional[Dict[str, str]] = {}
    total_sessions: Optional[int] = 0
    total_playtime_hours: Optional[float] = 0.0
