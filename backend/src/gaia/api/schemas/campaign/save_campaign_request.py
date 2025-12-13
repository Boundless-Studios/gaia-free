"""Schema for save campaign request."""

from pydantic import BaseModel

from gaia.api.schemas.campaign.campaign_metadata import CampaignMetadata
from gaia.api.schemas.campaign.campaign_state_schema import CampaignStateSchema


class SaveCampaignRequest(BaseModel):
    """Request to save a campaign."""
    campaign_id: str
    metadata: CampaignMetadata
    state: CampaignStateSchema
    auto_save: bool = False
