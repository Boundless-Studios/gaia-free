"""Character Updater - Handles character state updates from various sources."""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

from gaia.models.character import CharacterInfo, CharacterStatus
from gaia.models.item import Item

logger = logging.getLogger(__name__)


class CharacterUpdater:
    """Handles updates to character state from DM responses and other sources."""
    
    def update_from_dm_response(self, character: CharacterInfo, dm_update: Dict[str, Any]) -> CharacterInfo:
        """Update character information based on DM response.
        
        This method processes character updates from the Dungeon Master's responses,
        updating HP, status, inventory, etc.
        
        Args:
            character: The character to update
            dm_update: Dictionary containing character updates from DM
            
        Returns:
            Updated CharacterInfo object
        """
        # Extract character-specific updates if the update contains the character's ID
        if "character_updates" in dm_update:
            char_updates = dm_update["character_updates"].get(character.character_id, {})
            if char_updates:
                self.apply_updates(character, char_updates)
        
        # Narrative-based parsing removed; extractor now manages character resolution

        return character
    
    def apply_updates(self, character: CharacterInfo, updates: Dict[str, Any]) -> CharacterInfo:
        """Apply specific updates to a character.
        
        Args:
            character: The character to update
            updates: Dictionary of updates to apply
            
        Returns:
            Updated CharacterInfo object
        """
        # Update HP
        if "hit_points_current" in updates:
            old_hp = character.hit_points_current
            character.hit_points_current = updates["hit_points_current"]
            logger.info(f"Updated {character.name} HP: {old_hp} -> {character.hit_points_current}/{character.hit_points_max}")
        
        if "hit_points_max" in updates:
            character.hit_points_max = updates["hit_points_max"]
            logger.info(f"Updated {character.name} max HP: {character.hit_points_max}")
        
        # Update status
        if "status" in updates:
            try:
                old_status = character.status
                character.status = CharacterStatus[updates["status"].upper()]
                if old_status != character.status:
                    logger.info(f"Updated {character.name} status: {old_status.value} -> {character.status.value}")
            except KeyError:
                logger.warning(f"Unknown status for {character.name}: {updates['status']}")
        
        # Update inventory
        if "add_item" in updates:
            item_data = updates["add_item"]
            item = self._create_item_from_data(item_data, len(character.inventory))
            character.inventory[item.item_id] = item
            logger.info(f"Added item to {character.name}: {item.name}")
        
        if "add_items" in updates:
            for item_data in updates["add_items"]:
                item = self._create_item_from_data(item_data, len(character.inventory))
                character.inventory[item.item_id] = item
                logger.info(f"Added item to {character.name}: {item.name}")
        
        if "remove_item" in updates:
            item_id = updates["remove_item"]
            if item_id in character.inventory:
                removed_item = character.inventory.pop(item_id)
                logger.info(f"Removed item from {character.name}: {removed_item.name}")
            else:
                logger.warning(f"Tried to remove non-existent item {item_id} from {character.name}")
        
        # Update location
        if "location" in updates:
            old_location = character.location
            character.location = updates["location"]
            if old_location != character.location:
                logger.info(f"Updated {character.name} location: {old_location} -> {character.location}")
        
        # Update level
        if "level" in updates:
            old_level = character.level
            character.level = updates["level"]
            if old_level != character.level:
                logger.info(f"Updated {character.name} level: {old_level} -> {character.level}")
        
        # Update ability scores
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            if ability in updates:
                setattr(character, ability, updates[ability])
                logger.debug(f"Updated {character.name} {ability}: {updates[ability]}")
        
        # Update armor class
        if "armor_class" in updates:
            old_ac = character.armor_class
            character.armor_class = updates["armor_class"]
            if old_ac != character.armor_class:
                logger.info(f"Updated {character.name} AC: {old_ac} -> {character.armor_class}")
        
        # Update interaction tracking
        character.last_interaction = datetime.now()
        character.interaction_count += 1
        
        return character
    
    def parse_status_from_narrative(self, character: CharacterInfo, narrative_text: str) -> CharacterInfo:
        """Parse character status from DM narrative text.
        
        Uses keyword matching to infer character status from narrative descriptions.
        
        Args:
            character: The character to potentially update
            narrative_text: Text describing character status from DM
            
        Returns:
            Updated CharacterInfo object
        """
        # Only parse if character is mentioned in the narrative
        if character.name.lower() not in narrative_text.lower():
            return character
        
        old_status = character.status
        narrative_lower = narrative_text.lower()
        char_name_lower = character.name.lower()
        
        # Find the sentence or phrase containing the character's name
        # This helps avoid false positives from other characters
        sentences = narrative_lower.split('.')
        relevant_text = ' '.join([s for s in sentences if char_name_lower in s])
        
        if not relevant_text:
            relevant_text = narrative_lower
        
        # Check for status keywords in order of severity
        status_keywords = [
            (["dead", "killed", "slain", "deceased", "perished"], CharacterStatus.DEAD),
            (["unconscious", "down", "fallen", "knocked out"], CharacterStatus.UNCONSCIOUS),
            (["poisoned", "sick", "diseased", "afflicted"], CharacterStatus.AFFECTED),
            (["wounded", "injured", "hurt", "bloodied"], CharacterStatus.INJURED),
            (["healed", "recovered", "restored", "healthy"], CharacterStatus.HEALTHY)
        ]
        
        for keywords, status in status_keywords:
            if any(word in relevant_text for word in keywords):
                character.status = status
                if old_status != character.status:
                    logger.info(f"Parsed status change for {character.name}: {old_status.value} -> {character.status.value}")
                break
        
        return character
    
    def apply_combat_damage(self, character: CharacterInfo, damage: int, damage_type: Optional[str] = None) -> CharacterInfo:
        """Apply damage to a character from combat.
        
        Args:
            character: The character taking damage
            damage: Amount of damage to apply
            damage_type: Optional type of damage (fire, cold, etc.)
            
        Returns:
            Updated CharacterInfo object
        """
        old_hp = character.hit_points_current
        character.hit_points_current = max(0, character.hit_points_current - damage)
        
        logger.info(f"{character.name} takes {damage} {damage_type or ''} damage: {old_hp} -> {character.hit_points_current} HP")
        
        # Update status based on HP
        if character.hit_points_current <= 0:
            character.status = CharacterStatus.UNCONSCIOUS
            logger.warning(f"{character.name} has fallen unconscious!")
        elif character.hit_points_current < character.hit_points_max * 0.25:
            if character.status == CharacterStatus.HEALTHY:
                character.status = CharacterStatus.INJURED
                logger.info(f"{character.name} is badly injured!")
        
        return character
    
    def apply_healing(self, character: CharacterInfo, healing: int, source: Optional[str] = None) -> CharacterInfo:
        """Apply healing to a character.
        
        Args:
            character: The character receiving healing
            healing: Amount of healing to apply
            source: Optional source of healing (potion, spell, etc.)
            
        Returns:
            Updated CharacterInfo object
        """
        old_hp = character.hit_points_current
        character.hit_points_current = min(character.hit_points_max, character.hit_points_current + healing)
        
        logger.info(f"{character.name} heals {healing} HP from {source or 'unknown source'}: {old_hp} -> {character.hit_points_current} HP")
        
        # Update status if fully healed
        if character.hit_points_current == character.hit_points_max:
            if character.status in [CharacterStatus.INJURED, CharacterStatus.UNCONSCIOUS]:
                character.status = CharacterStatus.HEALTHY
                logger.info(f"{character.name} is fully healed!")
        elif character.status == CharacterStatus.UNCONSCIOUS and character.hit_points_current > 0:
            character.status = CharacterStatus.INJURED
            logger.info(f"{character.name} regains consciousness but is still injured")
        
        return character
    
    def add_status_effect(self, character: CharacterInfo, effect: str, duration: Optional[int] = None) -> CharacterInfo:
        """Add a status effect to a character.
        
        Args:
            character: The character to affect
            effect: The effect to add (poisoned, blessed, etc.)
            duration: Optional duration in turns
            
        Returns:
            Updated CharacterInfo object
        """
        # This would integrate with the Effect enum from models
        # For now, we'll just update the general status if applicable
        effect_lower = effect.lower()
        
        if any(word in effect_lower for word in ["poison", "disease", "curse"]):
            character.status = CharacterStatus.AFFECTED
            logger.info(f"{character.name} is affected by {effect}")
        
        # Could also add to status_effects list if needed
        # character.status_effects.append(Effect(effect))
        
        return character
    
    def level_up(self, character: CharacterInfo) -> CharacterInfo:
        """Level up a character, increasing stats appropriately.
        
        Args:
            character: The character to level up
            
        Returns:
            Updated CharacterInfo object
        """
        old_level = character.level
        character.level += 1
        
        # Calculate HP increase based on class (simplified)
        hp_increase = self._calculate_hp_increase(character.character_class)
        character.hit_points_max += hp_increase
        character.hit_points_current += hp_increase  # Also heal the new HP
        
        logger.info(f"{character.name} leveled up! {old_level} -> {character.level} (gained {hp_increase} max HP)")
        
        return character
    
    def _create_item_from_data(self, item_data: Dict[str, Any], inventory_size: int) -> Item:
        """Create an Item object from data dictionary.
        
        Args:
            item_data: Dictionary containing item information
            inventory_size: Current size of inventory (for generating IDs)
            
        Returns:
            Item object
        """
        return Item(
            item_id=item_data.get("id", f"item_{inventory_size}"),
            name=item_data.get("name", "Unknown Item"),
            item_type=item_data.get("type", "misc"),
            description=item_data.get("description", ""),
            quantity=item_data.get("quantity", 1),
            properties=item_data.get("properties", {})
        )
    
    def _calculate_hp_increase(self, character_class: str) -> int:
        """Calculate HP increase on level up based on class.
        
        Args:
            character_class: The character's class
            
        Returns:
            HP increase amount
        """
        hp_by_class = {
            'Barbarian': 7,  # 1d12 average
            'Fighter': 6, 'Paladin': 6, 'Ranger': 6,  # 1d10 average
            'Bard': 5, 'Cleric': 5, 'Druid': 5, 'Monk': 5, 'Rogue': 5, 'Warlock': 5,  # 1d8 average
            'Sorcerer': 4, 'Wizard': 4  # 1d6 average
        }
        
        # Handle multiclass by taking first class
        base_class = character_class.split()[0]
        return hp_by_class.get(base_class, 5)  # Default to d8 average
