# Agent Prompt Refactoring Opportunities

## Overview

This document outlines code simplification opportunities identified during the migration of agent prompts from hardcoded Python strings to database-backed SQL definitions. By moving runtime string concatenation from Python code into SQL template placeholders, we can reduce code complexity and improve maintainability.

## Current State

As of this analysis:
- **24 SQL prompts** defined in `backend/src/core/prompts/sql/`
- **4 agents migrated** to DB-backed prompts with fallback
- **16-17 agents remaining** to migrate
- **Audit script** available at `backend/scripts/audit_agent_prompts.py`

## Refactoring Patterns Identified

### Pattern 1: Runtime String Concatenation in `_build_*_prompt` Methods

**Problem**: Multiple agents have `_build_*_prompt` methods that concatenate context strings at runtime.

**Example from StreamingDMOrchestrator**:

#### Current Implementation (Python)

```python
async def _build_unified_prompt(
    self,
    conversation_history: str,
    scene_context: SceneContextData,
    player_input: str,
    *,
    force_scene_creation: bool = False,
    transition_indicators: Optional[List[str]] = None,
) -> str:
    """Build prompt for unified DM generation."""
    # Load base prompt from DB
    unified_prompt = await self._get_unified_streaming_prompt()

    # Manual string concatenation in Python
    prompt = f"""{unified_prompt}

CONVERSATION HISTORY:
{conversation_history}

CURRENT SCENE:
{scene_context.formatted_text}

PLAYER'S LATEST ACTION:
{player_input}

Generate your complete DM response now (both NARRATIVE and RESPONSE sections):"""

    if not scene_context.has_scene:
        prompt += """

SCENE STATUS:
No active scene is currently available. Before writing your two paragraphs you MUST call the `scene_creator` tool..."""

    return prompt
```

#### Proposed Implementation (SQL + Python)

**SQL Template** (with placeholders):
```sql
$PROMPT${{core_persona}}

YOUR SPECIFIC TASK:
Generate a complete DM response with TWO distinct paragraphs separated by a blank line.

CONVERSATION HISTORY:
{{conversation_history}}

CURRENT SCENE:
{{current_scene}}

PLAYER'S LATEST ACTION:
{{player_input}}

Generate your complete DM response now (both NARRATIVE and RESPONSE sections):{{scene_status}}

OUTPUT STRUCTURE:
...$PROMPT$
```

**Python Code** (simplified):
```python
async def _build_unified_prompt(
    self,
    conversation_history: str,
    scene_context: SceneContextData,
    player_input: str,
    *,
    force_scene_creation: bool = False,
    transition_indicators: Optional[List[str]] = None,
) -> str:
    """Build prompt for unified DM generation."""
    # Prepare scene status based on context
    scene_status = ""
    if not scene_context.has_scene:
        scene_status = """

SCENE STATUS:
No active scene is currently available. Before writing your two paragraphs you MUST call the `scene_creator` tool..."""
    elif force_scene_creation:
        indicator_text = ", ".join(transition_indicators or [])
        scene_status = f"""

SCENE STATUS:
A meaningful transition has occurred ({indicator_text})..."""

    # Load prompt from DB and resolve all placeholders in one call
    return await self.prompt_service.get_and_resolve_prompt(
        agent_type="streaming_dm",
        prompt_key="unified_streaming",
        fallback=UNIFIED_STREAMING_DM_PROMPT,
        context={
            "conversation_history": conversation_history,
            "current_scene": scene_context.formatted_text,
            "player_input": player_input,
            "scene_status": scene_status,
        }
    )
```

### Pattern 2: Metadata Prompt Building

**Current Implementation**:
```python
async def _build_metadata_prompt(
    self,
    conversation_history: str,
    scene_context: SceneContextData,
    player_input: str,
    narrative: str,
    player_response: str,
) -> str:
    """Build prompt for metadata generation."""
    metadata_prompt = await self._get_metadata_prompt()

    return f"""{metadata_prompt}

CONVERSATION HISTORY:
{conversation_history}

CURRENT SCENE:
{scene_context.formatted_text}

NARRATIVE (already provided):
{narrative}

PLAYER RESPONSE (already provided):
{player_response}

PLAYER'S LATEST ACTION:
{player_input}

Generate the metadata JSON now:"""
```

**Proposed Implementation**:

Move all context sections into SQL template with placeholders, then resolve in a single call:

```python
async def _build_metadata_prompt(
    self,
    conversation_history: str,
    scene_context: SceneContextData,
    player_input: str,
    narrative: str,
    player_response: str,
) -> str:
    """Build prompt for metadata generation."""
    return await self.prompt_service.get_and_resolve_prompt(
        agent_type="streaming_dm",
        prompt_key="metadata_generation",
        fallback=METADATA_GENERATION_PROMPT,
        context={
            "conversation_history": conversation_history,
            "current_scene": scene_context.formatted_text,
            "player_input": player_input,
            "narrative": narrative,
            "player_response": player_response,
        }
    )
```

## Benefits

### Code Simplification
- **Reduces Python code** from 10-20 lines to 5-10 lines per method
- **Eliminates f-string concatenation** - easier to read and maintain
- **Single source of truth** - prompt structure lives in SQL only

### Maintainability
- **Prompt changes don't require code changes** - update SQL only
- **Clear separation** - business logic in Python, prompt structure in SQL
- **Easier testing** - template structure changes don't break Python tests

