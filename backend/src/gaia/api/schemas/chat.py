"""
OpenAPI/Pydantic schemas for chat and campaign endpoints.
JSON-serializable models.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum


class InputType(str, Enum):
    """Types of input that can be sent to the backend."""
    CHAT = "CHAT"
    NEW_CAMPAIGN = "NEW_CAMPAIGN"
    BLANK_CAMPAIGN = "BLANK_CAMPAIGN"
    CONTEXT = "CONTEXT"


class MessageType(str, Enum):
    """Types of messages in the system."""
    USER_INPUT = "USER_INPUT"
    MACHINE_RESPONSE = "MACHINE_RESPONSE"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    ERROR = "ERROR"



class AgentType(str, Enum):
    """Types of agents that can respond."""
    DUNGEON_MASTER = "DUNGEON_MASTER"
    ENCOUNTER_RUNNER = "ENCOUNTER_RUNNER"
    NARRATOR = "NARRATOR"


class AudioArtifactPayload(BaseModel):
    """Metadata describing a synthesized audio artifact."""

    success: bool = Field(default=True, description="Indicates the artifact can be fetched")
    id: str = Field(..., description="Server-assigned audio artifact identifier")
    session_id: str = Field(..., description="Session the artifact belongs to")
    url: str = Field(..., description="Fetch URL or signed URL for playback")
    mime_type: str = Field(default="audio/mpeg", description="Media mime type")
    size_bytes: int = Field(..., description="Size of artifact in bytes")
    duration_sec: Optional[float] = Field(default=None, description="Duration in seconds if known")
    created_at: datetime = Field(..., description="Creation timestamp")
    provider: Optional[str] = Field(default=None, description="TTS provider used to generate the audio")
    storage_path: Optional[str] = Field(default=None, description="Internal storage path for cleanup tasks")
    bucket: Optional[str] = Field(default=None, description="Bucket name when stored in cloud storage")

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class PlayerCharacterContext(BaseModel):
    """Metadata describing the active player character for a user message."""
    character_id: Optional[str] = Field(default=None, description="Stable identifier for the active character")
    character_name: Optional[str] = Field(default=None, description="Display name for the active character")

    @field_validator("character_id", "character_name")
    @classmethod
    def _strip_empty(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def is_empty(self) -> bool:
        return not (self.character_id or self.character_name)


class StructuredGameData(BaseModel):
    """
    Structured data for game responses.
    All fields are optional and can be strings, dicts, or lists depending on the agent's output.
    """
    narrative: Optional[Union[str, Dict, List]] = Field(default="", description="The narrative content of the response")
    turn: Optional[Union[str, Dict, List]] = Field(default="", description="Current turn information")
    status: Optional[Union[str, Dict]] = Field(default="", description="Current game status")
    characters: Optional[Union[str, Dict, List]] = Field(default="", description="Character information")
    player_options: Optional[Union[str, List[str]]] = Field(default="", description="Available player actions")
    combat_status: Optional[Dict[str, Any]] = Field(default=None, description="Per-combatant status used by combat dashboards")
    combat_state: Optional[Dict[str, Any]] = Field(default=None, description="Detailed combat persistence snapshot")
    action_breakdown: Optional[Union[List, Dict]] = Field(default=None, description="Structured action breakdown from combat agents")
    turn_resolution: Optional[Union[Dict, List]] = Field(default=None, description="Turn resolution metadata from combat mechanics")
    environmental_conditions: Optional[str] = Field(default="", description="Environmental conditions")
    immediate_threats: Optional[str] = Field(default="", description="Immediate threats to the party")
    story_progression: Optional[str] = Field(default="", description="Story progression notes")
    answer: str = Field(default="Backend did not provide an answer.", description="The main response text")
    # Turn info block (for UI turn indicator)
    turn_info: Optional[Dict[str, Any]] = Field(default=None, description="Turn metadata: id, number, character_id, character_name, actions")
    
    # Image generation fields
    generated_image_url: Optional[str] = Field(default="", description="URL of generated image")
    generated_image_path: Optional[str] = Field(default="", description="Local path of generated image")
    generated_image_prompt: Optional[str] = Field(default="", description="Prompt used for image generation")
    generated_image_type: Optional[str] = Field(default="", description="Type of generated image")
    audio: Optional[AudioArtifactPayload] = Field(default=None, description="Audio narration metadata for client playback")

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""
    message: str = Field(..., description="The user's message")
    session_id: str = Field(default="default-session", description="Session/campaign ID")
    input_type: InputType = Field(default=InputType.CHAT, description="Type of input")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    player_character: Optional[PlayerCharacterContext] = Field(
        default=None,
        description="Active player character context for this message",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "I cast fireball at the goblin horde",
                "session_id": "campaign_123",
                "input_type": "CHAT"
            }
        }
    )


class ExecutionDetails(BaseModel):
    """Details about agent execution."""
    agent_name: Optional[str] = None
    agent_type: Optional[AgentType] = None
    execution_time: Optional[float] = None
    tokens_used: Optional[int] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    items_generated: Optional[int] = None


class MachineResponse(BaseModel):
    """Response from an AI agent."""
    message_id: Optional[str] = Field(default_factory=lambda: None)
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    message_type: MessageType = Field(default=MessageType.MACHINE_RESPONSE)
    agent_name: str = Field(default="Dungeon Master", description="Name of the responding agent")
    agent_type: Optional[AgentType] = Field(default=AgentType.DUNGEON_MASTER)
    structured_data: StructuredGameData
    execution_details: Optional[ExecutionDetails] = None
    thinking_details: Optional[str] = None
    conversation_context: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    success: bool = Field(default=True, description="Whether the request was successful")
    message: MachineResponse = Field(..., description="The agent's response")
    conversation_context: Optional[Dict[str, Any]] = Field(default=None, description="Conversation context")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": {
                    "agent_name": "Dungeon Master",
                    "structured_data": {
                        "narrative": "The fireball explodes in the midst of the goblin horde...",
                        "answer": "Your fireball deals 8d6 damage to all goblins in the area."
                    }
                }
            }
        }
    )


class NewCampaignRequest(BaseModel):
    """Request model for creating a new campaign."""
    blank: bool = Field(default=False, description="Create a blank campaign without intro")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Campaign metadata")


class NewCampaignResponse(BaseModel):
    """Response model for new campaign creation."""
    success: bool = Field(default=True, description="Whether the campaign was created successfully")
    session_id: str = Field(..., description="The new campaign's session ID")
    message: MachineResponse = Field(..., description="The initial campaign message")
    campaign_setup: Optional[Dict[str, Any]] = Field(default=None, description="Campaign setup details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "session_id": "campaign_xyz789",
                "message": {
                    "agent_name": "Dungeon Master",
                    "structured_data": {
                        "narrative": "Welcome to a new adventure...",
                        "answer": "Your journey begins in the tavern of Waterdeep..."
                    }
                }
            }
        }
    )


class AddContextRequest(BaseModel):
    """Request model for adding context to a campaign."""
    context: str = Field(..., description="Context information to add")
    session_id: str = Field(..., description="Campaign session ID")


class AddContextResponse(BaseModel):
    """Response model for adding context."""
    success: bool = Field(default=True, description="Whether context was added successfully")
    message: str = Field(default="Context added successfully", description="Status message")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    success: bool = Field(default=False)
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace for debugging")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error_code": "ORCHESTRATOR_ERROR",
                "error_message": "Failed to process user input",
                "error_details": {"reason": "Model timeout"}
            }
        }
    )
