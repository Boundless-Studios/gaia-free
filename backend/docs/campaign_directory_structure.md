# Campaign Directory Structure

## Overview

Campaigns are now organized in a hierarchical directory structure that keeps all campaign-related files together.

## Directory Structure

```
campaigns/
├── campaign_1/
│   ├── logs/
│   │   └── chat_history.json
│   └── data/
│       └── campaign_data.json
├── campaign_2 - The Lost Mine/
│   ├── logs/
│   │   └── chat_history.json
│   └── data/
│       ├── campaign_data.json
│       └── custom_data.json
└── campaign_3 - Epic Adventure/
    ├── logs/
    │   └── chat_history.json
    └── data/
        └── campaign_data.json
```

## Directory Naming Convention

- **Without Name**: `campaign_X` (e.g., `campaign_1`)
- **With Name**: `campaign_X - Name` (e.g., `campaign_2 - The Lost Mine`)

The campaign ID (`campaign_X`) is always included for easy identification, and the optional name makes directories human-readable.

## Subdirectories

### `/logs/`
Contains all conversation/chat history:
- `chat_history.json` - The main chat log containing all messages between players and the DM

### `/data/`
Contains structured campaign data:
- `campaign_data.json` - Structured data extracted from game sessions (characters, quests, locations, etc.)
- Additional JSON files can be stored here for custom campaign data

## Benefits

1. **Organization**: All files for a campaign are in one place
2. **Clarity**: Directory names show both ID and campaign name
3. **Scalability**: Easy to add new types of data (images, maps, notes)
4. **Portability**: Easy to backup, share, or move entire campaigns
5. **Clean**: No mixing of different campaigns' files

## API Changes

The `SimpleCampaignManager` class has been updated with new methods:

```python
# Get the data directory path for a campaign
data_path = manager.get_campaign_data_path("campaign_1")
# Returns: Path("campaigns/campaign_1/data/")
```

## Backward Compatibility

The system maintains backward compatibility with the old structure:
- Old format: `campaigns/logs/campaign_1.json`
- The manager will still read old-format campaigns
- New saves will use the new directory structure

## File Locations

- **Chat History**: `campaigns/{id} - {name}/logs/chat_history.json`
- **Campaign Data**: `campaigns/{id} - {name}/data/campaign_data.json`
- **Custom Data**: `campaigns/{id} - {name}/data/*.json`

## Implementation Details

The changes were made in:
1. `SimpleCampaignManager` - Updated to create and manage the new directory structure
2. `Orchestrator` - Updated to save structured data in the campaign's data directory
3. Frontend remains unchanged - it only needs the campaign ID

## Future Enhancements

This structure makes it easy to add:
- Character sheets as separate files
- Maps and images in an `assets/` subdirectory
- Notes and journals in a `notes/` subdirectory
- Backups in a `backups/` subdirectory