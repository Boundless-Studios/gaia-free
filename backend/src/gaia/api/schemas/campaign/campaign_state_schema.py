"""Schema for campaign state."""

from typing import Optional, Dict, Any, List

from pydantic import BaseModel

from gaia.api.schemas.campaign.conversation_history import ConversationHistory


class CampaignStateSchema(BaseModel):
    """Current state of a campaign."""
    campaign_id: str
    conversation_history: Optional[ConversationHistory] = None
    world_state: Optional[Dict[str, Any]] = {}
    character_sheets: Optional[Dict[str, Any]] = {}
    scene_context: Optional[Dict[str, Any]] = {}
    current_scene: Optional[str] = ""
    active_quests: Optional[List[str]] = []
    inventory: Optional[Dict[str, int]] = {}
    custom_data: Optional[Dict[str, Any]] = None
