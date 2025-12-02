"""Core character information data model."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

from gaia.models.character.enums import (
    CharacterStatus,
    Effect,
    CharacterRole,
    CharacterCapability,
)
from gaia.models.character.ability import Ability
from gaia.models.item import Item
from gaia.models.combat.mechanics.action_points import ActionPointState, ActionPointConfig
from gaia.models.combat import CombatStats


@dataclass
class CharacterInfo:
    """Detailed character information."""
    character_id: str
    name: str
    character_class: str
    level: int = 1
    race: str = "human"
    alignment: str = "neutral"
    hit_points_current: int = 10
    hit_points_max: int = 10
    armor_class: int = 10
    status: CharacterStatus = CharacterStatus.HEALTHY
    status_effects: List[Effect] = field(default_factory=list)
    inventory: Dict[str, Item] = field(default_factory=dict)
    abilities: Dict[str, Ability] = field(default_factory=dict)
    backstory: str = ""
    personality_traits: List[str] = field(default_factory=list)
    bonds: List[str] = field(default_factory=list)
    flaws: List[str] = field(default_factory=list)
    dialog_history: List[Dict[str, str]] = field(default_factory=list)
    quests: List[str] = field(default_factory=list)  # quest_ids
    location: Optional[str] = None
    
    # Character tracking extensions
    character_type: str = "player"  # player, npc, creature
    character_role: CharacterRole = CharacterRole.PLAYER
    capabilities: CharacterCapability = CharacterCapability.NONE
    description: str = ""  # Physical and personality description
    appearance: str = ""  # Visual appearance for consistency
    visual_description: str = ""  # Detailed appearance for image generation
    voice_id: Optional[str] = None  # ElevenLabs voice ID
    voice_settings: Dict[str, Any] = field(default_factory=dict)  # Speed, pitch, etc
    first_appearance: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    
    # Ability scores
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    # Combat-related fields
    action_points: Optional[ActionPointState] = None
    combat_stats: Optional[CombatStats] = None
    initiative_modifier: int = 0

    # Portrait and visual customization fields
    portrait_url: Optional[str] = None  # URL to generated portrait image
    portrait_path: Optional[str] = None  # Local file path to portrait
    portrait_prompt: Optional[str] = None  # Enhanced prompt used for generation

    # Basic identity (gender is NEW - added for portrait generation)
    gender: Optional[str] = None  # Male, Female, Non-binary

    # Visual appearance metadata
    age_category: Optional[str] = None  # Young, Adult, Middle-aged, Elderly
    build: Optional[str] = None  # Slender, Athletic, Muscular, Stocky, Heavyset
    height_description: Optional[str] = None  # tall, average height, short, etc.
    facial_expression: Optional[str] = None  # Confident, Serene, Determined, etc.
    facial_features: Optional[str] = None  # Distinguishing facial characteristics
    attire: Optional[str] = None  # Clothing and armor description
    primary_weapon: Optional[str] = None  # Main weapon/item
    distinguishing_feature: Optional[str] = None  # Most unique visual element
    background_setting: Optional[str] = None  # Environmental context
    pose: Optional[str] = None  # Character pose/action
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "character_id": self.character_id,
            "name": self.name,
            "character_class": self.character_class,
            "level": self.level,
            "race": self.race,
            "alignment": self.alignment,
            "hit_points_current": self.hit_points_current,
            "hit_points_max": self.hit_points_max,
            "armor_class": self.armor_class,
            "status": self.status.value,
            "status_effects": [effect.value for effect in self.status_effects],
            "inventory": {k: v.to_dict() for k, v in self.inventory.items()},
            "abilities": {k: v.to_dict() for k, v in self.abilities.items()},
            "backstory": self.backstory,
            "personality_traits": self.personality_traits,
            "bonds": self.bonds,
            "flaws": self.flaws,
            "dialog_history": self.dialog_history,
            "quests": self.quests,
            "location": self.location,
            "character_type": self.character_type,
            "character_role": self.character_role.value,
            "capabilities": int(self.capabilities),
            "description": self.description,
            "appearance": self.appearance,
            "visual_description": self.visual_description,
            "voice_id": self.voice_id,
            "voice_settings": self.voice_settings,
            "first_appearance": self.first_appearance.isoformat() if self.first_appearance else None,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None,
            "interaction_count": self.interaction_count,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
            "action_points": self.action_points.to_dict() if self.action_points else None,
            "combat_stats": self.combat_stats.to_dict() if self.combat_stats else None,
            "initiative_modifier": self.initiative_modifier,
            # Portrait and visual fields
            "portrait_url": self.portrait_url,
            "portrait_path": self.portrait_path,
            "portrait_prompt": self.portrait_prompt,
            "gender": self.gender,
            "age_category": self.age_category,
            "build": self.build,
            "height_description": self.height_description,
            "facial_expression": self.facial_expression,
            "facial_features": self.facial_features,
            "attire": self.attire,
            "primary_weapon": self.primary_weapon,
            "distinguishing_feature": self.distinguishing_feature,
            "background_setting": self.background_setting,
            "pose": self.pose
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterInfo':
        """Create from dictionary."""
        # Convert status
        status = CharacterStatus(data.get("status", "healthy"))
        data["status"] = status

        # Convert role/capabilities
        # TODO Overly defensive? character_role/capabilities should always be the correct type, we should add a helper within CharacterRole / Capability to 
        # deserialize with a safe default
        
        role_value = data.get("character_role")
        if isinstance(role_value, CharacterRole):
            data["character_role"] = role_value
        elif isinstance(role_value, str):
            try:
                data["character_role"] = CharacterRole(role_value)
            except ValueError:
                data["character_role"] = CharacterRole.PLAYER
        else:
            data["character_role"] = CharacterRole.PLAYER

        capabilities_value = data.get("capabilities")
        if isinstance(capabilities_value, CharacterCapability):
            data["capabilities"] = capabilities_value
        elif isinstance(capabilities_value, int):
            data["capabilities"] = CharacterCapability(capabilities_value)
        elif isinstance(capabilities_value, list):
            flag = CharacterCapability.NONE
            for item in capabilities_value:
                if isinstance(item, str):
                    try:
                        flag |= CharacterCapability[item.upper()]
                    except KeyError:
                        continue
                elif isinstance(item, int):
                    flag |= CharacterCapability(item)
            data["capabilities"] = flag
        else:
            data["capabilities"] = CharacterCapability.NONE
        
        # Convert status effects
        if "status_effects" in data:
            data["status_effects"] = [Effect(effect) if isinstance(effect, str) else effect 
                                     for effect in data["status_effects"]]
        
        # Convert inventory
        if "inventory" in data:
            data["inventory"] = {k: Item.from_dict(v) if isinstance(v, dict) else v 
                               for k, v in data["inventory"].items()}
        
        # Convert abilities
        if "abilities" in data:
            data["abilities"] = {k: Ability.from_dict(v) if isinstance(v, dict) else v 
                               for k, v in data["abilities"].items()}
        
        # Convert datetime fields
        if "first_appearance" in data and data["first_appearance"]:
            if isinstance(data["first_appearance"], str):
                data["first_appearance"] = datetime.fromisoformat(data["first_appearance"])
        if "last_interaction" in data and data["last_interaction"]:
            if isinstance(data["last_interaction"], str):
                data["last_interaction"] = datetime.fromisoformat(data["last_interaction"])

        # Convert combat-related fields
        if "action_points" in data and data["action_points"]:
            if isinstance(data["action_points"], dict):
                from core.models.combat.mechanics.action_points import ActionPointState
                data["action_points"] = ActionPointState(**data["action_points"])

        if "combat_stats" in data and data["combat_stats"]:
            if isinstance(data["combat_stats"], dict):
                from core.models.combat import CombatStats
                data["combat_stats"] = CombatStats(**data["combat_stats"])

        return cls(**data)

    @classmethod
    def from_combatant_info(cls, combatant_info, entry_dict: Optional[Dict] = None) -> 'CharacterInfo':
        """Create CharacterInfo from CombatantInfo for NPCs.

        Args:
            combatant_info: CombatantInfo object with NPC data
            entry_dict: Optional dictionary with additional data

        Returns:
            CharacterInfo instance for the NPC
        """
        import uuid

        name = combatant_info.name if combatant_info else entry_dict.get('name', 'Unknown')
        slug = name.lower().replace(' ', '_')
        npc_id = f"npc_{slug}_{uuid.uuid4().hex[:4]}"

        hp_max = combatant_info.hp_max if combatant_info and combatant_info.hp_max is not None else 12
        hp_current = combatant_info.hp_current if combatant_info and combatant_info.hp_current is not None else hp_max
        armor_class = combatant_info.armor_class if combatant_info and combatant_info.armor_class is not None else 13
        npc_level = combatant_info.level if combatant_info and combatant_info.level is not None else entry_dict.get('level', 1) if entry_dict else 1
        npc_class = combatant_info.class_or_creature if combatant_info else entry_dict.get('class_or_creature', 'Enemy') if entry_dict else 'Enemy'

        return cls(
            character_id=npc_id,
            name=name,
            character_class=npc_class or 'Enemy',
            level=npc_level or 1,
            character_type='creature',
            hit_points_current=hp_current,
            hit_points_max=hp_max,
            armor_class=armor_class,
            race='creature'
        )
