"""Arena combat setup module."""

import logging
from typing import List, Dict, Any

from gaia.models.scene_info import SceneInfo
from gaia.models.scene_participant import SceneParticipant
from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.character import CharacterInfo

logger = logging.getLogger(__name__)


def create_arena_characters() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Create predefined arena characters (PCs and NPCs).

    Returns:
        Tuple of (player_characters, npc_characters)
    """
    arena_characters = [
        {
            "name": "Marcus the Gladiator",
            "race": "Human",
            "class": "Fighter",
            "level": 5,
            "background": "Experienced arena champion with sword and shield",
            "abilities": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10}
        },
        {
            "name": "Lyra the Swift",
            "race": "Elf",
            "class": "Rogue",
            "level": 5,
            "background": "Agile arena combatant with dual short swords",
            "abilities": {"STR": 10, "DEX": 16, "CON": 12, "INT": 14, "WIS": 12, "CHA": 10}
        }
    ]

    arena_npcs = [
        {
            "name": "Gorak the Brutal",
            "race": "Half-Orc",
            "class": "Barbarian",
            "level": 5,
            "background": "Savage arena warrior wielding a massive greataxe",
            "abilities": {"STR": 18, "DEX": 12, "CON": 16, "INT": 8, "WIS": 10, "CHA": 8},
            "hit_points_max": 58,
            "hit_points_current": 58,
            "armor_class": 14,
            "hostile": True
        },
        {
            "name": "Theron the Mystic",
            "race": "Human",
            "class": "Wizard",
            "level": 5,
            "background": "Cunning arena spellcaster using combat magic and illusions",
            "abilities": {"STR": 8, "DEX": 14, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
            "hit_points_max": 32,
            "hit_points_current": 32,
            "armor_class": 15,
            "hostile": True
        }
    ]

    return arena_characters, arena_npcs


def create_arena_scene(
    campaign_id: str,
    all_combatants: List[CharacterInfo],
    difficulty: str = "medium"
) -> SceneInfo:
    """Create the hardcoded arena scene with proper character roster.

    Args:
        campaign_id: Campaign identifier
        all_combatants: All created characters (PCs and NPCs)
        difficulty: Arena difficulty level

    Returns:
        SceneInfo object for the arena
    """
    # Separate PCs and NPCs from created characters
    pc_chars = [
        char for char in all_combatants
        if not getattr(char, 'hostile', False) and char.character_type == 'player'
    ]
    npc_chars = [
        char for char in all_combatants
        if getattr(char, 'hostile', False) or char.character_type == 'npc'
    ]

    arena_scene = SceneInfo(
        scene_id=f"scene_{campaign_id}_arena",
        title="The Grand Arena",
        description="A circular combat arena with sandy floor, weapon racks along the walls, and cheering crowds in the stands.",
        location_id="grand_arena",
        location_description="The Grand Arena - a legendary gladiatorial combat venue",
        scene_type="combat",
        objectives=["Defeat your opponents in combat"],
        participants=[
            SceneParticipant(
                character_id=char.character_id,
                display_name=char.name,
                role=CharacterRole.PLAYER,
                capabilities=CharacterCapability.COMBAT,
                source="arena_setup"
            )
            for char in pc_chars
        ] + [
            SceneParticipant(
                character_id=char.character_id,
                display_name=char.name,
                role=CharacterRole.NPC_COMBATANT,
                capabilities=CharacterCapability.COMBAT,
                source="arena_setup"
            )
            for char in npc_chars
        ],
        pcs_present=[char.character_id for char in pc_chars],
        npcs_present=[char.character_id for char in npc_chars],
        npcs_involved=[char.character_id for char in npc_chars],
        narrative_notes=["Arena combat begins", "2v2 gladiatorial match"],
        metadata={"arena_mode": True, "difficulty": difficulty}
    )

    logger.info(f"Created arena scene: {arena_scene.scene_id} with {len(pc_chars)} PCs and {len(npc_chars)} NPCs")
    return arena_scene


def build_arena_prompt(difficulty: str = "medium", initiating_character: str = "Marcus the Gladiator") -> str:
    """Build the initial combat prompt for arena mode.

    Args:
        difficulty: Arena difficulty level
        initiating_character: Name of character who initiates combat (default: Marcus the Gladiator)

    Returns:
        Formatted prompt string
    """
    return f"""
    Start an immediate combat encounter in a gladiatorial arena!

    Setting: The Grand Arena - A circular combat arena with sandy floor, weapon racks along the walls, and cheering crowds in the stands.

    All combatants are already registered in the campaign:
    Player Characters:
    1. Marcus the Gladiator - Level 5 Human Fighter
    2. Lyra the Swift - Level 5 Elf Rogue

    NPC Opponents:
    1. Gorak the Brutal - Level 5 Half-Orc Barbarian (hostile)
    2. Theron the Mystic - Level 5 Human Wizard (hostile)

    The crowd roars as the gates open! Marcus and Lyra enter from the south gate, while Gorak and Theron enter from the north gate.
    The announcer shouts: "Let the combat begin!"

    {initiating_character} charges forward and strikes first! Generate an opening attack action for {initiating_character} targeting one of the hostile NPCs.

    Immediately start the combat encounter with these 4 combatants. Roll initiative for all 4 combatants and begin the first round of combat.
    The fight is to submission or unconsciousness - not necessarily to the death.
    Difficulty: {difficulty}
    Initiating Character: {initiating_character}
    """
