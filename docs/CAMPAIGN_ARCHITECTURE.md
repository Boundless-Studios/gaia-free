# Campaign Architecture

## Overview

A simplified campaign management system for Gaia D&D that focuses on clarity and ease of understanding.

## Core Principles

1. **Always in a Campaign**: Every message is part of a campaign. If no campaign is loaded, create a new one.
2. **Simple Numbering**: Campaigns are numbered sequentially (Campaign 1, Campaign 2, etc.)
3. **Optional Naming**: Campaigns can have names: "Campaign 1 - The Lost Mine of Phandelver"
4. **Message History is Context**: Loading a campaign = loading its message history into LLM context

## Directory Structure

```
campaigns/
├── logs/                              # Complete message history
│   ├── campaign_1.json
│   ├── campaign_2_the_lost_mine.json
│   └── campaign_3_curse_of_strahd.json
└── data/                              # Structured campaign data
    ├── campaign_1_data.json
    ├── campaign_2_data.json
    └── campaign_3_data.json
```

## Campaign Log Format

Each campaign log is a JSON file containing the complete conversation history:

```json
[
  {
    "role": "user",
    "content": "I want to play a rogue in a dark fantasy setting",
    "timestamp": "2024-01-20T10:30:00Z"
  },
  {
    "role": "assistant",
    "content": {
      "answer": "...",
      "narrative": "...",
      "turn": "...",
      "status": "...",
      "characters": "...",
      "input_needed": false
    },
    "timestamp": "2024-01-20T10:30:15Z"
  }
]
```

## Campaign Run Loop

### Phase 1: Campaign Resolution
```
IF campaign_id provided:
    Use existing campaign
ELSE:
    Create new campaign with next sequential number
```

### Phase 2: Load Campaign State
```
1. Read message history from campaigns/logs/campaign_X.json
2. Load all messages into LLM context
3. Setup campaign runner with loaded history
```

### Phase 3: Process User Input
```
1. Add user message to history
2. Save immediately (user input persisted)
```

### Phase 4: Generate AI Response
```
1. Analyze scenario with analyzer agent
2. Run DM agent with full context
3. Extract structured data from response
```

### Phase 5: Save Message History
```
1. Add assistant response to history
2. Save complete history to campaigns/logs/campaign_X.json
```

### Phase 6: Persist Structured Data
```
1. Extract campaign data (characters, quests, etc.)
2. Update campaigns/data/campaign_X_data.json
3. This enables advanced features without cluttering logs
```

## API Flow

### New Message (No Campaign)
```
POST /api/chat
{
  "message": "I want to play a wizard"
}

Response:
{
  "campaign_id": "campaign_1",
  "response": { ... structured DM response ... }
}
```

### Continue Campaign
```
POST /api/chat
{
  "message": "I cast fireball",
  "campaign_id": "campaign_1"
}

Response:
{
  "campaign_id": "campaign_1",
  "response": { ... structured DM response ... }
}
```

### List Campaigns
```
GET /api/campaigns

Response:
[
  {"id": "campaign_1", "name": null, "message_count": 10},
  {"id": "campaign_2", "name": "The Lost Mine", "message_count": 25}
]
```

### Load Campaign
```
GET /api/campaigns/{campaign_id}

Response:
{
  "id": "campaign_1",
  "name": null,
  "messages": [ ... full history ... ]
}
```

## Implementation Details

### Campaign Manager (Simplified)

```python
class SimpleCampaignManager:
    def __init__(self):
        self.campaigns_dir = Path("campaigns/logs")
        self.campaigns_dir.mkdir(exist_ok=True)
    
    def get_next_campaign_id(self) -> str:
        """Get the next sequential campaign ID"""
        existing = self.list_campaigns()
        next_num = len(existing) + 1
        return f"campaign_{next_num}"
    
    def load_campaign(self, campaign_id: str) -> List[Dict]:
        """Load campaign history from disk"""
        file_path = self.campaigns_dir / f"{campaign_id}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return []
    
    def save_campaign(self, campaign_id: str, messages: List[Dict]):
        """Save campaign history to disk"""
        file_path = self.campaigns_dir / f"{campaign_id}.json"
        with open(file_path, 'w') as f:
            json.dump(messages, f, indent=2)
```

### Orchestrator Integration

```python
# In the Unified Orchestrator
async def run_campaign(self, user_input: str, campaign_id: Optional[str] = None):
    # Step 1: Resolve campaign
    if not campaign_id:
        campaign_id = self.campaign_manager.get_next_campaign_id()
    
    # Step 2: Load campaign history
    messages = self.campaign_manager.load_campaign(campaign_id)
    
    # Step 3: Set LLM context with full history
    self.history_manager.clear()
    for msg in messages:
        self.history_manager.add_message(msg["role"], msg["content"])
    
    # Step 4: Add new user message
    self.history_manager.add_message("user", user_input)
    
    # Step 5: Run DM
    response = await self.run_dm_with_context()
    
    # Step 6: Add response to history
    self.history_manager.add_message("assistant", response)
    
    # Step 7: Save campaign
    all_messages = self.history_manager.get_full_history()
    self.campaign_manager.save_campaign(campaign_id, all_messages)
    
    return {
        "campaign_id": campaign_id,
        "response": response
    }
```

## Benefits

1. **Simplicity**: One file per campaign, easy to understand
2. **Transparency**: Can directly view/edit campaign logs
3. **Portability**: Easy to share or backup campaigns
4. **Debugging**: Clear what context the LLM sees
5. **No Hidden State**: Everything is in the message history

## Migration Path

1. Create campaigns/logs directory
2. Implement SimpleCampaignManager
3. Update orchestrator to use new flow
4. Migrate existing chat histories to new format
5. Remove complex persistence logic