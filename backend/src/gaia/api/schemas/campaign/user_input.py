"""Schema for user input."""

from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel


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
