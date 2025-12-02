# Campaign Compaction Strategy - Requirements Document

## Overview

This document outlines the requirements and design for implementing a campaign compaction strategy in the Gaia D&D system. The goal is to reduce hallucination in longer sessions by periodically translating raw conversation logs into structured campaign data models, which can then be used to provide more accurate and consistent context to the Dungeon Master agent.

## Problem Statement

### Current Issues
1. **Context Degradation**: As sessions grow longer, providing the entire message history to the DM agent leads to:
   - Increased hallucination
   - Inconsistent character states
   - Forgotten plot elements
   - Performance degradation

2. **Memory Limitations**: The current system passes all historical messages without summarization or structure, leading to:
   - Token limit constraints
   - Reduced response quality
   - Slower processing times

### Solution Approach
Implement a compaction strategy that:
- Translates conversation logs into structured data models every 5 turns
- Persists structured data to disk under `campaigns/campaign_XXX/data`
- Uses a specialized persistence agent with formatting tools
- Maintains campaign consistency while reducing context size

## System Architecture

### Components

#### 1. Campaign Persistence Agent
A new specialized agent responsible for:
- Receiving structured campaign state (if available) + raw logs
- Translating logs into campaign data models using formatter tools
- Maintaining in-memory representation of campaign state
- Coordinating data persistence to disk

**Key Responsibilities:**
- Parse raw conversation logs
- Extract relevant information for each data model
- Update existing campaign state
- Handle data conflicts and merging
- Ensure data consistency

#### 2. Formatter Tools Enhancement
Enhance existing formatter tools under `src/game/dnd_agents/tools/formatters/` to:
- Update a shared in-memory campaign data representation
- Work collaboratively to build complete campaign state
- Handle incremental updates to existing data

**Required Tool Enhancements:**
- `character_updater.py` - Update CharacterInfo models
- `npc_updater.py` - Update NPCInfo models
- `environment_updater.py` - Update EnvironmentInfo models
- `quest_updater.py` - Update QuestInfo models
- `ability_updater.py` - Update abilities and items
- New tool: `scene_narrative_updater.py` - Create SceneInfo and NarrativeInfo

#### 3. Shared State Manager
A new component to:
- Maintain in-memory CampaignData instance
- Provide thread-safe access to campaign state
- Handle concurrent updates from multiple formatter tools
- Support atomic batch updates

#### 4. Orchestrator Integration
Enhance the orchestrator to:
- Track scene progression (turn counts)
- Trigger compaction every 5 turns
- Manage persistence agent lifecycle
- Handle compaction failures gracefully

## Data Flow

### Compaction Process
1. **Trigger**: Orchestrator detects 5 turns have passed
2. **Collection**: Gather last 5 turns of raw logs + current campaign state
3. **Analysis**: Persistence agent analyzes logs and identifies updates
4. **Extraction**: Agent uses formatter tools to extract structured data
5. **Merge**: Update shared campaign state with new information
6. **Persist**: Save updated campaign data to disk
7. **Cleanup**: Mark processed logs as compacted

### Loading Process
1. **Campaign Start**: Load existing campaign data from disk
2. **Context Build**: Create DM context from structured data instead of raw logs
3. **Recent History**: Include only recent (non-compacted) conversation logs
4. **Handoff**: Provide compact, structured context to DM agent

## Technical Requirements

### Data Storage
- **Location**: `campaigns/campaign_XXX/data/`
- **Format**: JSON files for each data model type
- **Structure**:
  ```
  campaigns/campaign_001/data/
  ├── campaign_data.json      # Main campaign data
  ├── characters.json         # Character details
  ├── npcs.json              # NPC information
  ├── environments.json      # Location data
  ├── scenes.json           # Scene progression
  ├── narratives.json       # Story narratives
  └── compaction_state.json # Tracking compaction progress
  ```

### Persistence Agent Configuration
```python
class CampaignPersistenceAgent:
    name = "campaign-persistence-agent"
    model = "claude-3-5-sonnet-20241022"  # High quality for data extraction
    
    tools = [
        "character_updater_tool",
        "npc_updater_tool",
        "environment_updater_tool",
        "quest_updater_tool",
        "ability_updater_tool",
        "item_updater_tool",
        "scene_narrative_updater_tool"
    ]
    
    instructions = """
    You are a specialized agent responsible for extracting and organizing campaign 
    data from conversation logs. Your role is to:
    
    1. Analyze conversation logs to identify campaign information
    2. Use appropriate formatter tools to update campaign data models
    3. Ensure data consistency and completeness
    4. Handle conflicts between existing and new data appropriately
    5. Maintain narrative continuity and character progression
    """
```

