"""Custom JSON encoder for combat-related objects."""
import json
from typing import Any
from dataclasses import asdict, is_dataclass


class CombatJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles combat dataclasses."""

    def default(self, obj: Any) -> Any:
        """Convert non-JSON serializable objects to serializable format."""
        # Handle dataclasses (including TurnTransitionResult)
        if is_dataclass(obj) and not isinstance(obj, type):
            # Check if object has a to_dict method
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            # Otherwise use asdict
            return asdict(obj)

        # Let the base class default method handle other types
        return super().default(obj)