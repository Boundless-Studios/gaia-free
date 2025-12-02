# Campaign Persistence Agent - Design Document

## Overview

The Campaign Persistence Agent is a specialized agent responsible for extracting structured campaign data from conversation logs and maintaining an accurate, up-to-date representation of the campaign state. This agent works with formatter tools to populate campaign data models that can be persisted to disk.

## Agent Architecture

### Core Components

```python
class CampaignPersistenceAgent(Agent):
    """Agent for extracting and persisting campaign data from logs."""
    
    name = "campaign-persistence-agent"
    model = "claude-3-5-sonnet-20241022"
    
    # Shared state manager (singleton)
    campaign_state_manager = CampaignStateManager()
    
    def __init__(self):
        super().__init__()
        self.tools = self._initialize_tools()
        self.instructions = self._load_instructions()
```

### Agent Instructions

```markdown
You are a specialized Campaign Persistence Agent responsible for extracting and organizing 
campaign data from D&D game conversation logs. Your primary goal is to maintain an accurate,
comprehensive representation of the campaign state.

## Your Responsibilities:

1. **Analyze Conversation Logs**
   - Read through provided conversation logs carefully
   - Identify all campaign-relevant information
   - Track changes and updates to existing entities

2. **Extract Structured Data**
   - Character information (stats, inventory, status)
   - NPC details (relationships, locations, dialogue)
   - Environment descriptions and connections
   - Quest progression and objectives
   - Scene transitions and narrative flow
   - Combat outcomes and consequences

3. **Use Appropriate Tools**
   - character_updater: For player character changes
   - npc_updater: For NPC information
   - environment_updater: For location details
   - quest_updater: For quest progression
   - ability_updater: For spells and abilities
   - item_updater: For inventory changes
   - scene_narrative_updater: For story progression

4. **Handle Data Conflicts**
   - When new data conflicts with existing state:
     - Prefer the most recent information
     - Maintain narrative consistency
     - Preserve important historical details
   - Log significant changes for review

5. **Maintain Continuity**
   - Ensure character progression makes sense
   - Track cause and effect relationships
   - Preserve important dialogue and decisions
   - Note significant narrative moments

## Processing Guidelines:

- Process logs chronologically
- Update data incrementally (don't recreate from scratch)
- Focus on facts, not speculation
- Preserve player agency and choices
- Track both explicit and implied information

## Output Format:

After processing, provide a summary of:
1. Major updates made
2. New entities discovered
3. Significant narrative developments
4. Any data conflicts resolved

Remember: You are building a living document of the campaign. Every detail matters, 
but narrative coherence is paramount.
```

## Workflow Design

### 1. Log Analysis Phase

```python
async def analyze_logs(self, logs: List[Dict], existing_state: CampaignData) -> AnalysisResult:
    """Analyze logs to identify what needs to be extracted."""
    
    analysis = AnalysisResult()
    
    for log_entry in logs:
        # Identify log type (user action, DM response, system message)
        log_type = self._classify_log(log_entry)
        
        # Extract relevant sections
        if log_type == LogType.DM_RESPONSE:
            # Parse structured data if available
            structured = self._extract_structured_data(log_entry)
            analysis.add_structured_data(structured)
            
            # Parse narrative content
            narrative = self._extract_narrative(log_entry)
            analysis.add_narrative(narrative)
            
        elif log_type == LogType.USER_ACTION:
            # Track player decisions
            action = self._extract_player_action(log_entry)
            analysis.add_player_action(action)
    
    return analysis
```

### 2. Data Extraction Phase

