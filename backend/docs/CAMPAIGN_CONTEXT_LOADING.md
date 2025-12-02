# Campaign Context Loading

This document describes how campaign context is automatically loaded into the LLM message history when campaigns are loaded in Gaia.

## Overview

When a campaign is loaded (either automatically or manually), the system now automatically loads all relevant campaign context into the LLM's message history. This ensures that the LLM has access to all the structured campaign data when generating responses.

## What Gets Loaded

The following campaign data is automatically loaded into the LLM context:

### Basic Campaign Information
- Campaign title and description
- Game style and theme
- Current scene and location

### Player Characters
- Character names, classes, levels, and races
- Current hit points and armor class
- Status conditions and effects
- Current location

### Non-Player Characters (NPCs)
- NPC names and roles
- Locations and dispositions
- Descriptions and relationships

### Locations and Environments
- Location names and types
- Environmental descriptions
- Hazards and points of interest

### Active Quests
- Quest titles and descriptions
- Current status and objectives
- Quest givers and locations

### Recent Scenes
- Scene titles and types
- Scene descriptions and outcomes
- Connected locations and NPCs

### Recent Story Events
- Narrative content and types
- Speakers and timestamps
- Story progression details

## How It Works

### Automatic Loading

When using `PersistentDnDOrchestrator`, campaign context is automatically loaded in the following scenarios:

1. **First Campaign Access**: When a session first accesses a campaign, the context is loaded automatically
2. **Campaign Updates**: After each campaign interaction, the context is refreshed to include the latest information
3. **Manual Loading**: When manually loading a campaign via `load_campaign()`

### Context Management

The system includes several features to manage campaign context:

- **Duplicate Prevention**: The system checks for existing campaign context to avoid duplicates
- **Context Refresh**: After campaign updates, the context is refreshed to ensure the LLM has the latest information
- **Context Filtering**: When switching campaigns, old context is removed and new context is loaded

## Implementation Details

### Key Methods

- `_load_campaign_context_into_llm()`: Loads campaign data into LLM message history
- `refresh_campaign_context()`: Refreshes campaign context after updates
- `_ensure_campaign_loaded()`: Ensures campaign is loaded and context is available

### Message Format

Campaign context is added as a system message with the following structure:

```
Campaign Context:
# Campaign: [Title]
Description: [Description]
Game Style: [Style]
Game Theme: [Theme]
Current Scene: [Scene ID]
Current Location: [Location ID]

## Player Characters:
- [Character Name] ([Race] [Class] [Level])
  HP: [Current]/[Max]
  AC: [Armor Class]
  Status: [Status]
  Location: [Location]

## Non-Player Characters:
- [NPC Name] ([Role])
  Location: [Location]
  Disposition: [Disposition]
  Description: [Description]

## Locations:
- [Location Name] ([Type])
  Description: [Description]
  Hazards: [Hazards]

## Active Quests:
- [Quest Title]
  Status: [Status]
  Description: [Description]
  Objectives: [Objectives]

## Recent Scenes:
- [Scene Title] ([Type])
  Description: [Description]
  Outcomes: [Outcomes]

## Recent Story Events:
- [Type]: [Content]
  Speaker: [Speaker]
```

## Usage Examples

### Basic Usage

```python
from src.core.agent_orchestration.orchestrator_with_persistence import PersistentDnDOrchestrator

# Create orchestrator
orchestrator = PersistentDnDOrchestrator()

# Create a new campaign (context loaded automatically)
campaign_result = orchestrator.create_new_campaign(
    title="My Adventure",
    description="An epic quest",
    game_style="balanced"
)

# Run campaign (context automatically available to LLM)
result = await orchestrator.run_campaign("I want to explore the dungeon", campaign_result["campaign_id"])
```

### Manual Campaign Loading

```python
# Load an existing campaign (context loaded automatically)
success = orchestrator.load_campaign("existing_campaign_id")

if success:
    # Campaign context is now available to the LLM
    result = await orchestrator.run_campaign("What's happening?", "existing_campaign_id")
```

### Refreshing Context

```python
# Manually refresh campaign context
orchestrator.refresh_campaign_context("campaign_id")
```

## Benefits

1. **Consistent Context**: The LLM always has access to the complete campaign state
2. **Automatic Updates**: Context is automatically refreshed after each interaction
3. **Rich Information**: All structured campaign data is available for better responses
4. **Seamless Experience**: No manual context management required

## Technical Notes

- Campaign context is stored as system messages in the conversation history
- Context is automatically filtered to avoid duplicates
- The system handles large campaigns by limiting the number of recent scenes and narratives shown
- Context loading is designed to be efficient and not impact performance significantly

## Future Enhancements

Potential future improvements could include:

- Configurable context depth (how much history to include)
- Context summarization for very large campaigns
- Selective context loading based on relevance
- Context compression for long-running campaigns 