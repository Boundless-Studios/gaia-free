"""Schema for load campaign request."""

from pydantic import BaseModel


class LoadCampaignRequest(BaseModel):
    """Request to load a campaign."""
    campaign_id: str
