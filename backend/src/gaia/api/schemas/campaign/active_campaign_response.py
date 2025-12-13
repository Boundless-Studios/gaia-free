"""Schema for active campaign response."""

from typing import Optional

from pydantic import BaseModel


class ActiveCampaignResponse(BaseModel):
    """Response for active campaign query."""
    active_campaign_id: Optional[str] = None
    name: Optional[str] = None