```python
async def extract_campaign_data(self, analysis: AnalysisResult) -> None:
    """Use tools to extract and update campaign data."""
    
    # Initialize shared state for this extraction session
    self.campaign_state_manager.begin_transaction()
    
    try:
        # Process each data category
        await self._process_characters(analysis.character_updates)
        await self._process_npcs(analysis.npc_updates)
        await self._process_environments(analysis.environment_updates)
        await self._process_quests(analysis.quest_updates)
        await self._process_scenes(analysis.scene_data)
        await self._process_narratives(analysis.narratives)
        
        # Commit all changes atomically
        self.campaign_state_manager.commit()
        
    except Exception as e:
        # Rollback on any error
        self.campaign_state_manager.rollback()
        raise
```

### 3. Tool Coordination

```python
async def _process_characters(self, character_updates: List[CharacterUpdate]):
    """Process character updates using character_updater tool."""
    
    for update in character_updates:
        # Prepare tool parameters
        params = {
            "character_id": update.character_id,
            "updates": update.changes,
            "source": update.source_reference
        }
        
        # Call tool (updates shared state internally)
        await self.use_tool("character_updater", params)
```

## Shared State Manager

### Design

```python
class CampaignStateManager:
    """Thread-safe manager for campaign state during extraction."""
    
    def __init__(self):
        self._current_state: Optional[CampaignData] = None
        self._transaction_state: Optional[CampaignData] = None
        self._lock = asyncio.Lock()
        
    async def begin_transaction(self):
        """Start a new transaction."""
        async with self._lock:
            if self._transaction_state is not None:
                raise RuntimeError("Transaction already in progress")
            # Deep copy current state for transaction
            self._transaction_state = copy.deepcopy(self._current_state)
    
    async def get_state(self) -> CampaignData:
        """Get current working state."""
        async with self._lock:
            return self._transaction_state or self._current_state
    
    async def update_character(self, character: CharacterInfo):
        """Update a character in the working state."""
        async with self._lock:
            if not self._transaction_state:
                raise RuntimeError("No transaction in progress")
            self._transaction_state.add_character(character)
    
    async def commit(self):
        """Commit transaction changes."""
        async with self._lock:
            if not self._transaction_state:
                raise RuntimeError("No transaction in progress")
            self._current_state = self._transaction_state
            self._transaction_state = None
    
    async def rollback(self):
        """Rollback transaction changes."""
        async with self._lock:
            self._transaction_state = None
```

## Tool Integration

### Enhanced Formatter Tools

Each formatter tool needs to be enhanced to work with the shared state:

```python
# Example: character_updater.py enhancement
async def character_updater_tool_handler(ctx, params):
    """Update character information in shared state."""
    
    # Get shared state manager from context
    state_manager = ctx.get("campaign_state_manager")
    if not state_manager:
        raise ValueError("No campaign state manager in context")
    
    # Get current state
    campaign_data = await state_manager.get_state()
    
    # Extract character or create new
    character_id = params["character_id"]
    character = campaign_data.characters.get(character_id)
    
    if not character:
        character = CharacterInfo(character_id=character_id, name=params["name"])
    
    # Apply updates
    for field, value in params["updates"].items():
        if hasattr(character, field):
            setattr(character, field, value)
    
    # Update in shared state
    await state_manager.update_character(character)
    
    return f"Updated character: {character.name}"
```

## Integration with Orchestrator

### Initialization

```python
# In orchestrator.py
class Orchestrator:
    def __init__(self):
        # ... existing init ...
        self.persistence_agent = None
        self.campaign_state_manager = CampaignStateManager()
        
    async def _get_persistence_agent(self):
        """Lazy initialize persistence agent."""
        if not self.persistence_agent:
            self.persistence_agent = CampaignPersistenceAgent()
            # Inject shared state manager
            self.persistence_agent.campaign_state_manager = self.campaign_state_manager
        return self.persistence_agent
```

### Compaction Flow

