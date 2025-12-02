# Formatter Tools Review for Campaign Compaction

## Overview

The existing formatter tools under `src/game/dnd_agents/tools/formatters/` provide a foundation for updating campaign data models. However, they need enhancement to work with the campaign compaction strategy.

## Current Tool Architecture

### Existing Tools

1. **character_updater.py**
   - Updates CharacterInfo fields
   - Has persistence hooks integration
   - Returns structured data with update mode
   - Missing: Character ID generation, inventory as Item objects

2. **npc_updater.py** (based on hook implementation)
   - Updates NPCInfo fields
   - Similar structure to character_updater
   - Missing: NPC ID generation, proper inventory handling

3. **environment_updater.py** (based on hook implementation)
   - Updates EnvironmentInfo fields
   - Sets current scene when first environment created
   - Missing: Location ID generation, connected locations

4. **quest_updater.py** (based on hook implementation)
   - Updates QuestInfo fields
   - Manages active quest list
   - Missing: Quest ID generation, objective tracking

5. **item_updater.py** (based on hook implementation)
   - Creates items with properties
   - Currently adds to first character's inventory as string
   - Missing: Proper Item object creation, inventory management

6. **ability_updater.py**
   - Not reviewed but likely updates abilities/spells
   - Missing: Integration with Ability data model

### Persistence Hooks System

The `persistence_hooks.py` file shows an existing pattern for tool persistence:
- Global hook instance
- Session-based persistence
- Automatic campaign saving after tool calls
- Error handling that doesn't fail tool execution

## Required Enhancements

### 1. Shared State Integration

Current tools save directly to campaign. For compaction, they need to:
```python
# Instead of:
self.campaign_manager.save_campaign(...)

# Use shared state:
state_manager = ctx.get("campaign_state_manager")
await state_manager.update_character(character)
```

### 2. ID Generation

Tools need consistent ID generation:
```python
def generate_character_id(name: str, campaign_id: str) -> str:
    """Generate consistent character ID."""
    return f"char_{campaign_id}_{name.lower().replace(' ', '_')}"
```

### 3. Data Model Alignment

Tools need to create proper data model instances:
```python
# Current: Adds string to inventory
campaign.characters[0].inventory.append(item_name)

# Required: Add Item object
item = Item(
    name=item_data["name"],
    item_type=item_data.get("type", "misc"),
    properties=item_data.get("properties", {})
)
character.inventory[item.name] = item
```

### 4. New Tools Needed

#### scene_narrative_updater.py
```python
def update_scene_narrative(
    scene_title: str,
    scene_type: str,  # combat, exploration, social, puzzle
    location: str,
    description: str,
    objectives: Optional[List[str]] = None,
    npcs_involved: Optional[List[str]] = None,
    narrative_content: Optional[str] = None,
    narrative_type: Optional[str] = None,  # description, dialog, action
    speaker: Optional[str] = None
) -> dict:
    """Updates scene and narrative information."""
```

## Integration Pattern

### Enhanced Tool Handler

```python
async def enhanced_tool_handler(ctx: Any, params: Any) -> str:
    """Enhanced handler that works with shared state."""
    
    # Get shared state manager
    state_manager = ctx.get("campaign_state_manager")
    if not state_manager:
        # Fallback to direct persistence
        return await legacy_tool_handler(ctx, params)
    
    # Parse params
    if isinstance(params, str):
        params = json.loads(params)
    
    # Validate params
    validate(instance=params, schema=tool_params_schema)
    
    # Get current campaign data
    campaign_data = await state_manager.get_state()
    
    # Process update
    entity = process_update(params, campaign_data)
    
    # Update shared state
    await state_manager.update_entity(entity)
    
    # Return result
    return json.dumps({
        "status": "success",
        "entity": entity.to_dict(),
        "update_type": params.get("update_existing") and "update" or "create"
    })
```

## Migration Strategy

### Phase 1: Dual Mode Support
- Tools check for `campaign_state_manager` in context
- If present, use shared state
- If not, use existing persistence hooks
- No breaking changes

### Phase 2: Enhanced Data Models
- Add ID generation
- Create proper object instances
- Add missing fields to match campaign_data_models.py

### Phase 3: New Tools
- Implement scene_narrative_updater
- Add bulk update tools for efficiency
- Create validation tools

## Tool Coordination

### Batch Updates
For efficiency, the persistence agent should batch related updates:

```python
# In persistence agent
async def process_combat_outcome(self, combat_data):
    """Process combat outcome with multiple tool calls."""
    
    # Batch character updates
    character_updates = []
    for char in combat_data["participants"]:
        character_updates.append({
            "name": char["name"],
            "hp": char["current_hp"],
            "conditions": char["conditions"]
        })
    
    # Use batch tool
    await self.use_tool("batch_character_updater", {
        "updates": character_updates
    })
```

### Tool Dependencies
Some updates require coordination:
1. Environment update → Update character locations
2. Quest completion → Update character experience
3. NPC death → Remove from environment

## Validation Requirements

### Pre-Update Validation
- Check entity exists before update
- Validate relationships (e.g., location exists)
- Ensure data consistency

### Post-Update Validation
- Verify no data corruption
- Check invariants maintained
- Validate references still valid

## Performance Considerations

### Caching
- Cache frequently accessed entities
- Maintain lookup indices
- Reuse parsed data

### Lazy Loading
- Only load entities being updated
- Defer expensive operations
- Batch similar updates

## Testing Strategy

### Unit Tests
- Test each tool independently
- Mock shared state manager
- Verify data transformations

### Integration Tests
- Test tool coordination
- Verify persistence
- Test error scenarios

### Load Tests
- Test with large campaigns
- Measure update performance
- Verify memory usage

## Conclusion

The existing formatter tools provide a solid foundation but need enhancement for the compaction strategy:

1. **Shared State Integration**: Modify to work with CampaignStateManager
2. **Data Model Alignment**: Create proper object instances
3. **ID Management**: Consistent ID generation
4. **New Tools**: Scene and narrative management
5. **Coordination**: Batch updates and dependencies

With these enhancements, the formatter tools will effectively support the campaign compaction system while maintaining backward compatibility.