"""Simple scene storage manager for D&D campaigns."""

import json
import os
from datetime import datetime
from typing import List, Optional
import logging

class SimpleSceneManager:
    """Simple manager for storing Scene Creator outputs as strings."""
    
    def __init__(self, campaign_id: str = "default"):
        self.campaign_id = campaign_id
        # Get environment name from environment variable
        self.environment_name = os.getenv('ENVIRONMENT_NAME', 'default')
        
        # Get campaign storage path from environment (required)
        campaign_storage = os.getenv('CAMPAIGN_STORAGE_PATH')
        if not campaign_storage:
            raise ValueError(
                "CAMPAIGN_STORAGE_PATH environment variable is not set. "
                "Please set it to your campaign storage directory."
            )
        base_path = os.path.join(campaign_storage, 'campaigns')
        
        # Use the campaigns structure with environment
        self.scenes_dir = os.path.join(base_path, self.environment_name, campaign_id, 'data', 'scenes')
        self.logger = logging.getLogger(__name__)
        
        # Ensure directory exists
        os.makedirs(self.scenes_dir, exist_ok=True)
    
    def store_scene(self, scene_output: str, scene_id: Optional[str] = None) -> str:
        """Store a scene creator output as a string."""
        if scene_id is None:
            scene_id = f"scene_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        scene_data = {
            "id": scene_id,
            "timestamp": datetime.now().isoformat(),
            "output": scene_output
        }
        
        filepath = os.path.join(self.scenes_dir, f"{scene_id}.json")
        with open(filepath, 'w') as f:
            json.dump(scene_data, f, indent=2)
        
        self.logger.info(f"🎭 Stored scene: {scene_id}")
        return scene_id
    
    def get_recent_scenes(self, limit: int = 5) -> List[str]:
        """Get recent scene outputs for DM context."""
        try:
            scene_files = []
            for filename in os.listdir(self.scenes_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.scenes_dir, filename)
                    with open(filepath, 'r') as f:
                        scene_data = json.load(f)
                        scene_files.append((scene_data['timestamp'], scene_data['output']))
            
            # Sort by timestamp (most recent first) and return outputs
            scene_files.sort(key=lambda x: x[0], reverse=True)
            return [output for _, output in scene_files[:limit]]
            
        except Exception as e:
            self.logger.error(f"Error retrieving scenes: {e}")
            return []
    
    def get_recent_scenes_as_string(self, limit: int = 3) -> str:
        """Get formatted scene context for DM."""
        recent_scenes = self.get_recent_scenes(limit)
        if not recent_scenes:
            return ""
        
        context = "Recent scene context:\n"
        for i, scene in enumerate(recent_scenes, 1):
            context += f"\n--- Scene {i} ---\n{scene}\n"
        
        return context 