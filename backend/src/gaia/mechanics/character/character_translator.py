"""Character Translator - Converts between different character representations."""

from typing import Dict, Any, Optional
from datetime import datetime

from gaia.models.character import CharacterInfo, CharacterStatus
from gaia.mechanics.character.character_info_generator import CharacterInfoGenerator


class CharacterTranslator:
    """Handles translation between different character representations.
    
    This class focuses purely on converting between different data formats,
    while generation of defaults and derived values is handled by CharacterInfoGenerator.
    """
    
    def __init__(self):
        """Initialize the translator with a generator instance."""
        self.generator = CharacterInfoGenerator()
    
    def simple_to_character_info(self, simple_char: Dict[str, Any], slot_id: Optional[int] = None) -> CharacterInfo:
        """Convert a simple character dict to a full CharacterInfo object.
        
        Args:
            simple_char: Simple character dict with basic fields (name, class, race, etc.)
            slot_id: Optional slot ID for generating defaults
            
        Returns:
            Complete CharacterInfo object
        """
        # Generate character ID
        character_id = self.generator.generate_character_id(simple_char, slot_id)
        
        # Extract basic info with defaults
        basic_info = self.generator.extract_basic_info(simple_char, slot_id)
        
        # Generate derived values
        max_hp = self.generator.calculate_hit_points(
            basic_info['character_class'], 
            basic_info['level']
        )
        base_ac = self.generator.calculate_armor_class(basic_info['character_class'])
        
        # Generate abilities and inventory
        abilities = self.generator.generate_class_abilities(
            basic_info['character_class'], 
            basic_info['level']
        )
        inventory = self.generator.generate_starting_inventory(basic_info['character_class'])
        
        # Generate ability scores if not provided
        if 'strength' not in simple_char:
            ability_scores = self.generator.generate_ability_scores(
                basic_info['character_class'],
                basic_info['race']
            )
        else:
            ability_scores = {
                'strength': simple_char.get('strength', 10),
                'dexterity': simple_char.get('dexterity', 10),
                'constitution': simple_char.get('constitution', 10),
                'intelligence': simple_char.get('intelligence', 10),
                'wisdom': simple_char.get('wisdom', 10),
                'charisma': simple_char.get('charisma', 10)
            }
        
        # Generate personality and visual descriptions
        personality_traits = self.generator.extract_personality_traits(
            simple_char.get('description', '')
        )
        visual_description = self.generator.generate_visual_description(simple_char)

        # Apply defaults for appearance fields if not provided
        # These defaults match the CharacterGeneratorOutput model
        appearance_defaults = {
            'gender': 'non-binary',
            'age_category': 'adult',
            'build': 'average',
            'height_description': 'average height',
            'facial_expression': 'determined',
            'pose': 'standing confidently'
        }

        # Create CharacterInfo object
        character_info = CharacterInfo(
            character_id=character_id,
            name=basic_info['name'],
            character_class=basic_info['character_class'],
            level=basic_info['level'],
            race=basic_info['race'],
            alignment=simple_char.get('alignment', 'neutral good'),
            hit_points_current=simple_char.get('hit_points_current', max_hp),
            hit_points_max=simple_char.get('hit_points_max', max_hp),
            armor_class=simple_char.get('armor_class', base_ac),
            status=CharacterStatus.HEALTHY,
            status_effects=[],
            inventory=inventory,
            abilities=abilities,
            backstory=simple_char.get('backstory', ''),
            personality_traits=personality_traits,
            bonds=simple_char.get('bonds', []),
            flaws=simple_char.get('flaws', []),
            dialog_history=[],
            quests=simple_char.get('quests', []),
            location=simple_char.get('location'),
            character_type=simple_char.get('character_type', 'player'),
            description=simple_char.get('description', ''),
            appearance=simple_char.get('appearance', ''),
            visual_description=visual_description,
            voice_id=simple_char.get('voice_id'),
            voice_settings=simple_char.get('voice_settings', {}),
            # Visual metadata for portrait generation - apply defaults if None/empty
            gender=simple_char.get('gender') or appearance_defaults['gender'],
            age_category=simple_char.get('age_category') or appearance_defaults['age_category'],
            build=simple_char.get('build') or appearance_defaults['build'],
            height_description=simple_char.get('height_description') or appearance_defaults['height_description'],
            facial_expression=simple_char.get('facial_expression') or appearance_defaults['facial_expression'],
            facial_features=simple_char.get('facial_features'),
            attire=simple_char.get('attire'),
            primary_weapon=simple_char.get('primary_weapon'),
            distinguishing_feature=simple_char.get('distinguishing_feature'),
            background_setting=simple_char.get('background_setting'),
            pose=simple_char.get('pose') or appearance_defaults['pose'],
            # Portrait data
            portrait_url=simple_char.get('portrait_url'),
            portrait_path=simple_char.get('portrait_path'),
            portrait_prompt=simple_char.get('portrait_prompt'),
            first_appearance=datetime.now(),
            last_interaction=datetime.now(),
            interaction_count=0,
            **ability_scores  # Unpack ability scores
        )
        
        return character_info
    
    def character_info_to_simple(self, character: CharacterInfo) -> Dict[str, Any]:
        """Convert a CharacterInfo object to a simple dictionary.
        
        Args:
            character: CharacterInfo object to convert
            
        Returns:
            Simple dictionary representation
        """
        return {
            'character_id': character.character_id,
            'name': character.name,
            'character_class': character.character_class,
            'class': character.character_class,  # Alias for compatibility
            'level': character.level,
            'race': character.race,
            'alignment': character.alignment,
            'hit_points_current': character.hit_points_current,
            'hit_points_max': character.hit_points_max,
            'armor_class': character.armor_class,
            'backstory': character.backstory,
            'description': character.description,
            'voice_id': character.voice_id,
            'strength': character.strength,
            'dexterity': character.dexterity,
            'constitution': character.constitution,
            'intelligence': character.intelligence,
            'wisdom': character.wisdom,
            'charisma': character.charisma
        }
    
    def update_from_dm_response(self, character: CharacterInfo, updates: Dict[str, Any]) -> CharacterInfo:
        """Update a CharacterInfo object based on DM response data.
        
        Args:
            character: Existing CharacterInfo to update
            updates: Dictionary of updates from DM response
            
        Returns:
            Updated CharacterInfo object
        """
        # Update HP if provided
        if 'hit_points_current' in updates:
            character.hit_points_current = updates['hit_points_current']
        
        # Update status if provided
        if 'status' in updates:
            try:
                character.status = CharacterStatus[updates['status'].upper()]
            except KeyError:
                pass  # Invalid status, ignore
        
        # Update location if provided
        if 'location' in updates:
            character.location = updates['location']
        
        # Update interaction tracking
        character.last_interaction = datetime.now()
        character.interaction_count += 1
        
        return character
    
    def merge_with_profile(self, character: CharacterInfo, profile_data: Dict[str, Any]) -> CharacterInfo:
        """Merge character info with profile data.
        
        Args:
            character: CharacterInfo object
            profile_data: Profile data to merge
            
        Returns:
            Updated CharacterInfo with profile data
        """
        if 'voice_id' in profile_data:
            character.voice_id = profile_data['voice_id']
        
        if 'voice_settings' in profile_data:
            character.voice_settings = profile_data['voice_settings']
        
        if 'appearance' in profile_data:
            character.appearance = profile_data['appearance']
        
        return character