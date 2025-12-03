"""Campaign data model."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

from gaia.models.game_enums import GameStyle, GameTheme
from gaia.models.npc import NPCInfo
from gaia.models.environment import EnvironmentInfo
from gaia.models.scene_info import SceneInfo
from gaia.models.narrative import NarrativeInfo
from gaia.models.quest import QuestInfo


@dataclass
class CampaignData:
    """Complete campaign data structure."""
    campaign_id: str
    title: str = "Untitled Campaign"
    description: str = ""
    game_style: GameStyle = GameStyle.BALANCED
    game_theme: Optional[GameTheme] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_played: datetime = field(default_factory=datetime.now)
    
    # Core game data - characters are managed separately, we just store IDs
    character_ids: List[str] = field(default_factory=list)  # List of character IDs in the campaign
    npcs: Dict[str, NPCInfo] = field(default_factory=dict)
    environments: Dict[str, EnvironmentInfo] = field(default_factory=dict)
    scenes: Dict[str, SceneInfo] = field(default_factory=dict)
    scene_order: List[str] = field(default_factory=list)  # Ordered list of scene_ids
    narratives: List[NarrativeInfo] = field(default_factory=list)
    quests: Dict[str, QuestInfo] = field(default_factory=dict)
    
    # Current state
    current_scene_id: Optional[str] = None
    current_location_id: Optional[str] = None
    active_quest_ids: List[str] = field(default_factory=list)

    # Turn order management (campaign-level)
    turn_order: List[str] = field(default_factory=list)  # Character IDs in turn order
    current_turn_index: int = 0  # Current position in turn order
    
    # Session tracking
    total_sessions: int = 0
    total_playtime_hours: float = 0.0
    
    # Additional metadata
    tags: Dict[str, str] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "campaign_id": self.campaign_id,
            "title": self.title,
            "description": self.description,
            "game_style": self.game_style.value,
            "game_theme": self.game_theme.value if self.game_theme else None,
            "created_at": self.created_at.isoformat(),
            "last_played": self.last_played.isoformat(),
            "character_ids": self.character_ids,
            "npcs": {k: v.to_dict() for k, v in self.npcs.items()},
            "environments": {k: v.to_dict() for k, v in self.environments.items()},
            "scenes": {k: v.to_dict() for k, v in self.scenes.items()},
            "scene_order": self.scene_order,
            "narratives": [n.to_dict() for n in self.narratives],
            "quests": {k: v.to_dict() for k, v in self.quests.items()},
            "current_scene_id": self.current_scene_id,
            "current_location_id": self.current_location_id,
            "active_quest_ids": self.active_quest_ids,
            "turn_order": self.turn_order,
            "current_turn_index": self.current_turn_index,
            "total_sessions": self.total_sessions,
            "total_playtime_hours": self.total_playtime_hours,
            "tags": self.tags,
            "custom_data": self.custom_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CampaignData':
        """Create from dictionary."""
        # Convert string dates to datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("last_played"), str):
            data["last_played"] = datetime.fromisoformat(data["last_played"])
        
        # Convert game style
        if isinstance(data.get("game_style"), str):
            data["game_style"] = GameStyle(data["game_style"])
        
        # Convert game theme
        if data.get("game_theme") and isinstance(data.get("game_theme"), str):
            data["game_theme"] = GameTheme(data["game_theme"])
        
        # Character IDs are just a list of strings, no conversion needed
        if "npcs" in data:
            data["npcs"] = {k: NPCInfo.from_dict(v) for k, v in data["npcs"].items()}
        if "environments" in data:
            data["environments"] = {k: EnvironmentInfo.from_dict(v) for k, v in data["environments"].items()}
        if "scenes" in data:
            data["scenes"] = {k: SceneInfo.from_dict(v) for k, v in data["scenes"].items()}
        if "narratives" in data:
            data["narratives"] = [NarrativeInfo.from_dict(n) for n in data["narratives"]]
        if "quests" in data:
            data["quests"] = {k: QuestInfo.from_dict(v) for k, v in data["quests"].items()}
        
        return cls(**data)
    
    def add_character_id(self, character_id: str):
        """Add a character ID reference."""
        if character_id not in self.character_ids:
            self.character_ids.append(character_id)
    
    def add_npc(self, npc: NPCInfo):
        """Add or update an NPC."""
        self.npcs[npc.npc_id] = npc
    
    def add_environment(self, environment: EnvironmentInfo):
        """Add or update an environment."""
        self.environments[environment.location_id] = environment
    
    def add_scene(self, scene: SceneInfo):
        """Add or update a scene."""
        self.scenes[scene.scene_id] = scene
        if scene.scene_id not in self.scene_order:
            self.scene_order.append(scene.scene_id)
        self.current_scene_id = scene.scene_id
        if scene.location_id:
            self.current_location_id = scene.location_id
    
    def add_narrative(self, narrative: NarrativeInfo):
        """Add a narrative entry."""
        self.narratives.append(narrative)
    
    def add_quest(self, quest: QuestInfo):
        """Add or update a quest."""
        self.quests[quest.quest_id] = quest
        if quest.status == "active" and quest.quest_id not in self.active_quest_ids:
            self.active_quest_ids.append(quest.quest_id)
    
    def update_session_stats(self, session_duration_hours: float):
        """Update session statistics."""
        self.total_sessions += 1
        self.total_playtime_hours += session_duration_hours
        self.last_played = datetime.now()

    def get_scene_storage_mode(self) -> str:
        """Get the scene storage mode for this campaign.

        Returns:
            "database" or "filesystem"

        Default behavior:
        - New campaigns without this setting: "database" (preferred)
        - Existing campaigns: "filesystem" (backwards compatibility)
        """
        if not self.custom_data:
            # No custom_data means old campaign, use filesystem for backwards compat
            return "filesystem"

        # Check if mode is explicitly set
        mode = self.custom_data.get("scene_storage_mode")
        if mode in ("database", "filesystem"):
            return mode

        # Not set - determine based on whether campaign has existing scenes
        # If campaign has scenes dict populated, it's using filesystem
        if self.scenes:
            return "filesystem"

        # New campaign, use database by default
        return "database"

    def set_scene_storage_mode(self, mode: str) -> None:
        """Set the scene storage mode for this campaign.

        Args:
            mode: "database" or "filesystem"

        Raises:
            ValueError: If mode is invalid
        """
        if mode not in ("database", "filesystem"):
            raise ValueError(f"Invalid scene_storage_mode: {mode}. Must be 'database' or 'filesystem'")

        if not self.custom_data:
            self.custom_data = {}

        self.custom_data["scene_storage_mode"] = mode