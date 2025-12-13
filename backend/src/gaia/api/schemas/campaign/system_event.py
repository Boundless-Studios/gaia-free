"""Schema for system event."""

from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel


class SystemEvent(BaseModel):
    """System event message."""
    message_id: str
    timestamp: datetime
    session_id: str
    message_type: str = "SYSTEM_EVENT"
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    severity: Optional[str] = "info"
