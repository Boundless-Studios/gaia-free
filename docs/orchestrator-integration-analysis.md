# Orchestrator Integration Analysis for Campaign Compaction

## Current State Analysis

### Existing Integration Points

The orchestrator already has several key integration points that can be leveraged for the compaction strategy:

1. **Campaign Data Persistence** (Line 180-223)
   - Already persists structured data after each turn
   - Uses `CampaignDataExtractor` to extract from DM responses
   - Saves to `campaign_data.json` in campaign data directory

2. **History Management** (Line 86-98)
   - Loads campaign history on each run
   - Maintains conversation history in `ConversationHistoryManager`
   - Clears and repopulates for each campaign run

3. **Campaign Manager Integration** (Line 39, 169-173)
   - Uses `SimpleCampaignManager` for campaign operations
   - Has access to campaign data paths
   - Handles campaign lifecycle

4. **Session Tracking** (Line 212-213)
   - Already tracks `total_sessions`
   - Updates `last_played` timestamp

### Missing Components for Compaction

1. **Turn Counting**
   - No persistent turn counter across the campaign
   - No trigger mechanism for periodic actions

2. **Scene Tracking**
   - No explicit scene progression tracking
   - Scene IDs are in data models but not actively managed

3. **Log Segmentation**
   - No mechanism to mark logs as "compacted"
   - All history is loaded every time

4. **Selective History Loading**
   - Currently loads entire history into memory
   - No support for loading only recent, non-compacted logs

## Proposed Integration Changes

### 1. Add Turn and Scene Tracking

```python
class Orchestrator:
    def __init__(self):
        # ... existing init ...
        self.turn_counter = {}  # campaign_id -> turn_count
        self.scene_tracker = {}  # campaign_id -> current_scene_id
        self.compaction_interval = 5
        self.persistence_agent = None
        
    def _load_campaign_state(self, campaign_id: str):
        """Load campaign state including turn and scene info."""
        state_file = self.campaign_manager.get_campaign_data_path(campaign_id) / "compaction_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                self.turn_counter[campaign_id] = state.get("turn_count", 0)
                self.scene_tracker[campaign_id] = state.get("current_scene_id")
        else:
            self.turn_counter[campaign_id] = 0
            self.scene_tracker[campaign_id] = None
    
    def _save_campaign_state(self, campaign_id: str):
        """Save campaign state including turn and scene info."""
        state_file = self.campaign_manager.get_campaign_data_path(campaign_id) / "compaction_state.json"
        state = {
            "turn_count": self.turn_counter.get(campaign_id, 0),
            "current_scene_id": self.scene_tracker.get(campaign_id),
            "last_compaction_turn": self._get_last_compaction_turn(campaign_id)
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
```

### 2. Modify run_campaign Method

Insert compaction logic at key points:

```python
async def run_campaign(self, user_input: str, campaign_id: Optional[str] = None) -> Dict[str, Any]:
    # ... existing code up to line 84 ...
    
    # Load campaign state (NEW)
    self._load_campaign_state(campaign_id)
    
    # ... existing code for loading history ...
    
    # Filter to only load non-compacted messages (MODIFIED)
    messages = self._load_recent_messages(campaign_id)
    
    # ... existing code up to line 133 ...
    
    # Increment turn counter (NEW)
    self.turn_counter[campaign_id] = self.turn_counter.get(campaign_id, 0) + 1
    
    # Update scene tracking if needed (NEW)
    if structured_data and structured_data.get("scene_id"):
        self.scene_tracker[campaign_id] = structured_data["scene_id"]
    
    # Check for compaction trigger (NEW)
    if self.turn_counter[campaign_id] % self.compaction_interval == 0:
        asyncio.create_task(self._trigger_compaction(campaign_id))
    
    # Save campaign state (NEW)
    self._save_campaign_state(campaign_id)
    
    # ... rest of existing code ...
```

### 3. Add Compaction Methods

