# Internal Endpoints API Documentation

This document describes the internal API endpoints available for testing, debugging, and advanced operations in the Gaia backend.

## Base URL
```
http://localhost:8000/api/internal
```

---

## Scene Analysis Endpoints

### 1. Analyze Scene
**POST** `/analyze-scene`

Analyzes a player's input using all 5 scene analyzers in parallel.

#### Request Body
```json
{
  "user_input": "I attack the goblin with my sword",
  "campaign_id": "campaign_11",  // Optional
  "model": "llama3.2:3b",  // Optional, default: "llama3.2:3b"
  "context": {  // Optional custom context
    "location": "dungeon",
    "combat_round": 2
  },
  "include_previous_scenes": true,  // Optional, default: true
  "num_previous_scenes": 3  // Optional, default: 2
}
```

#### Response
```json
{
  "success": true,
  "analysis": {
    "complexity": {
      "level": "SIMPLE",
      "score": 3,
      "factors": [...],
      "primary_challenge": "Basic combat resolution"
    },
    "requirements": {
      "tools": ["dice_roller", "combat_tracker"],
      "agents": [],
      "tool_justifications": {...}
    },
    "scene": {
      "primary_type": "COMBAT",
      "secondary_types": ["ACTION"],
      "game_phase": "ENCOUNTER"
    },
    "special_considerations": {
      "flags": [...],
      "requires_dm_judgment": false
    },
    "routing": {
      "primary_agent": "CombatAgent",
      "confidence": "HIGH",
      "reasoning": "Combat action requires combat resolution"
    }
  },
  "execution_time": 5.234,
  "model_used": "llama3.2:3b"
}
```

### 2. Analyze Current Scene (Campaign)
**POST** `/campaign/{campaign_id}/analyze-current-scene`

Automatically analyzes the latest scene in a campaign with full context.

#### Parameters
- `campaign_id` (path): Campaign identifier
- `model` (query): LLM model to use (default: "llama3.2:3b")
- `num_previous_scenes` (query): Number of previous scenes to include (default: 3)

#### Example
```bash
curl -X POST "http://localhost:8000/api/internal/campaign/campaign_11/analyze-current-scene?model=llama3.2:3b"
```

#### Response
```json
{
  "success": true,
  "analysis": {
    // Same as analyze-scene output
    "input_analyzed": "I look around the tunnels",
    "campaign_id": "campaign_11",
    "previous_scenes_included": 3,
    "context_keys": ["previous_scenes", "last_user_actions", ...]
  },
  "execution_time": 6.304,
  "model_used": "llama3.2:3b",
  "message": "Analyzed current scene from campaign campaign_11"
}
```

### 3. Test Individual Analyzer
**POST** `/test-individual-analyzer`

Tests a specific analyzer in isolation.

#### Parameters
- `analyzer_name`: One of: `complexity`, `tools`, `categorization`, `special`, `routing`
- `user_input`: The input to analyze
- `model`: LLM model to use
- `context`: Optional context

#### Example
```bash
curl -X POST "http://localhost:8000/api/internal/test-individual-analyzer" \
  -H "Content-Type: application/json" \
  -d '{
    "analyzer_name": "complexity",
    "user_input": "I cast fireball",
    "model": "llama3.2:3b"
  }'
```

### 4. Get Scene Analyzer Status
**GET** `/scene-analyzer/status`

Returns the current status of the scene analyzer system.

#### Response
```json
{
  "initialized": true,
  "model": "llama3.2:3b",
  "analyzers": [
    "ComplexityAnalyzer",
    "ToolSelector",
    "SceneCategorizer",
    "SpecialConsiderations",
    "NextAgentRecommender"
  ],
  "context_manager_available": true
}
```

---

## Campaign Management Endpoints

### 5. Get Campaign Context
**GET** `/campaign/{campaign_id}/context`

Retrieves the current context for a campaign including previous scenes and game state.

#### Parameters
- `campaign_id` (path): Campaign identifier
- `num_scenes` (query): Number of previous scenes to include (default: 5)
- `include_summary` (query): Whether to include campaign summary (default: false)

#### Response
```json
{
  "success": true,
  "campaign_id": "campaign_11",
  "context": {
    "previous_scenes": [...],
    "recent_user_actions": [...],
    "game_state": {...},
    "active_characters": [...],
    "campaign_metadata": {...},
    "campaign_summary": {...}  // If include_summary=true
  }
}
```

### 6. Get Current Campaign Status
**GET** `/campaign/{campaign_id}/current-status`

Shows the current status of a campaign and what the analyzer will see.

