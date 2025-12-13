"""Schema for campaign admin response."""

from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from gaia.models.campaign_db import Campaign


class CampaignAdminResponse(BaseModel):
    """Response model for campaign listing."""
    campaign_id: str
    external_campaign_id: str
    environment: str
    name: Optional[str]
    description: Optional[str]
    owner_id: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    # Nested state summary
    current_turn: int
    is_processing: bool
    event_count: int

    @staticmethod
    def from_model(campaign: "Campaign", event_count: int = 0) -> "CampaignAdminResponse":
        state = campaign.state
        return CampaignAdminResponse(
            campaign_id=str(campaign.campaign_id),
            external_campaign_id=campaign.external_campaign_id,
            environment=campaign.environment,
            name=campaign.name,
            description=campaign.description,
            owner_id=campaign.owner_id,
            is_active=campaign.is_active,
            created_at=campaign.created_at.isoformat() if hasattr(campaign, 'created_at') and campaign.created_at else None,
            updated_at=campaign.updated_at.isoformat() if hasattr(campaign, 'updated_at') and campaign.updated_at else None,
            current_turn=state.current_turn if state else 0,
            is_processing=state.is_processing if state else False,
            event_count=event_count,
        )