### Orchestrator Integration Points

#### Scene Tracking
Add to `orchestrator.py`:
```python
class Orchestrator:
    def __init__(self):
        # ... existing init ...
        self.turn_counter = 0
        self.compaction_interval = 5
        self.persistence_agent = None  # Lazy init
        
    async def run_campaign(self, user_input: str, campaign_id: Optional[str] = None):
        # ... existing code ...
        
        # Increment turn counter
        self.turn_counter += 1
        
        # Check for compaction trigger
        if self.turn_counter % self.compaction_interval == 0:
            await self._trigger_compaction(campaign_id)
        
        # ... rest of method ...
```

#### Compaction Trigger
```python
async def _trigger_compaction(self, campaign_id: str):
    """Trigger campaign data compaction."""
    try:
        # Initialize persistence agent if needed
        if not self.persistence_agent:
            self.persistence_agent = CampaignPersistenceAgent()
        
        # Get recent logs (last 5 turns)
        recent_logs = self._get_recent_logs(campaign_id, self.compaction_interval)
        
        # Load current campaign state
        campaign_data = self._load_campaign_data(campaign_id)
        
        # Run persistence agent
        updated_data = await self.persistence_agent.compact_logs(
            recent_logs, 
            campaign_data
        )
        
        # Persist to disk
        self._save_campaign_data(campaign_id, updated_data)
        
        # Mark logs as compacted
        self._mark_logs_compacted(campaign_id, recent_logs)
        
    except Exception as e:
        logger.error(f"Compaction failed: {e}")
        # Continue normal operation even if compaction fails
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Create shared state manager for campaign data
2. Enhance existing formatter tools to work with shared state
3. Create scene/narrative updater tool
4. Implement basic persistence logic

### Phase 2: Agent Development (Week 2)
1. Develop CampaignPersistenceAgent
2. Implement log analysis and data extraction logic
3. Create tool coordination mechanism
4. Add conflict resolution logic

### Phase 3: Orchestrator Integration (Week 3)
1. Add turn counting and scene tracking
2. Implement compaction triggers
3. Create log management (marking as compacted)
4. Add failure handling and recovery

### Phase 4: Context Loading (Week 4)
1. Modify campaign loading to use structured data
2. Update DM context builder
3. Implement hybrid approach (structured + recent logs)
4. Add backwards compatibility

### Phase 5: Testing & Optimization (Week 5)
1. Create comprehensive test scenarios
2. Benchmark performance improvements
3. Tune compaction interval
4. Add monitoring and metrics

## Success Criteria

1. **Reduced Hallucination**: Measurable reduction in inconsistencies after 10+ turns
2. **Performance**: Faster response times for long sessions
3. **Data Integrity**: No loss of important campaign information
4. **Seamless Experience**: Users shouldn't notice compaction happening
5. **Reliability**: System continues working even if compaction fails

## Future Enhancements

1. **Configurable Intervals**: Allow different compaction frequencies
2. **Smart Compaction**: Trigger based on content complexity, not just turn count
3. **Selective Loading**: Load only relevant campaign data based on current scene
4. **Multi-Agent Compaction**: Use multiple specialized agents for different data types
5. **Compression**: Further reduce context size with advanced summarization

## Risks and Mitigations

### Risk 1: Data Loss
**Mitigation**: Always maintain raw logs as backup, implement versioning

### Risk 2: Extraction Errors
**Mitigation**: Validate extracted data, maintain previous state as fallback

### Risk 3: Performance Impact
**Mitigation**: Run compaction asynchronously, don't block main game flow

### Risk 4: Complexity
**Mitigation**: Incremental implementation, extensive testing at each phase

## Conclusion

This campaign compaction strategy will significantly improve the Gaia D&D system's ability to handle longer sessions while maintaining narrative consistency and reducing hallucination. The modular design allows for incremental implementation and testing, ensuring system stability throughout development.