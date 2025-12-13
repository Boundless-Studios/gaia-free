"""Schema for stats response."""

from typing import Optional, Dict, Any

from pydantic import BaseModel


class StatsResponse(BaseModel):
    """Statistics response."""
    success: bool = True
    current_agent: Optional[str] = None
    total_messages: int = 0
    model_name: Optional[str] = None
    session_duration: float = 0.0
    agent_stats: Optional[Dict[str, Any]] = {}
