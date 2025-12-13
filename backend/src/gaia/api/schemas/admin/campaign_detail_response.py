"""Schema for campaign detail response."""

from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel

from gaia.api.schemas.admin.campaign_state_response import CampaignStateResponse

if TYPE_CHECKING:
    from gaia.models.campaign_db import Campaign


class CampaignDetailResponse(BaseModel):
    """Response model for campaign details with full state."""
    campaign_id: str
    external_campaign_id: str
    environment: str
    name: Optional[str]
    description: Optional[str]
    owner_id: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    state: Optional[CampaignStateResponse]
    event_count: int

    @staticmethod
    def from_model(campaign: "Campaign", event_count: int = 0) -> "CampaignDetailResponse":
        return CampaignDetailResponse(
            campaign_id=str(campaign.campaign_id),
            external_campaign_id=campaign.external_campaign_id,
            environment=campaign.environment,
            name=campaign.name,
            description=campaign.description,
            owner_id=campaign.owner_id,
            is_active=campaign.is_active,
            created_at=campaign.created_at.isoformat() if hasattr(campaign, 'created_at') and campaign.created_at else None,
            updated_at=campaign.updated_at.isoformat() if hasattr(campaign, 'updated_at') and campaign.updated_at else None,
            state=CampaignStateResponse.from_model(campaign.state) if campaign.state else None,
            event_count=event_count,
        )
