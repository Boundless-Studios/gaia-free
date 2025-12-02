"""Non-player character data model."""

from dataclasses import dataclass, field
from typing import Dict, List, Any
from gaia.models.item import Item


@dataclass
class NPCInfo:
    """Non-player character information."""
    npc_id: str
    name: str
    role: str  # merchant, guard, innkeeper, quest_giver, etc.
    description: str = ""
    location: str = ""
    disposition: str = "neutral"  # friendly, neutral, hostile
    dialog_options: List[str] = field(default_factory=list)
    inventory: Dict[str, Item] = field(default_factory=dict)
    quests_offered: List[str] = field(default_factory=list)  # quest_ids
    relationship_level: int = 0  # -100 to 100
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "location": self.location,
            "disposition": self.disposition,
            "dialog_options": self.dialog_options,
            "inventory": {k: v.to_dict() for k, v in self.inventory.items()},
            "quests_offered": self.quests_offered,
            "relationship_level": self.relationship_level,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPCInfo':
        """Create from dictionary."""
        # Convert inventory
        if "inventory" in data:
            data["inventory"] = {k: Item.from_dict(v) if isinstance(v, dict) else v 
                               for k, v in data["inventory"].items()}
        return cls(**data)