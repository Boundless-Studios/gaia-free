"""Schema for load campaign response."""

from pydantic import BaseModel

from gaia.api.schemas.campaign.campaign_metadata import CampaignMetadata
from gaia.api.schemas.campaign.campaign_state_schema import CampaignStateSchema


class LoadCampaignResponse(BaseModel):
    """Response from loading a campaign."""
    success: bool = True
    metadata: CampaignMetadata
    state: CampaignStateSchema
    message: str = "Campaign loaded successfully"