#### Response
```json
{
  "success": true,
  "status": {
    "campaign_id": "campaign_11",
    "total_messages": 40,
    "total_turns": 20,
    "last_user_input": "I look around the tunnels",
    "last_user_timestamp": "2025-08-18T14:57:24.576302",
    "last_assistant_response": {
      "narrative": "The tunnel forks ahead...",
      "status": "Underground maintenance fork..."
    },
    "context_available": {
      "previous_scenes": 2,
      "recent_actions": 3,
      "active_characters": 1,
      "game_state_fields": [...]
    },
    "ready_for_analysis": true
  }
}
```

---

## Campaign Summarization Endpoints

### 7. Generate Campaign Summary
**POST** `/campaign/{campaign_id}/summarize`

Generates a summary of campaign history using CampaignSummarizer.

#### Parameters
- `campaign_id` (path): Campaign identifier
- `last_n_messages` (query): Number of recent messages to summarize (0 for all, default: 50)
- `model` (query): LLM model to use (default: "llama3.1:8b")
- `merge_with_previous` (query): Whether to merge with previous summaries (default: false)

#### Response
```json
{
  "success": true,
  "campaign_id": "campaign_11",
  "summary": {
    "summary": "Narrative text...",
    "characters": [...],
    "locales": [...],
    "events": [...],
    "treasures": [...],
    "story_threads": [...]
  },
  "model_used": "llama3.1:8b",
  "messages_analyzed": 50,
  "characters_found": 8,
  "locations_found": 7,
  "events_found": 9
}
```

### 8. Generate Complete Campaign Summary
**POST** `/campaign/{campaign_id}/generate-complete-summary`

Generates a complete one-time summary of the entire campaign.

#### Parameters
- `campaign_id` (path): Campaign identifier
- `model` (query): LLM model to use (default: "kimi-k2-instruct")
- `save_to_disk` (query): Whether to save summary to disk (default: true)

#### Response
```json
{
  "success": true,
  "campaign_id": "campaign_11",
  "summary": {
    // Full campaign summary structure
  },
  "model_used": "kimi-k2-instruct",
  "saved_to": "/home/gaia/campaigns/.../summary_turn_0020.json",
  "total_messages": 40,
  "characters_found": 8,
  "locations_found": 7,
  "events_found": 9,
  "treasures_found": 5,
  "story_threads_found": 7
}
```

---

## Usage Examples

### Analyzing a Combat Scene
```bash
curl -X POST "http://localhost:8000/api/internal/analyze-scene" \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "I attack the dragon with my +2 longsword",
    "campaign_id": "campaign_11",
    "include_previous_scenes": true
  }'
```

### Getting Campaign Context Before Analysis
```bash
# Check what context is available
curl "http://localhost:8000/api/internal/campaign/campaign_11/current-status"

# Get the full context
curl "http://localhost:8000/api/internal/campaign/campaign_11/context?num_scenes=3"

# Analyze the current scene with context
curl -X POST "http://localhost:8000/api/internal/campaign/campaign_11/analyze-current-scene"
```

### Generating Campaign Summaries
```bash
# Summarize last 20 messages
curl -X POST "http://localhost:8000/api/internal/campaign/campaign_11/summarize?last_n_messages=20"

# Generate complete campaign summary
curl -X POST "http://localhost:8000/api/internal/campaign/campaign_11/generate-complete-summary"
```

### Testing Individual Analyzers
```bash
# Test complexity analyzer
curl -X POST "http://localhost:8000/api/internal/test-individual-analyzer" \
  -d '{"analyzer_name": "complexity", "user_input": "I cast fireball at the group"}'

# Test routing analyzer
curl -X POST "http://localhost:8000/api/internal/test-individual-analyzer" \
  -d '{"analyzer_name": "routing", "user_input": "I want to buy items from the merchant"}'
```

---

## Error Responses

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Detailed error message",
  "campaign_id": "campaign_11"  // If applicable
}
```

Common error codes:
- `404`: Campaign not found
- `400`: Invalid parameters
- `500`: Internal server error

---

## Notes

1. **Model Selection**: The `model` parameter accepts any model available in your LLM setup (Ollama, Claude, Parasail)
2. **Context Loading**: Campaign context is automatically loaded from disk when `campaign_id` is provided
3. **Parallel Execution**: All 5 analyzers run in parallel for optimal performance
4. **Logging**: Detailed analyzer results are logged to the backend logs for debugging
5. **Performance**: Typical analysis takes 5-20 seconds depending on model and context size

---

## Environment Variables

Configure these for optimal operation:
```bash
CAMPAIGN_STORAGE_PATH=/home/gaia/campaigns  # Campaign data location
USE_SMALLER_MODEL=true  # Use lighter models for faster analysis
OLLAMA_HOST=http://localhost:11434  # Ollama server location
```