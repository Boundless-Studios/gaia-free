"""Schema for list campaigns request."""

from pydantic import BaseModel, Field


class ListCampaignsRequest(BaseModel):
    """Request to list campaigns."""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="last_played", pattern="^(created|last_played|title)$")
    ascending: bool = False
