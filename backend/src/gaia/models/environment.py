"""Environment and location data model."""

from dataclasses import dataclass, field
from typing import Dict, List, Any
from gaia.models.item import Item


@dataclass
class EnvironmentInfo:
    """Environment and location information."""
    location_id: str
    name: str
    description: str
    environment_type: str  # dungeon, forest, city, tavern, etc.
    weather: str = "clear"
    time_of_day: str = "day"
    visibility: str = "normal"  # normal, dim, dark
    hazards: List[str] = field(default_factory=list)
    points_of_interest: List[str] = field(default_factory=list)
    connected_locations: List[str] = field(default_factory=list)
    npcs_present: List[str] = field(default_factory=list)  # npc_ids
    items_available: Dict[str, Item] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "environment_type": self.environment_type,
            "weather": self.weather,
            "time_of_day": self.time_of_day,
            "visibility": self.visibility,
            "hazards": self.hazards,
            "points_of_interest": self.points_of_interest,
            "connected_locations": self.connected_locations,
            "npcs_present": self.npcs_present,
            "items_available": {k: v.to_dict() for k, v in self.items_available.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnvironmentInfo':
        """Create from dictionary."""
        # Convert items_available
        if "items_available" in data:
            data["items_available"] = {k: Item.from_dict(v) if isinstance(v, dict) else v 
                                     for k, v in data["items_available"].items()}
        return cls(**data)