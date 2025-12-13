"""Schema for save campaign response."""

from datetime import datetime

from pydantic import BaseModel


class SaveCampaignResponse(BaseModel):
    """Response from saving a campaign."""
    success: bool = True
    campaign_id: str
    message: str = "Campaign saved successfully"
    saved_at: datetime
