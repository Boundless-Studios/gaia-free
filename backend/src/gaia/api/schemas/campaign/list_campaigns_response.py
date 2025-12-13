"""Schema for list campaigns response."""

from typing import Optional, List

from pydantic import BaseModel

from gaia.api.schemas.campaign.campaign_metadata import CampaignMetadata


class ListCampaignsResponse(BaseModel):
    """Response with list of campaigns."""
    success: bool = True
    campaigns: List[CampaignMetadata]
    total_count: int
    message: Optional[str] = None
