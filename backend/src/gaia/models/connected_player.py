"""ConnectedPlayer data model - represents a player connected to a session."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConnectedPlayer:
    """Represents a player connected to the session."""
    character_id: str
    character_name: str
    user_id: Optional[str] = None
    seat_id: Optional[str] = None
    is_dm: bool = False
