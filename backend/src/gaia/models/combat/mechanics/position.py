"""Position model for battlefield positioning."""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Position:
    """Position on the battlefield."""
    x: int
    y: int
    z: int = 0  # For flying/elevation

    def distance_to(self, other: 'Position') -> float:
        """Calculate distance to another position."""
        import math
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create Position from dictionary representation.

        Args:
            data: Dictionary containing position data

        Returns:
            Deserialized Position
        """
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            z=data.get("z", 0)
        )