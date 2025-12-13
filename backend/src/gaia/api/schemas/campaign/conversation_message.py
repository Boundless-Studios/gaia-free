"""Schema for conversation message."""

from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel


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
