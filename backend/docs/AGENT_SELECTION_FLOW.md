# Agent Selection and Execution Flow

## Current Implementation

### Agent Selection Decision Tree

```
User Input
    ↓
Orchestrator.run_campaign()
    ↓
[Check Scene Context]
    ├─ No active scene → Skip to main flow
    └─ Has active scene → Try scene agents
            ↓
    [Keyword-based Selection]
        ├─ Contains "say/ask/tell/talk/speak" → DialogAgent
        ├─ Contains "look/search/examine/investigate/explore" → ExplorationAgent
        ├─ Contains "attack/cast/fight/hit/shoot" → None (use main flow)
        └─ Default → ActionResolver
            ↓
    [Scene Agent Response]
        ├─ Returns response → Use it, skip main flow
        └─ Returns None or needs handoff → Continue to main flow
            ↓
[Main Flow - ScenarioAnalyzer]
    ↓
[Campaign Runner - DungeonMaster]
    ↓
[Response Processing]
```

## Problems with Current Implementation

### 1. Scene Agents Don't Use Runner Interface
- Scene agents try to call `agent.run()` which doesn't exist
- Should use `Runner.run()` like other agents

### 2. Simplistic Keyword Matching
- Misses context and nuance
- Example: "I tell him to attack" triggers DialogAgent but might need combat

### 3. No Integration with ScenarioAnalyzer
- Scene agents bypass the analyzer completely
- Lose valuable context and intent analysis

### 4. Scene State Management Issues
- Scene context initialized but not properly maintained
- No clear handoff mechanism between scene and DM

## Proposed Improvements

### 1. Fix Scene Agent Execution
```python
# Instead of:
agent.run(prompt)

# Use:
from agents import Runner, RunConfig
result = await Runner.run(
    agent,
    prompt,
    run_config=RunConfig(...)
)
```

### 2. Integrate ScenarioAnalyzer First
```python
# Always analyze first
analysis = await scenario_analyzer.analyze(user_input)

# Then route based on analysis
if analysis.requires_new_scene:
    → DungeonMaster
elif analysis.interaction_type == "dialog":
    → DialogAgent
elif analysis.interaction_type == "exploration":
    → ExplorationAgent
# etc.
```

### 3. Better Agent Selection Logic
Instead of keyword matching, use the ScenarioAnalyzer's output:
- `interaction_type`: dialog, exploration, action, combat
- `requires_dm`: boolean flag for complex scenarios
- `confidence`: how certain the analyzer is

### 4. Proper Scene State Tracking
- Initialize scene from DM responses
- Track interaction count
- Detect when new scene needed
- Smooth handoffs between agents

## Execution Flow

### How Agents Execute

1. **Agent Creation**: Each agent has an `as_openai_agent()` method
2. **Runner.run()**: Executes the agent with:
   - Agent instance
   - Input prompt
   - RunConfig (model, temperature, tools)
   - Max turns
3. **Response Processing**: Parse structured output or raw text
4. **History Management**: Add to conversation history

### Model Resolution
```python
# How models are resolved
model = resolve_model(agent.model)  # e.g., "qwen3-32b"
provider = get_model_provider_for_resolved_model(model)
run_config = RunConfig(
    model=model,
    model_provider=provider,
    model_settings=ModelSettings(...)
)
```

## Next Steps

1. Fix scene agent execution to use Runner interface
2. Integrate ScenarioAnalyzer before scene agent selection
3. Improve selection logic based on analysis
4. Add proper async/await support
5. Test end-to-end flow