### Consistency
- **Uniform placeholder syntax** - `{{variable}}` in SQL templates
- **Centralized template resolution** - one method handles all placeholders
- **Version control** - SQL prompts support versioning for A/B testing

## Migration Strategy

### Phase 1: Infrastructure (✅ Complete)
- [x] PromptService supports `get_prompt_with_fallback()`
- [x] PromptService supports `resolve_template()` for `{{placeholders}}`
- [x] SQL prompts use `{{double_braces}}` for placeholders
- [x] All agents have hardcoded fallback prompts

### Phase 2: Agent Migration (In Progress)
- [x] StreamingDungeonMasterAgent migrated
- [x] StreamingDMOrchestrator migrated (partially - still has string concat)
- [x] ActionResolver migrated
- [x] DialogAgent migrated
- [ ] ExplorationAgent
- [ ] SceneDescriberAgent
- [ ] Remaining 14 agents

### Phase 3: Code Simplification (⚠️ NOT TO BE EXECUTED)
**This phase is documented for future reference but should NOT be implemented now:**
- [ ] Add `PromptService.get_and_resolve_prompt()` convenience method
- [ ] Update SQL templates to include context placeholders
- [ ] Refactor `_build_*_prompt` methods to use new pattern
- [ ] Remove string concatenation from Python code
- [ ] Update tests to verify placeholder resolution

### Phase 4: Validation (Future)
- [ ] Run audit script to verify all agents migrated
- [ ] Integration tests with DB-loaded prompts
- [ ] Performance testing (DB load vs hardcoded)
- [ ] Rollback plan if issues discovered

## Code Locations

### Files to Refactor (Phase 3 - NOT TO BE EXECUTED)
1. [backend/src/game/dnd_agents/streaming_dm_orchestrator.py](../../backend/src/game/dnd_agents/streaming_dm_orchestrator.py) (lines 611-691)
   - `_build_unified_prompt()` - 47 lines → ~15 lines
   - `_build_metadata_prompt()` - 18 lines → ~10 lines

2. Scene agents with similar patterns (to be identified during migration)

### SQL Templates to Update (Phase 3 - NOT TO BE EXECUTED)
1. [backend/src/core/prompts/sql/dungeon_master/streaming_dm__unified_streaming.sql](../../backend/src/core/prompts/sql/dungeon_master/streaming_dm__unified_streaming.sql)
   - Add: `{{conversation_history}}`, `{{current_scene}}`, `{{player_input}}`, `{{scene_status}}`

2. [backend/src/core/prompts/sql/dungeon_master/streaming_dm__metadata_generation.sql](../../backend/src/core/prompts/sql/dungeon_master/streaming_dm__metadata_generation.sql)
   - Add: `{{conversation_history}}`, `{{current_scene}}`, `{{player_input}}`, `{{narrative}}`, `{{player_response}}`

## Audit Tooling

Run the audit script to track migration progress:

```bash
cd backend
python3 scripts/audit_agent_prompts.py
```

**Sample Output**:
```
=== Agent Prompt Audit ===

📊 Scanning SQL prompts...
   Found 24 SQL prompts

🐍 Scanning Python prompts...
   Found 5 Python prompt constants

🔍 Scanning agent classes...
   Found 20 agent classes

✅ Exact Matches (4):
   • streaming_dm__unified_streaming
   • streaming_dm__metadata_generation
   • action_resolver__base_prompt
   • dialog__base_prompt

✅ Migrated Agents (4):
   • StreamingDungeonMasterAgent
   • StreamingDMOrchestrator
   • ActionResolver
   • DialogAgent

❌ Not Migrated (16):
   • ExplorationAgent (missing db_session, missing _get_prompt method)
   • SceneDescriberAgent (missing db_session, missing _get_prompt method)
   • ... (14 more)
```

## Risks and Mitigation

### Risk: Performance Impact
- **Concern**: DB lookups for every prompt might be slower than hardcoded strings
- **Mitigation**: PromptService already has caching; fallback ensures zero downtime

### Risk: Template Syntax Errors
- **Concern**: Typos in `{{placeholders}}` could break prompts
- **Mitigation**: Validate templates during migration; Python tests catch missing placeholders

### Risk: Breaking Changes
- **Concern**: Prompt changes in SQL could break existing functionality
- **Mitigation**: Version control on prompts; rollback to previous version if needed

## Implementation Status

### Completed
- ✅ Document created outlining refactoring opportunities
- ✅ Phase 1 infrastructure complete
- ✅ 4 agents migrated to DB-backed prompts

### In Progress
- 🔄 Phase 2: Migrating remaining agents to DB-backed prompts

### Future Work (NOT TO BE EXECUTED NOW)
- ⚠️ Phase 3: Code simplification via SQL template placeholders
- ⚠️ Phase 4: Validation and performance testing

## References

- Audit Script: [backend/scripts/audit_agent_prompts.py](../../backend/scripts/audit_agent_prompts.py)
- PromptService: [backend/src/core/prompts/prompt_service.py](../../backend/src/core/prompts/prompt_service.py)
- SQL Prompts: [backend/src/core/prompts/sql/](../../backend/src/core/prompts/sql/)
- Migration Pattern Example: [backend/src/game/dnd_agents/streaming_dungeon_master.py](../../backend/src/game/dnd_agents/streaming_dungeon_master.py) (lines 102-124)
