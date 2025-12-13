"""Schema for simple campaign."""

from pydantic import BaseModel


class SimpleCampaign(BaseModel):
    """Simple campaign info for frontend display."""
    title: str
    description: str
    game_style: str = "balanced"
