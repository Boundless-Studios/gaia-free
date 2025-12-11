"""
OpenAPI/Pydantic schemas for campaign management.
Completes the migration from protobuf to OpenAPI.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from gaia.api.schemas.chat import MachineResponse, StructuredGameData


class ConversationMessage(BaseModel):
    """A single message in the conversation history.

    Turn-based ordering fields (turn_number, response_index, response_type)
    provide authoritative message ordering, replacing timestamp-based sorting.

    Turn Structure:
    - Each turn has a monotonically increasing turn_number
    - Within a turn, response_index orders messages:
      - 0: TURN_INPUT (player + DM input)
      - 1-N: STREAMING chunks
      - N+1: FINAL response
    """

    message_id: str
    timestamp: datetime
    role: str
    content: str

    # Turn-based ordering (authoritative)
    turn_number: Optional[int] = None  # Global turn counter (1, 2, 3...)
    response_index: Optional[int] = None  # Index within turn (0, 1, 2...)
    response_type: Optional[str] = None  # turn_input | streaming | final | system | private

    # Attribution
    sender_user_id: Optional[str] = None  # Who sent this message
    character_id: Optional[str] = None
    character_name: Optional[str] = None

    # Agent metadata
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    thinking_details: Optional[str] = None

    # Audio
    has_audio: bool = False
    audio_url: Optional[str] = None


class ConversationHistory(BaseModel):
    """Complete conversation history for a session."""
    session_id: str
    messages: List[ConversationMessage]
    total_messages: int
    session_started: datetime
    last_activity: datetime


class CampaignMetadata(BaseModel):
    """Metadata about a campaign."""
    campaign_id: str
    title: str
    description: Optional[str] = ""
    created_at: datetime
    last_played: datetime
    game_style: Optional[str] = "balanced"
    tags: Optional[Dict[str, str]] = {}
    total_sessions: Optional[int] = 0
    total_playtime_hours: Optional[float] = 0.0


class CampaignState(BaseModel):
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


class SaveCampaignRequest(BaseModel):
    """Request to save a campaign."""
    campaign_id: str
    metadata: CampaignMetadata
    state: CampaignState
    auto_save: bool = False


class SaveCampaignResponse(BaseModel):
    """Response from saving a campaign."""
    success: bool = True
    campaign_id: str
    message: str = "Campaign saved successfully"
    saved_at: datetime


class LoadCampaignRequest(BaseModel):
    """Request to load a campaign."""
    campaign_id: str


class LoadCampaignResponse(BaseModel):
    """Response from loading a campaign."""
    success: bool = True
    metadata: CampaignMetadata
    state: CampaignState
    message: str = "Campaign loaded successfully"


class ListCampaignsRequest(BaseModel):
    """Request to list campaigns."""
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="last_played", pattern="^(created|last_played|title)$")
    ascending: bool = False


class ListCampaignsResponse(BaseModel):
    """Response with list of campaigns."""
    success: bool = True
    campaigns: List[CampaignMetadata]
    total_count: int
    message: Optional[str] = None


class DeleteCampaignRequest(BaseModel):
    """Request to delete a campaign."""
    campaign_id: str


class DeleteCampaignResponse(BaseModel):
    """Response from deleting a campaign."""
    success: bool = True
    message: str = "Campaign deleted successfully"


class StatsResponse(BaseModel):
    """Statistics response."""
    success: bool = True
    current_agent: Optional[str] = None
    total_messages: int = 0
    model_name: Optional[str] = None
    session_duration: float = 0.0
    agent_stats: Optional[Dict[str, Any]] = {}


# Character Generation Models

class SimpleCharacter(BaseModel):
    """Simple character representation for frontend display."""
    name: str
    character_class: str
    race: str
    level: int = 1
    description: Optional[str] = ""
    backstory: Optional[str] = ""


class SimpleCampaign(BaseModel):
    """Simple campaign info for frontend display."""
    title: str
    description: str
    game_style: str = "balanced"


class AutoFillCampaignRequest(BaseModel):
    """Request to auto-fill a campaign."""
    # Empty - just triggers random selection
    pass


class AutoFillCampaignResponse(BaseModel):
    """Response from auto-filling a campaign."""
    success: bool = True
    campaign: SimpleCampaign


class AutoFillCharacterRequest(BaseModel):
    """Request to auto-fill a character."""
    slot_id: int


class AutoFillCharacterResponse(BaseModel):
    """Response from auto-filling a character."""
    success: bool = True
    character: SimpleCharacter


# Additional models that weren't in protobuf but are used

class UserInput(BaseModel):
    """User input message."""
    message_id: str
    timestamp: datetime
    session_id: str
    message_type: str = "USER_INPUT"
    content: str
    input_type: str
    metadata: Optional[Dict[str, Any]] = None
    character_id: Optional[str] = None
    character_name: Optional[str] = None


class SystemEvent(BaseModel):
    """System event message."""
    message_id: str
    timestamp: datetime
    session_id: str
    message_type: str = "SYSTEM_EVENT"
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    severity: Optional[str] = "info"


class BaseMessage(BaseModel):
    """Base message class."""
    message_id: str
    timestamp: datetime
    session_id: str
    message_type: str


# WebSocket and Player View Models

class PlayerCampaignMessage(BaseModel):
    """Message in player campaign view."""
    message_id: str
    timestamp: datetime
    role: str
    content: Any  # Can be string or dict
    agent_name: Optional[str] = None


class PlayerCampaignResponse(BaseModel):
    """Response for player campaign view."""
    success: bool = True
    campaign_id: str
    session_id: str
    name: Optional[str] = None
    timestamp: datetime
    activated: bool = False
    needs_response: bool = False
    structured_data: Optional[StructuredGameData] = None
    messages: List[PlayerCampaignMessage] = []
    message_count: int = 0


class ActiveCampaignResponse(BaseModel):
    """Response for active campaign query."""
    active_campaign_id: Optional[str] = None
    name: Optional[str] = None
