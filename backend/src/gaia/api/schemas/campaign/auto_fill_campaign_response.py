"""Schema for auto-fill campaign response."""

from pydantic import BaseModel

from gaia.api.schemas.campaign.simple_campaign import SimpleCampaign


class AutoFillCampaignResponse(BaseModel):
    """Response from auto-filling a campaign."""
    success: bool = True
    campaign: SimpleCampaign