```python
async def _trigger_compaction(self, campaign_id: str):
    """Trigger asynchronous campaign compaction."""
    try:
        logger.info(f"🔄 Starting compaction for {campaign_id} at turn {self.turn_counter[campaign_id]}")
        
        # Get persistence agent
        if not self.persistence_agent:
            from src.game.dnd_agents.campaign_persistence_agent import CampaignPersistenceAgent
            self.persistence_agent = CampaignPersistenceAgent()
        
        # Get logs to compact
        start_turn = self.turn_counter[campaign_id] - self.compaction_interval
        end_turn = self.turn_counter[campaign_id]
        logs_to_compact = self._get_logs_for_turns(campaign_id, start_turn, end_turn)
        
        # Load current campaign data
        campaign_data = self._load_campaign_data(campaign_id)
        
        # Run compaction
        result = await self.persistence_agent.compact_logs(
            logs=logs_to_compact,
            existing_state=campaign_data,
            campaign_id=campaign_id
        )
        
        # Save compacted data
        self._save_campaign_data(campaign_id, result.updated_state)
        
        # Mark logs as compacted
        self._mark_logs_compacted(campaign_id, start_turn, end_turn)
        
        logger.info(f"✅ Compaction completed for {campaign_id}")
        
    except Exception as e:
        logger.error(f"❌ Compaction failed for {campaign_id}: {e}")
        # Don't interrupt gameplay

def _load_recent_messages(self, campaign_id: str) -> List[Dict]:
    """Load only non-compacted messages."""
    all_messages = self.campaign_manager.load_campaign(campaign_id)
    
    # Get last compaction turn
    last_compaction = self._get_last_compaction_turn(campaign_id)
    
    # Filter messages
    if last_compaction > 0:
        # Only return messages after last compaction
        return [msg for msg in all_messages if msg.get("turn", 0) > last_compaction]
    
    return all_messages
```

### 4. Enhanced Message Structure

Modify how messages are saved to include turn information:

```python
def _save_campaign_history(self, campaign_id: str, campaign_name: Optional[str] = None):
    """Save the current campaign history to disk."""
    all_messages = []
    current_turn = self.turn_counter.get(campaign_id, 0)
    
    for msg in self.history_manager.get_full_history():
        message_dict = {
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": datetime.now().isoformat(),
            "turn": current_turn,  # Add turn number
            "scene_id": self.scene_tracker.get(campaign_id),  # Add scene ID
            "compacted": False  # Track compaction status
        }
        # ... rest of existing code ...
```

## Scene Progression Tracking

### Automatic Scene Detection

The orchestrator should detect scene transitions based on:

1. **Explicit Scene Markers** in structured data
2. **Location Changes** indicating new scenes
3. **Major Narrative Shifts** (combat start/end, quest completion)
4. **Time Transitions** (rest, travel)

```python
def _detect_scene_transition(self, structured_data: Dict, previous_scene_id: str) -> Optional[str]:
    """Detect if a scene transition occurred."""
    
    # Explicit scene ID in response
    if structured_data.get("scene_id"):
        return structured_data["scene_id"]
    
    # Location change
    current_location = structured_data.get("location")
    if current_location and current_location != self._last_location.get(campaign_id):
        return f"scene_{campaign_id}_{self.turn_counter[campaign_id]}"
    
    # Combat state change
    if structured_data.get("combat_started") or structured_data.get("combat_ended"):
        return f"scene_{campaign_id}_{self.turn_counter[campaign_id]}"
    
    # Major narrative marker
    if structured_data.get("chapter_end") or structured_data.get("quest_completed"):
        return f"scene_{campaign_id}_{self.turn_counter[campaign_id]}"
    
    return None
```

## Benefits of This Integration

1. **Minimal Disruption**: Compaction runs asynchronously
2. **Backward Compatible**: Existing campaigns continue to work
3. **Incremental Implementation**: Can be rolled out in phases
4. **Flexible Triggers**: Easy to adjust compaction frequency
5. **Scene-Aware**: Tracks narrative progression naturally

## Implementation Priority

### Phase 1: Basic Turn Tracking
- Add turn counter
- Save/load turn state
- No compaction yet

### Phase 2: Scene Tracking
- Detect scene transitions
- Track scene progression
- Associate turns with scenes

### Phase 3: Compaction Trigger
- Add persistence agent
- Implement async compaction
- Mark compacted logs

### Phase 4: Selective Loading
- Load only recent logs
- Hybrid context building
- Performance optimization

## Risks and Mitigations

### Risk: Breaking Existing Campaigns
**Mitigation**: 
- Default values for missing state
- Graceful handling of missing files
- Backward compatibility checks

### Risk: Compaction During Critical Moments
**Mitigation**:
- Async execution
- Skip compaction during combat
- User-configurable intervals

### Risk: Lost Context
**Mitigation**:
- Keep recent logs in full
- Validate compacted data
- Fallback to full history

## Monitoring Points

1. **Turn Progression**: Log turn counts
2. **Scene Transitions**: Track scene changes
3. **Compaction Events**: Log start/end/duration
4. **Memory Usage**: Before/after compaction
5. **Response Quality**: A/B test with/without compaction