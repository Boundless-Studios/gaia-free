"""Schema for delete campaign response."""

from pydantic import BaseModel


class DeleteCampaignResponse(BaseModel):
    """Response from deleting a campaign."""
    success: bool = True
    message: str = "Campaign deleted successfully"
