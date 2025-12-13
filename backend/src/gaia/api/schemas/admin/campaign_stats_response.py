"""Schema for campaign statistics response."""

from typing import Dict

from pydantic import BaseModel


class CampaignStatsResponse(BaseModel):
    """Response model for campaign statistics."""
    total_campaigns: int
    active_campaigns: int
    inactive_campaigns: int
    campaigns_by_environment: Dict[str, int]
    total_events: int
    events_by_type: Dict[str, int]
    campaigns_processing: int
