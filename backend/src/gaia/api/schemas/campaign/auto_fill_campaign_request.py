"""Schema for auto-fill campaign request."""

from pydantic import BaseModel


class AutoFillCampaignRequest(BaseModel):
    """Request to auto-fill a campaign."""
    # Empty - just triggers random selection
    pass
