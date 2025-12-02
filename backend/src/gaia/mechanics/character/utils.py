"""Utility functions for character management."""

from typing import Any, Dict, Optional, TypeVar, Type
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CharacterDataConverter:
    """Utility class for converting between dictionaries and objects."""
    
    @staticmethod
    def to_dict(obj: Any) -> Dict[str, Any]:
        """Convert an object to a dictionary.
        
        Handles objects with to_dict() method, __dict__ attribute, or returns as-is if already a dict.
        
        Args:
            obj: Object to convert
            
        Returns:
            Dictionary representation of the object
        """
        if obj is None:
            return {}
        
        if isinstance(obj, dict):
            return obj
        
        if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
            try:
                return obj.to_dict()
            except Exception as e:
                logger.warning(f"Failed to call to_dict() on {type(obj).__name__}: {e}")
        
        if hasattr(obj, '__dict__'):
            return obj.__dict__.copy()
        
        # Fallback for basic types
        return {'value': obj}
    
    @staticmethod
    def from_dict(data: Dict[str, Any], target_class: Optional[Type[T]] = None) -> T:
        """Convert a dictionary to an object.
        
        Handles classes with from_dict() method or direct instantiation.
        
        Args:
            data: Dictionary to convert
            target_class: Optional target class to instantiate
            
        Returns:
            Instance of target_class or the original data if no class provided
        """
        if target_class is None:
            return data
        
        # Clean up data for CharacterInfo specifically
        if target_class.__name__ == 'CharacterInfo':
            # Remove fields that CharacterStorage adds but CharacterInfo doesn't expect
            clean_data = data.copy()
            clean_data.pop('id', None)  # Remove 'id' field added by storage
            clean_data.pop('last_modified', None)  # Remove metadata
            clean_data.pop('campaigns', None)  # Remove campaign tracking
            clean_data.pop('last_campaign', None)  # Remove campaign tracking
            data = clean_data
        
        if hasattr(target_class, 'from_dict') and callable(getattr(target_class, 'from_dict')):
            try:
                return target_class.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to call from_dict() on {target_class.__name__}: {e}")
        
        # Try direct instantiation
        try:
            return target_class(**data)
        except Exception as e:
            logger.error(f"Failed to instantiate {target_class.__name__} from dict: {e}")
            return data
    
    @staticmethod
    def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely get a value from a dictionary with a default.
        
        Args:
            data: Dictionary to get value from
            key: Key to look up
            default: Default value if key not found
            
        Returns:
            Value from dictionary or default
        """
        if not isinstance(data, dict):
            return default
        return data.get(key, default)
    
    @staticmethod
    def merge_dicts(base: Dict[str, Any], updates: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
        """Merge two dictionaries.
        
        Args:
            base: Base dictionary
            updates: Dictionary with updates
            deep: Whether to perform deep merge for nested dicts
            
        Returns:
            Merged dictionary (new instance)
        """
        result = base.copy()
        
        if not deep:
            result.update(updates)
            return result
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = CharacterDataConverter.merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value
        
        return result


class PathResolver:
    """Utility for resolving character storage paths."""
    
    def __init__(self, campaign_id: str):
        """Initialize path resolver.
        
        Args:
            campaign_id: Campaign identifier
        """
        self.campaign_id = campaign_id
        self._campaign_manager = None
    
    @property
    def campaign_manager(self):
        """Lazy load campaign manager to avoid circular imports."""
        if self._campaign_manager is None:
            from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
            self._campaign_manager = SimpleCampaignManager()
        return self._campaign_manager
    
    def get_characters_path(self):
        """Get the path to the campaign's characters directory.
        
        Returns:
            Path object or None if not available
        """
        return self.campaign_manager.get_campaign_characters_path(self.campaign_id)
    
    def get_character_file_path(self, character_id: str):
        """Get the path to a specific character file.
        
        Args:
            character_id: Character identifier
            
        Returns:
            Path object or None if not available
        """
        characters_path = self.get_characters_path()
        if characters_path:
            return characters_path / f"{character_id}.json"
        return None