```python
async def _trigger_compaction(self, campaign_id: str):
    """Execute campaign data compaction."""
    
    logger.info(f"🔄 Starting compaction for campaign {campaign_id}")
    
    # Get agent
    agent = await self._get_persistence_agent()
    
    # Load current campaign data
    current_data = self._load_campaign_data(campaign_id)
    self.campaign_state_manager._current_state = current_data
    
    # Get recent logs
    recent_logs = self._get_recent_logs(campaign_id, self.compaction_interval)
    
    # Create compaction context
    context = {
        "campaign_id": campaign_id,
        "existing_state": current_data,
        "logs": recent_logs
    }
    
    # Run agent
    result = await agent.compact_campaign_data(context)
    
    # Get updated state and persist
    updated_data = self.campaign_state_manager._current_state
    self._save_campaign_data(campaign_id, updated_data)
    
    logger.info(f"✅ Compaction complete: {result}")
```

## Error Handling

### Graceful Degradation

```python
class CampaignPersistenceAgent:
    async def compact_campaign_data(self, context: Dict) -> Dict:
        """Main entry point for compaction."""
        
        try:
            # Analyze logs
            analysis = await self.analyze_logs(
                context["logs"], 
                context["existing_state"]
            )
            
            # Extract data
            await self.extract_campaign_data(analysis)
            
            # Generate summary
            summary = self._generate_summary(analysis)
            
            return {
                "status": "success",
                "summary": summary,
                "updates_count": analysis.total_updates
            }
            
        except Exception as e:
            logger.error(f"Compaction failed: {e}", exc_info=True)
            
            # Return partial results if possible
            return {
                "status": "partial",
                "error": str(e),
                "summary": "Compaction partially completed"
            }
```

### Validation

```python
def _validate_extraction(self, before: CampaignData, after: CampaignData) -> bool:
    """Validate that extraction didn't corrupt data."""
    
    # Check critical data wasn't lost
    if len(after.characters) < len(before.characters):
        logger.warning("Characters were lost during extraction")
        return False
    
    # Check data consistency
    for char_id, character in after.characters.items():
        if character.level < 1 or character.hit_points_max < 1:
            logger.warning(f"Invalid character data: {char_id}")
            return False
    
    return True
```

## Performance Considerations

### Batching

- Process multiple updates to the same entity together
- Minimize tool calls by batching related updates
- Use bulk operations where possible

### Caching

- Cache frequently accessed data during extraction
- Maintain lookup tables for entity relationships
- Reuse parsed structured data

### Async Operations

- Run independent tool operations concurrently
- Use asyncio.gather for parallel processing
- Don't block on I/O operations

## Testing Strategy

### Unit Tests

```python
async def test_character_extraction():
    """Test extracting character updates from logs."""
    
    # Setup
    agent = CampaignPersistenceAgent()
    logs = [
        {
            "role": "assistant",
            "content": {
                "narrative": "The wizard gains a level!",
                "characters": {
                    "wizard_001": {"level": 6, "hp_max": 38}
                }
            }
        }
    ]
    
    # Execute
    analysis = await agent.analyze_logs(logs, CampaignData("test"))
    
    # Verify
    assert len(analysis.character_updates) == 1
    assert analysis.character_updates[0].character_id == "wizard_001"
```

### Integration Tests

- Test full compaction flow with real campaign data
- Verify data persistence and loading
- Test error recovery scenarios
- Validate performance with large datasets

## Monitoring

### Metrics

- Compaction duration
- Number of entities processed
- Data conflicts resolved
- Error rates
- Memory usage during compaction

### Logging

```python
logger.info(f"📊 Compaction metrics: {json.dumps({
    'duration_seconds': duration,
    'logs_processed': len(logs),
    'characters_updated': len(character_updates),
    'npcs_updated': len(npc_updates),
    'scenes_created': len(new_scenes),
    'conflicts_resolved': conflict_count
})}")
```

## Future Enhancements

1. **Parallel Processing**: Use multiple agents for different data types
2. **Incremental Updates**: Only process changed data
3. **Smart Conflict Resolution**: ML-based conflict resolution
4. **Data Versioning**: Track all changes with version history
5. **Compression**: Reduce storage size with smart summarization