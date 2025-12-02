# D&D Formatter and Updater Tools Documentation

This document describes the formatter and updater tools available for D&D agents in the Gaia system.

## Overview

The formatter and updater tools are divided into two categories:

1. **Formatter Tools** - Format existing data for display
2. **Updater Tools** - Create or update campaign data models

## Formatter Tools

### 1. Character Formatter Tool (`character_formatter_tool`)

Formats character data for display.

**Parameters:**
- `character_data` (dict): Character information to format

**Example Usage:**
```python
result = await character_formatter_tool_handler(ctx, {
    "character_data": {
        "name": "Aragorn",
        "class": "Ranger",
        "level": 10,
        "hp": 84,
        "max_hp": 84,
        "ac": 16
    }
})
```

### 2. DM Output Formatter Tool (`dm_output_formatter_tool`)

Formats Dungeon Master responses into structured output.

**Parameters:**
- `answer` (string): Direct answer to player
- `narrative` (string): Story narrative
- `turn` (string): Turn information
- `status` (string): Current game status
- `characters` (string): Character information

**Example Usage:**
```python
result = await dm_output_formatter_tool_handler(ctx, {
    "answer": "You enter the ancient tomb.",
    "narrative": "The air is thick with dust...",
    "turn": "It's your turn to act.",
    "status": "No immediate threats visible.",
    "characters": "Aragorn (Ranger, HP: 84/84)"
})
```

### 3. Game State Formatter Tool (`game_state_formatter`)

Formats overall game state information.

**Parameters:**
- `game_state` (dict): Current game state data

**Example Usage:**
```python
result = await game_state_formatter_tool_handler(ctx, {
    "game_state": {
        "current_scene": "Tomb Entrance",
        "time_of_day": "Night",
        "weather": "Clear",
        "active_quests": ["Find the Lost Artifact"]
    }
})
```

### 4. Response Formatter Tool (`response_formatter`)

General purpose response formatter with metadata.

**Parameters:**
- `message` (string): The message to format
- `response_type` (string): Type of response (narration, dialogue, action, system)
- `metadata` (dict, optional): Additional metadata

**Example Usage:**
```python
result = await response_formatter_tool_handler(ctx, {
    "message": "The door creaks open.",
    "response_type": "narration",
    "metadata": {"sound_effect": "creaking_door.mp3"}
})
```

## Updater Tools

### 1. Character Updater Tool (`character_updater`)

Creates or updates character information.

**Parameters:**
- `name` (string, required): Character name
- `class_type` (string): Character class
- `race` (string): Character race
- `level` (int): Level (1-20)
- `hp` (int): Current hit points
- `max_hp` (int): Maximum hit points
- `ac` (int): Armor class
- `abilities` (dict): Ability scores (STR, DEX, CON, INT, WIS, CHA)
- `saving_throws` (dict): Saving throw modifiers
- `skills` (dict): Skill modifiers
- `status` (string): Status (active, unconscious, dead, stabilized, incapacitated)
- `conditions` (array): Active conditions
- `temporary_hp` (int): Temporary hit points
- `hit_dice` (string): Hit dice (e.g., "5d10")
- `death_saves` (dict): Death saving throws
- `inspiration` (bool): Has inspiration
- `proficiency_bonus` (int): Proficiency bonus (2-6)
- `speed` (int): Movement speed
- `initiative_bonus` (int): Initiative modifier
- `passive_perception` (int): Passive perception
- `languages` (array): Known languages
- `proficiencies` (array): Proficiencies
- `update_existing` (bool): Update mode vs create mode

**Example Usage:**
```python
# Create new character
result = update_character(
    name="Aragorn",
    class_type="Ranger",
    race="Human",
    level=10,
    hp=84,
    max_hp=84,
    ac=16,
    abilities={"STR": 18, "DEX": 16, "CON": 14, "INT": 12, "WIS": 14, "CHA": 13},
    update_existing=False
)

# Update existing character
result = update_character(
    name="Aragorn",
    hp=65,
    conditions=["exhausted", "poisoned"],
    update_existing=True
)
```

### 2. Ability Updater Tool (`ability_updater`)

Creates or updates abilities, spells, and features.

**Parameters:**
- `name` (string, required): Ability name
- `ability_type` (string): Type (spell, feature, trait, action, reaction)
- `description` (string): Full description
- `level` (int): Spell level (0-9) or ability level
- `damage` (string): Damage dice (e.g., "8d6")
- `damage_type` (string): Damage type
- `range` (string): Range/reach
- `area_of_effect` (string): Area description
- `duration` (string): Duration
- `components` (array): Spell components (V, S, M)
- `material_component` (string): Material component description
- `casting_time` (string): Casting time
- `school` (string): Magic school
- `classes` (array): Classes that can use
- `prerequisites` (array): Prerequisites
- `update_existing` (bool): Update mode

**Example Usage:**
```python
result = update_ability(
    name="Fireball",
    ability_type="spell",
    description="A bright streak flashes...",
    level=3,
    damage="8d6",
    damage_type="fire",
    range="150 feet",
    area_of_effect="20-foot radius sphere",
    components=["V", "S", "M"],
    material_component="A tiny ball of bat guano and sulfur"
)
```

### 3. Quest Updater Tool (`quest_updater`)

Creates or updates quest information.

