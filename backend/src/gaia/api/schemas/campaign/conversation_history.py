"""Schema for conversation history."""

from typing import List
from datetime import datetime

from pydantic import BaseModel

from gaia.api.schemas.campaign.conversation_message import ConversationMessage


class ConversationHistory(BaseModel):
    """Complete conversation history for a session."""
    session_id: str
    messages: List[ConversationMessage]
    total_messages: int
    session_started: datetime
    last_activity: datetime
