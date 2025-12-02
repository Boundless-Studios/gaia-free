"""Character Info Generator - Generates default values and data for character creation."""

from typing import Dict, Any, List, Optional, Iterable

from gaia.mechanics.character.id_utils import (
    NPC_PREFIX,
    PC_PREFIX,
    allocate_character_id,
)
from gaia.models.character import Ability, VoiceArchetype
from gaia.models.item import Item


class CharacterInfoGenerator:
    """Generates character information, defaults, and derived values."""
    
    @staticmethod
    def generate_character_id(
        simple_char: Dict[str, Any],
        slot_id: Optional[int] = None,
        existing_ids: Optional[Iterable[str]] = None
    ) -> str:
        """Generate a unique character ID.
        
        Args:
            simple_char: Character data dictionary
            slot_id: Optional slot ID for the character (not used in ID generation)
            existing_ids: Optional collection of IDs to ensure uniqueness within
            
        Returns:
            Unique character ID string
        """
        # Use existing character_id if provided (to avoid duplicates)
        if 'character_id' in simple_char:
            return simple_char['character_id']
        
        # Generate a readable ID based on character name
        name = simple_char.get('name', 'unknown')
        # Add pc: or npc: prefix based on character type
        character_type = simple_char.get('character_type', 'player')
        is_npc = simple_char.get('hostile', False) or str(character_type).lower() == 'npc'
        prefix = NPC_PREFIX if is_npc else PC_PREFIX
        return allocate_character_id(name, prefix=prefix, existing_ids=existing_ids)
    
    @staticmethod
    def extract_basic_info(simple_char: Dict[str, Any], slot_id: Optional[int] = None) -> Dict[str, Any]:
        """Extract basic character information from simple character dict.
        
        Args:
            simple_char: Simple character dictionary
            slot_id: Optional slot ID
            
        Returns:
            Dictionary containing basic character info
        """
        return {
            'name': simple_char.get('name', f'Adventurer {slot_id + 1 if slot_id else 1}'),
            'character_class': simple_char.get('character_class', simple_char.get('class', 'Fighter')),
            'race': simple_char.get('race', 'Human'),
            'level': simple_char.get('level', 1)
        }
    
    @staticmethod
    def calculate_hit_points(character_class: str, level: int) -> int:
        """Calculate hit points based on D&D 5e rules.
        
        Args:
            character_class: Character's class
            level: Character's level
            
        Returns:
            Maximum hit points
        """
        hp_by_class = {
            'Barbarian': 12,
            'Fighter': 10, 'Paladin': 10, 'Ranger': 10,
            'Bard': 8, 'Cleric': 8, 'Druid': 8, 'Monk': 8, 'Rogue': 8, 'Warlock': 8,
            'Sorcerer': 6, 'Wizard': 6
        }
        
        # Handle multiclass by taking first class
        base_hp = hp_by_class.get(character_class.split()[0], 8)
        
        # Simple calculation: base HP + (level - 1) * average roll
        return base_hp + (level - 1) * ((base_hp // 2) + 1)
    
    @staticmethod
    def calculate_armor_class(character_class: str) -> int:
        """Calculate armor class based on typical class equipment.
        
        Args:
            character_class: Character's class
            
        Returns:
            Base armor class value
        """
        if character_class in ['Fighter', 'Paladin']:
            return 16  # Assumes chain mail
        elif character_class in ['Ranger', 'Rogue']:
            return 14  # Assumes leather armor + dex
        elif character_class in ['Monk']:
            return 13  # Unarmored defense
        elif character_class in ['Barbarian']:
            return 12  # Unarmored defense
        elif character_class in ['Wizard', 'Sorcerer']:
            return 12  # Mage armor
        else:
            return 10  # Base AC
    
    @staticmethod
    def generate_class_abilities(character_class: str, level: int) -> Dict[str, Ability]:
        """Generate basic abilities based on class and level."""
        abilities = {}
        
        # Add basic attack
        abilities["basic_attack"] = Ability(
            ability_id="basic_attack",
            name="Basic Attack",
            description="Standard weapon attack",
            ability_type="action",
            damage_dice="1d8"
        )
        
        # Add class-specific abilities
        if character_class == "Fighter" and level >= 1:
            abilities["second_wind"] = Ability(
                ability_id="second_wind",
                name="Second Wind",
                description="Regain 1d10 + level hit points",
                ability_type="bonus_action",
                damage_dice=f"1d10+{level}",
                cooldown="short rest"
            )
        elif character_class == "Wizard" and level >= 1:
            abilities["firebolt"] = Ability(
                ability_id="firebolt",
                name="Fire Bolt",
                description="Hurl a mote of fire (1d10 fire damage)",
                ability_type="action",
                damage_dice="1d10"
            )
        elif character_class == "Cleric" and level >= 1:
            abilities["sacred_flame"] = Ability(
                ability_id="sacred_flame",
                name="Sacred Flame",
                description="Radiant flame (1d8 radiant damage)",
                ability_type="action",
                damage_dice="1d8"
            )
        elif character_class == "Rogue" and level >= 1:
            abilities["sneak_attack"] = Ability(
                ability_id="sneak_attack",
                name="Sneak Attack",
                description=f"Deal extra {(level + 1) // 2}d6 damage when you have advantage",
                ability_type="passive",
                damage_dice=f"{(level + 1) // 2}d6"
            )
        
        return abilities
    
    @staticmethod
    def generate_starting_inventory(character_class: str) -> Dict[str, Item]:
        """Generate starting inventory based on class."""
        inventory = {}
        
        # Basic items everyone gets
        inventory["rations"] = Item(
            item_id="rations",
            name="Rations (5 days)",
            item_type="consumable",
            description="Trail rations for 5 days",
            quantity=5
        )
        
        inventory["waterskin"] = Item(
            item_id="waterskin",
            name="Waterskin",
            item_type="consumable",
            description="Leather waterskin",
            quantity=1
        )
        
        # Class-specific items
        if character_class in ["Fighter", "Paladin"]:
            inventory["longsword"] = Item(
                item_id="longsword",
                name="Longsword",
                item_type="weapon",
                description="A versatile blade (1d8 damage)",
                quantity=1,
                properties={"damage": "1d8", "versatile": True}
            )
            inventory["shield"] = Item(
                item_id="shield",
                name="Shield",
                item_type="armor",
                description="Wooden shield (+2 AC)",
                quantity=1,
                properties={"ac_bonus": 2}
            )
        elif character_class in ["Wizard", "Sorcerer"]:
            inventory["quarterstaff"] = Item(
                item_id="quarterstaff",
                name="Quarterstaff",
                item_type="weapon",
                description="A wooden staff (1d6 damage)",
                quantity=1,
                properties={"damage": "1d6"}
            )
            inventory["spellbook"] = Item(
                item_id="spellbook",
                name="Spellbook",
                item_type="misc",
                description="Contains your prepared spells",
                quantity=1
            )
        elif character_class in ["Rogue", "Ranger"]:
            inventory["shortsword"] = Item(
                item_id="shortsword",
                name="Shortsword",
                item_type="weapon",
                description="A quick blade (1d6 damage)",
                quantity=1,
                properties={"damage": "1d6", "finesse": True}
            )
            inventory["shortbow"] = Item(
                item_id="shortbow",
                name="Shortbow",
                item_type="weapon",
                description="Ranged weapon (1d6 damage)",
                quantity=1,
                properties={"damage": "1d6", "range": "80/320"}
            )
        
        return inventory
    
    @staticmethod
    def extract_personality_traits(description: str) -> List[str]:
        """Extract personality traits from description."""
        traits = []
        
        # Simple keyword extraction
        if any(word in description.lower() for word in ['brave', 'courageous', 'fearless']):
            traits.append("Brave and courageous")
        if any(word in description.lower() for word in ['wise', 'intelligent', 'clever']):
            traits.append("Wise and thoughtful")
        if any(word in description.lower() for word in ['strong', 'powerful', 'mighty']):
            traits.append("Strong and determined")
        if any(word in description.lower() for word in ['quick', 'agile', 'nimble']):
            traits.append("Quick and agile")
        if any(word in description.lower() for word in ['kind', 'compassionate', 'caring']):
            traits.append("Kind and compassionate")
        
        # Default trait if none found
        if not traits:
            traits.append("Adventurous spirit")
        
        return traits
    
    @staticmethod
    def generate_visual_description(simple_char: Dict[str, Any]) -> str:
        """Generate a detailed visual description for image generation."""
        name = simple_char.get('name', 'Adventurer')
        character_class = simple_char.get('character_class', simple_char.get('class', 'Fighter'))
        race = simple_char.get('race', 'Human')
        description = simple_char.get('description', '')
        
        # Build visual description
        visual_parts = []
        
        # Race appearance
        race_visuals = {
            'Human': 'human with varied features',
            'Elf': 'elegant elf with pointed ears and graceful features',
            'Dwarf': 'stout dwarf with a thick beard',
            'Halfling': 'small halfling with curly hair',
            'Dragonborn': 'draconic humanoid with scales and reptilian features',
            'Tiefling': 'tiefling with horns and a tail',
            'Half-Orc': 'muscular half-orc with tusks',
            'Gnome': 'small gnome with expressive features',
            'Half-Elf': 'half-elf with slightly pointed ears'
        }
        visual_parts.append(race_visuals.get(race, race.lower()))
        
        # Class appearance
        class_visuals = {
            'Fighter': 'wearing battle-worn armor and carrying weapons',
            'Wizard': 'in flowing robes with arcane symbols, carrying a staff',
            'Cleric': 'in religious vestments with holy symbols',
            'Rogue': 'in dark leather armor with concealed daggers',
            'Ranger': 'in practical traveling gear with a bow',
            'Paladin': 'in shining armor with holy symbols',
            'Barbarian': 'in furs and tribal markings',
            'Sorcerer': 'with magical energy crackling around them',
            'Warlock': 'in dark robes with otherworldly trinkets',
            'Druid': 'in natural garments with nature symbols',
            'Monk': 'in simple robes with a serene expression',
            'Bard': 'in colorful clothes with a musical instrument'
        }
        visual_parts.append(class_visuals.get(character_class.split()[0], 'in adventuring gear'))
        
        # Add custom description if available
        if description:
            visual_parts.append(description)
        
        return f"A {', '.join(visual_parts)}. Fantasy RPG character art."
    
    @staticmethod
    def generate_ability_scores(character_class: str, race: str) -> Dict[str, int]:
        """Generate ability scores based on class and race.
        
        Args:
            character_class: Character's class
            race: Character's race
            
        Returns:
            Dictionary of ability scores
        """
        # Standard array: 15, 14, 13, 12, 10, 8
        # Assign based on class priorities
        class_priorities = {
            'Fighter': {'strength': 15, 'constitution': 14, 'dexterity': 13, 'wisdom': 12, 'charisma': 10, 'intelligence': 8},
            'Wizard': {'intelligence': 15, 'constitution': 14, 'dexterity': 13, 'wisdom': 12, 'charisma': 10, 'strength': 8},
            'Cleric': {'wisdom': 15, 'constitution': 14, 'strength': 13, 'charisma': 12, 'dexterity': 10, 'intelligence': 8},
            'Rogue': {'dexterity': 15, 'intelligence': 14, 'constitution': 13, 'wisdom': 12, 'charisma': 10, 'strength': 8},
            'Ranger': {'dexterity': 15, 'wisdom': 14, 'constitution': 13, 'strength': 12, 'intelligence': 10, 'charisma': 8},
            'Paladin': {'strength': 15, 'charisma': 14, 'constitution': 13, 'wisdom': 12, 'dexterity': 10, 'intelligence': 8},
            'Barbarian': {'strength': 15, 'constitution': 14, 'dexterity': 13, 'wisdom': 12, 'charisma': 10, 'intelligence': 8},
            'Sorcerer': {'charisma': 15, 'constitution': 14, 'dexterity': 13, 'wisdom': 12, 'intelligence': 10, 'strength': 8},
            'Warlock': {'charisma': 15, 'constitution': 14, 'dexterity': 13, 'wisdom': 12, 'intelligence': 10, 'strength': 8},
            'Druid': {'wisdom': 15, 'constitution': 14, 'dexterity': 13, 'intelligence': 12, 'charisma': 10, 'strength': 8},
            'Monk': {'dexterity': 15, 'wisdom': 14, 'constitution': 13, 'strength': 12, 'intelligence': 10, 'charisma': 8},
            'Bard': {'charisma': 15, 'dexterity': 14, 'constitution': 13, 'wisdom': 12, 'intelligence': 10, 'strength': 8}
        }
        
        # Get base scores for class
        base_class = character_class.split()[0]  # Handle multiclass
        scores = class_priorities.get(base_class, {
            'strength': 13, 'dexterity': 12, 'constitution': 14,
            'intelligence': 10, 'wisdom': 11, 'charisma': 10
        })
        
        # Apply racial bonuses (simplified)
        race_bonuses = {
            'Human': {'all': 1},
            'Elf': {'dexterity': 2},
            'Dwarf': {'constitution': 2},
            'Halfling': {'dexterity': 2},
            'Dragonborn': {'strength': 2, 'charisma': 1},
            'Tiefling': {'charisma': 2, 'intelligence': 1},
            'Half-Orc': {'strength': 2, 'constitution': 1},
            'Gnome': {'intelligence': 2},
            'Half-Elf': {'charisma': 2}
        }
        
        bonuses = race_bonuses.get(race, {})
        for ability, bonus in bonuses.items():
            if ability == 'all':
                for key in scores:
                    scores[key] += bonus
            elif ability in scores:
                scores[ability] += bonus
        
        return scores
    
    @staticmethod
    def determine_voice_archetype(character_data: Dict[str, Any]) -> VoiceArchetype:
        """Determine appropriate voice archetype based on character information.
        
        Args:
            character_data: Dictionary containing character information
            
        Returns:
            Appropriate VoiceArchetype
        """
        text_fields = [
            character_data.get('description', ''),
            character_data.get('backstory', ''),
            character_data.get('personality', ''),
            character_data.get('role', ''),
            character_data.get('name', '')
        ]
        combined_text = ' '.join(text_fields).lower()
        
        # Keyword-based archetype detection
        archetype_keywords = {
            VoiceArchetype.VILLAIN: ["villain", "evil", "dark", "sinister", "malevolent", "antagonist", "corrupt"],
            VoiceArchetype.MENTOR: ["mentor", "teacher", "wise", "sage", "master", "guide", "instructor"],
            VoiceArchetype.MERCHANT: ["merchant", "trader", "shop", "vendor", "seller", "bartender", "innkeeper"],
            VoiceArchetype.CHILD: ["child", "young", "kid", "youth", "boy", "girl", "apprentice"],
            VoiceArchetype.ELDER: ["elder", "old", "ancient", "aged", "venerable", "grandfather", "grandmother"],
            VoiceArchetype.CREATURE: ["monster", "beast", "creature", "dragon", "demon", "undead"],
            VoiceArchetype.NARRATOR: ["mystic", "seer", "oracle", "prophet", "diviner", "mysterious", "narrator"],
            VoiceArchetype.HERO: ["hero", "champion", "warrior", "knight", "adventurer", "brave"]
        }
        
        # Count keyword matches for each archetype
        archetype_scores = {}
        for archetype, keywords in archetype_keywords.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            if score > 0:
                archetype_scores[archetype] = score
        
        # Return archetype with highest score
        if archetype_scores:
            return max(archetype_scores.items(), key=lambda x: x[1])[0]
        
        # Check character type for specific defaults
        char_type = character_data.get('character_type', '')
        if char_type == 'creature':
            return VoiceArchetype.CREATURE
        
        # Default based on character class if available
        char_class = character_data.get('character_class', character_data.get('class', '')).lower()
        if any(word in char_class for word in ['wizard', 'mage', 'sorcerer']):
            return VoiceArchetype.ELDER  # Wizards often portrayed as wise elders
        elif any(word in char_class for word in ['cleric', 'priest', 'paladin']):
            return VoiceArchetype.MENTOR
        elif any(word in char_class for word in ['fighter', 'warrior', 'ranger']):
            return VoiceArchetype.HERO
        elif any(word in char_class for word in ['rogue', 'thief', 'assassin']):
            return VoiceArchetype.NARRATOR
        
        # Final default based on character type
        if char_type == 'player':
            return VoiceArchetype.HERO
        
        return VoiceArchetype.NARRATOR
