"""Schema for simple character."""

from typing import Optional

from pydantic import BaseModel


class SimpleCharacter(BaseModel):
    """Simple character representation for frontend display."""
    name: str
    character_class: str
    race: str
    level: int = 1
    description: Optional[str] = ""
    backstory: Optional[str] = ""
