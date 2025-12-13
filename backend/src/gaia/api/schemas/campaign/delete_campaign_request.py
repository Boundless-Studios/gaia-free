"""Schema for delete campaign request."""

from pydantic import BaseModel


class DeleteCampaignRequest(BaseModel):
    """Request to delete a campaign."""
    campaign_id: str
