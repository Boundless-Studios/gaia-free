"""Schema for base message."""

from datetime import datetime

from pydantic import BaseModel


class BaseMessage(BaseModel):
    """Base message class."""
    message_id: str
    timestamp: datetime
    session_id: str
    message_type: str
