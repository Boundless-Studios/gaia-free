"""Item data model."""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Item:
    """Represents an item in the game."""
    item_id: str
    name: str
    quantity: int = 1
    item_type: str = "misc"  # weapon, armor, consumable, quest, misc
    description: str = ""
    value_gp: float = 0.0
    weight_lbs: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)  # magical properties, damage dice, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "quantity": self.quantity,
            "item_type": self.item_type,
            "description": self.description,
            "value_gp": self.value_gp,
            "weight_lbs": self.weight_lbs,
            "properties": self.properties
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """Create from dictionary."""
        return cls(**data)