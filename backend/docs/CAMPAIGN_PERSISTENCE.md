# Campaign Persistence System

## Overview

The Gaia campaign persistence system provides comprehensive state management for D&D campaigns, allowing players to save and resume their adventures across sessions.

## Architecture

### Core Components

1. **Simple Campaign Manager** (`src/core/campaign/simple_campaign_manager.py`)
   - Central hub for all campaign operations
   - Handles create, read, update, delete (CRUD) operations
   - Mirrors state to local storage (and GCS when configured)
   - Provides session-based caching for performance

2. **Data Models** (`src/core/session/campaign_data_models.py`)
   - Comprehensive data structures for all campaign elements
   - Type-safe serialization/deserialization
   - Support for characters, NPCs, environments, scenes, narratives, and quests

3. **Unified Orchestrator** (`src/core/agent_orchestration/orchestrator.py`)
   - Single orchestrator implementation with built-in persistence
   - Automatic campaign loading and saving
   - Conversation history restoration
   - No deferred initialization - all components ready on startup

### Storage Structure

```
data/campaigns/
├── metadata/       # Quick-access campaign metadata
│   └── {session_id}.json
├── states/         # Full campaign state files
│   └── {session_id}.json
└── backups/        # Automatic backups (keeps last 5)
    └── {session_id}_{timestamp}.json
```

## Features

### Automatic Features

- **Auto-Import**: Legacy campaigns from chat history are automatically imported on first use
- **Auto-Save**: Campaign state is saved after each DM response
- **Auto-Backup**: Backups created before manual saves (last 5 retained)
- **Session Recovery**: Conversation history restored when loading campaigns

### Campaign Management

- Create new campaigns with custom titles and game styles
- Load existing campaigns with full state restoration
- List campaigns with sorting and pagination
- Delete campaigns (with automatic backup)
- Update campaign metadata

### Data Persistence

The system persists:
- **Story Details**: Narrative content and progression
- **Scene Descriptions**: Current and past scenes
- **Character Information**: Stats, inventory, status effects
- **NPCs**: Non-player characters and their relationships
- **Environments**: Locations and their connections
- **Quests**: Active and completed quests
- **Conversation History**: Full chat history

## Usage

### Basic Campaign Operations

```python
from core.campaign import SimpleCampaignManager

# Get the campaign manager
manager = SimpleCampaignManager()

# Create a new campaign
campaign = manager.create_campaign(
    session_id="my_campaign_001",
    title="The Lost Mines",
    description="A classic adventure",
    game_style="balanced"
)

# List campaigns
campaigns = manager.list_campaigns(sort_by="last_played")

# Load a campaign
campaign_data = manager.load_campaign("my_campaign_001")

# Save campaign (manual save)
manager.save_campaign("my_campaign_001", [])

# Delete campaign
manager.delete_campaign("my_campaign_001")
```

### Using the Unified Orchestrator

```python
from core.agent_orchestration import Orchestrator

# Create orchestrator
orchestrator = Orchestrator()

# Create a new campaign
campaign_info = orchestrator.create_new_campaign(
    title="Curse of Strahd",
    description="A gothic horror campaign",
    game_style="horror"
)

# Load existing campaign
orchestrator.load_campaign("existing_campaign_id")

# Run campaign (with auto-persistence)
result = await orchestrator.run_campaign(
    "I attack the goblin",
    session_id="my_campaign_001"
)

# The campaign is automatically saved after each turn
```

### Campaign Workflow Pattern

```python
# 1. Load campaign -> 2. Run campaign -> 3. Persist updates

# The orchestrator handles this automatically:
orchestrator = Orchestrator()

# This single call does everything:
# - Loads campaign (or creates if new)
# - Runs the DM response
# - Persists all updates
result = await orchestrator.run_campaign(user_input, session_id)
```

## API Integration

When integrated with the API, campaigns can be managed via HTTP endpoints:

```python
# GET /api/campaigns - List all campaigns
# POST /api/campaigns - Create new campaign
# GET /api/campaigns/{id} - Load campaign
# POST /api/campaigns/{id}/save - Save campaign
# DELETE /api/campaigns/{id} - Delete campaign
```

## Migration from Legacy System

The system automatically imports campaigns from the legacy chat history format:
- Files in `logs/chat_history/{session_id}_*.json` are detected
- Campaign titles extracted from filenames
- Conversation history preserved
- Import happens automatically on first use

## Best Practices

1. **Session IDs**: Use meaningful session IDs for campaigns (e.g., "curse_of_strahd_2024")
2. **Regular Saves**: While auto-save is enabled, manual saves create backups
3. **Campaign Titles**: Use descriptive titles for easy identification
4. **Game Styles**: Choose appropriate game style for better DM responses

## Error Handling

The system handles various error cases:
- Missing campaigns return None/empty results
- Corrupted files fall back to legacy system
- Failed saves log errors but don't crash
- Automatic cleanup of old backups

## Performance Considerations

- Campaigns are cached in memory after first load
- Metadata stored separately for fast listing
- Only active campaigns kept in memory
- Conversation history loaded on demand

## Future Enhancements

Planned improvements:
- Campaign templates for quick starts
- Export/import for campaign sharing
- Cloud backup integration
- Campaign analytics and insights
- Multi-user campaign support