**Parameters:**
- `name` (string, required): Quest name
- `description` (string): Quest description
- `objectives` (array): List of objectives with completion status
- `status` (string): Status (active, completed, failed, abandoned)
- `rewards` (array): Quest rewards
- `quest_giver` (string): NPC who gave the quest
- `prerequisites` (array): Prerequisites
- `level_requirement` (int): Minimum level
- `time_limit` (string): Time limit
- `failure_conditions` (array): Failure conditions
- `update_existing` (bool): Update mode

**Example Usage:**
```python
result = update_quest(
    name="Rescue the Princess",
    description="Save Princess Zelda from the dragon's lair.",
    objectives=[
        {"description": "Find the dragon's lair", "completed": True},
        {"description": "Defeat the dragon", "completed": False}
    ],
    status="active",
    rewards=["1000 gold pieces", "Magic sword"],
    quest_giver="King Hyrule"
)
```

### 4. Item Updater Tool (`item_updater`)

Creates or updates items and equipment.

**Parameters:**
- `name` (string, required): Item name
- `item_type` (string): Type (weapon, armor, potion, scroll, wondrous, other)
- `rarity` (string): Rarity (common, uncommon, rare, very rare, legendary, artifact)
- `value` (int): Value in gold pieces
- `weight` (float): Weight in pounds
- `description` (string): Item description
- `damage` (string): Damage for weapons
- `damage_type` (string): Damage type
- `properties` (array): Item properties
- `ac_bonus` (int): AC bonus for armor
- `attunement_required` (bool): Requires attunement
- `charges` (int): Number of charges
- `recharge` (string): Recharge rate
- `spell_effect` (string): Spell effect
- `update_existing` (bool): Update mode

**Example Usage:**
```python
result = update_item(
    name="Excalibur",
    item_type="weapon",
    rarity="legendary",
    damage="1d10+3",
    damage_type="slashing",
    properties=["versatile", "magical"],
    attunement_required=True,
    description="The legendary sword of King Arthur."
)
```

### 5. NPC Updater Tool (`npc_updater`)

Creates or updates NPC information.

**Parameters:**
- `name` (string, required): NPC name
- `race` (string): NPC race
- `occupation` (string): Job/role
- `personality_traits` (array): Personality traits
- `ideals` (array): Ideals and beliefs
- `bonds` (array): Bonds and connections
- `flaws` (array): Character flaws
- `relationship_to_party` (string): Relationship (ally, neutral, hostile)
- `knowledge` (array): What they know
- `secrets` (array): Hidden information
- `inventory` (array): Items they carry
- `dialogue_style` (string): How they speak
- `current_location` (string): Where they are
- `faction` (string): Faction affiliation
- `update_existing` (bool): Update mode

**Example Usage:**
```python
result = update_npc(
    name="Elrond",
    race="Elf",
    occupation="Lord of Rivendell",
    personality_traits=["wise", "kind", "ancient"],
    relationship_to_party="ally",
    dialogue_style="Formal and poetic",
    current_location="Rivendell",
    faction="Council of the Wise"
)
```

### 6. Environment Updater Tool (`environment_updater`)

Creates or updates location/environment information.

**Parameters:**
- `name` (string, required): Location name
- `environment_type` (string): Type (dungeon, city, wilderness, etc.)
- `description` (string): Location description
- `hazards` (array): Environmental hazards
- `weather_conditions` (string): Current weather
- `time_of_day` (string): Time of day
- `lighting_conditions` (string): Lighting
- `ambient_sounds` (array): Background sounds
- `notable_features` (array): Notable features
- `exits` (dict): Available exits
- `hidden_areas` (array): Hidden locations
- `traps` (array): Trap descriptions
- `inhabitants` (array): Who lives here
- `resources` (array): Available resources
- `update_existing` (bool): Update mode

**Example Usage:**
```python
result = update_environment(
    name="Dragon's Lair",
    environment_type="dungeon",
    description="A vast cavern filled with treasure and bones.",
    hazards=["extreme heat", "unstable ground"],
    weather_conditions="N/A - underground",
    notable_features=["treasure hoard", "dragon bones", "lava pools"],
    hidden_areas=["secret treasure vault"]
)
```

## Integration with Campaign Persistence

The formatter and updater tools are designed to work with the campaign persistence system:

1. **During Gameplay**: The DM agent uses these tools to format responses and update campaign state
2. **Automatic Persistence**: The `SimpleCampaignManager` uses the `CampaignDataExtractor` to parse tool outputs
3. **Structured Data**: Tool outputs are saved as timestamped structured data for audit trails

## Best Practices

1. **Use Update Mode**: Set `update_existing=true` when modifying existing entities
2. **Validate Input**: All tools validate against JSON schemas
3. **Handle Errors**: Tools return error messages for invalid input
4. **Batch Updates**: Use multiple tool calls for complex updates
5. **Maintain Consistency**: Ensure character names and IDs match across updates

## Testing

Run the test suite to verify tool functionality:

```bash
cd /home/lya/code/Gaia
python -m pytest test/dnd_agents/test_formatter_tools.py -v
```

## Adding Tools to Agents

To add a tool to an agent:

```python
from src.game.dnd_agents.tools import character_updater_tool_export

class MyAgent:
    tools = [
        character_updater_tool_export,
        # other tools...
    ]
```

The tools will automatically be available to the agent during execution.
