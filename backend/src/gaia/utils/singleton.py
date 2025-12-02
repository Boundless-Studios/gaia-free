"""Singleton metaclass for ensuring single instances of managers."""

class SingletonMeta(type):
    """
    A thread-safe implementation of Singleton metaclass.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            # Create new instance if it doesn't exist
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
    @classmethod
    def clear_instances(mcs):
        """Clear all singleton instances (useful for testing)."""
        mcs._instances.clear()
    
    @classmethod
    def clear_instance(mcs, cls):
        """Clear a specific singleton instance."""
        if cls in mcs._instances:
            del mcs._instances[cls]