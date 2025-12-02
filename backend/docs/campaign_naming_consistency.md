# Campaign Naming Consistency Fix

## Overview

Fixed inconsistencies in campaign ID generation to ensure all campaigns use sequential numbering (`campaign_1`, `campaign_2`, etc.) regardless of how they are created.

## Changes Made

### 1. Fixed `campaign_endpoints.py`
**File**: `/src/api/campaign_endpoints.py`

Changed the `create_campaign` method from using UUID-based IDs:
```python
# OLD: campaign_id = f"campaign_{uuid.uuid4().hex[:8]}"
```

To using sequential IDs from the campaign manager:
```python
# NEW: 
if self.orchestrator and hasattr(self.orchestrator, 'campaign_manager'):
    campaign_id = self.orchestrator.campaign_manager.get_next_campaign_id()
else:
    # Fallback to simple campaign manager
    from src.core.campaign.simple_campaign_manager import SimpleCampaignManager
    simple_manager = SimpleCampaignManager()
    campaign_id = simple_manager.get_next_campaign_id()
```

### 2. Added `start_new_campaign` Method to Orchestrator
**File**: `/src/core/agent_orchestration/orchestrator.py`

Added a new method that the protobuf endpoint expects:
```python
async def start_new_campaign(self) -> Dict[str, Any]:
    """Start a new campaign with an auto-generated sequential ID."""
    campaign_id = self.campaign_manager.get_next_campaign_id()
    logger.info(f"🆕 Starting new campaign: {campaign_id}")
    
    welcome_message = (
        "Welcome, brave adventurers! You stand at the threshold of a new journey..."
    )
    
    return await self.run_campaign(welcome_message, campaign_id)
```

### 3. Fixed Protobuf Endpoint
**File**: `/src/api/protobuf_endpoints.py`

- Removed the UUID generation from `new_campaign_protobuf`
- Updated `_process_protobuf_request` to extract campaign_id from the orchestrator's response
- Ensures the campaign_id is properly set in the MachineResponse

### 4. Added Missing `clear()` Method
**File**: `/src/core/session/history_manager.py`

Added the missing `clear()` method to `ConversationHistoryManager`:
```python
def clear(self):
    """Clear the conversation history."""
    self.history = []
```

## Result

Now all campaign creation paths use sequential IDs:
- Frontend Campaign Manager → `/api/campaigns` → `campaign_3`
- Frontend New Campaign button → `/api/proto/new-campaign` → `campaign_4`
- Direct orchestrator usage → `run_campaign()` → `campaign_5`

## Benefits

1. **Consistent Naming**: All campaigns follow the pattern `campaign_N`
2. **Easy Organization**: Campaigns are numbered sequentially in the file system
3. **Better UX**: Users can easily see the order campaigns were created
4. **Simplified Debugging**: Clear, predictable campaign IDs

## File Organization

Campaigns are stored as:
```
campaigns/logs/
├── campaign_1.json
├── campaign_2_the_lost_mine.json
├── campaign_3.json
└── campaign_4_epic_adventure.json
```

Where the filename includes the campaign ID and optionally the campaign name.