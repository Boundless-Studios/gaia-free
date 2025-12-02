# Streaming Dungeon Master Architecture

## Overview

This document describes the streaming DM narrative generation system that enables real-time, progressive responses to players. The system separates narrative generation into distinct, sequentially streamed phases for immediate player feedback.

## Architecture

### Core Components

1. **StreamingDMOrchestrator** (`src/game/dnd_agents/streaming_dm_orchestrator.py`)
   - Manages three-phase sequential generation
   - Coordinates WebSocket streaming via callbacks
   - Handles fallback to non-streaming on failure

2. **StreamingLLMClient** (`src/core/llm/streaming_llm_client.py`)
   - Provides streaming completion API
   - Wraps AsyncOpenAI for real-time chunk delivery
   - Supports both streaming and non-streaming modes

3. **Streaming Prompts** (`src/game/dnd_agents/streaming_dm_prompts.py`)
   - Four specialized prompts for each generation phase
   - Focused, task-specific instructions for better results

4. **CampaignBroadcaster Updates** (`src/api/websocket/campaign_broadcaster.py`)
   - New methods for broadcasting streaming chunks
   - WebSocket message types for each phase

5. **CampaignRunner Integration** (`src/core/session/campaign_runner.py`)
   - `run_dungeon_master_streaming()` method
   - Maintains backward compatibility with original DM

## Generation Flow

### Phase 1: Narrative (Immediate Streaming)
- **Purpose**: Set atmospheric tone and scene description
- **Streaming**: Yes, chunks sent as generated
- **WebSocket Event**: `narrative_chunk`
- **Content**: Scene atmosphere, environment, sensations
- **Timing**: Starts immediately, streams progressively

### Phase 2: Player Response (Sequential Streaming)
- **Purpose**: Address player action and consequences
- **Streaming**: Yes, chunks sent as generated
- **WebSocket Event**: `player_response_chunk`
- **Content**: Direct answer/response to player
- **Timing**: Starts after narrative complete

### Phase 3: Player Options (Single Generation)
- **Purpose**: Provide contextual action choices
- **Streaming**: No, sent as complete list
- **WebSocket Event**: `player_options`
- **Content**: 3-5 actionable options
- **Timing**: Generated after response complete

### Phase 4: Metadata (Background)
- **Purpose**: Track game state for backend
- **Streaming**: No, generated async
- **WebSocket Event**: `metadata_update`
- **Content**: Environmental conditions, threats, story progress
- **Timing**: Non-blocking, generated in background

## WebSocket Message Types

### narrative_chunk
```json
{
  "type": "narrative_chunk",
  "content": "The tavern falls silent as you enter...",
  "is_final": false,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### player_response_chunk
```json
{
  "type": "player_response_chunk",
  "content": "You notice a hooded figure watching you...",
  "is_final": false,
  "timestamp": "2025-01-15T10:30:02Z"
}
```

### player_options
```json
{
  "type": "player_options",
  "options": [
    "Approach the hooded figure",
    "Order a drink and observe",
    "Search for exits",
    "Ask the bartender about the figure"
  ],
  "timestamp": "2025-01-15T10:30:05Z"
}
```

### metadata_update
```json
{
  "type": "metadata_update",
  "metadata": {
    "environmental_conditions": "Dimly lit, crowded, noisy",
    "immediate_threats": "Unknown hooded figure - potentially hostile",
    "story_progression": "Party has entered the Rusty Dragon Inn",
    "scene_elements": {
      "npcs_present": ["Hooded Figure", "Bartender", "Patrons"],
      "objects_of_interest": ["Back exit", "Staircase to upper floor"],
      "current_location": "The Rusty Dragon Inn"
    }
  },
  "timestamp": "2025-01-15T10:30:06Z"
}
```

## Usage

### Backend: Campaign Runner

```python
# Use streaming DM
result = await campaign_runner.run_dungeon_master_streaming(
    user_input="I look for suspicious characters",
    dm_context=dm_context,
    session_id=session_id,
    broadcaster=campaign_broadcaster,
)
```

### Frontend: WebSocket Handler (TODO)

```typescript
// Handle narrative chunks
socket.on('narrative_chunk', (data) => {
  if (data.is_final) {
    // Narrative complete
  } else {
    // Append chunk to narrative display
    appendNarrativeChunk(data.content);
  }
});

// Handle player response chunks
socket.on('player_response_chunk', (data) => {
  if (data.is_final) {
    // Response complete
  } else {
    // Append chunk to response display
    appendResponseChunk(data.content);
  }
});

// Handle player options
socket.on('player_options', (data) => {
  displayPlayerOptions(data.options);
});

// Handle metadata update
socket.on('metadata_update', (data) => {
  updateGameState(data.metadata);
});
```

## Key Design Decisions

### 1. Sequential vs. Parallel Generation
- **Decision**: Sequential (narrative → response → options)
- **Rationale**:
  - Better narrative coherence
  - Response can reference narrative
  - Options can reference both narrative and response
  - Simpler state management

### 2. Streaming vs. Non-Streaming Phases
- **Decision**: Stream narrative and response, not options
- **Rationale**:
  - Narrative/response benefit from progressive display
  - Options work better as complete list
  - Metadata is for backend only

### 3. Combat Responsibility
- **Decision**: DM does NOT handle combat
- **Rationale**:
  - Separate combat agents manage turn order
  - DM focuses on narrative and roleplay
  - Cleaner separation of concerns

### 4. Fallback Strategy
- **Decision**: Fallback to non-streaming DM on errors
- **Rationale**:
  - Ensures players always get a response
  - Graceful degradation
  - Maintains backward compatibility

## Testing

### Backend Testing
Tests are designed for Docker environment with all dependencies:

```bash
# Run in backend-dev container
docker exec gaia-backend-dev python3 test/test_streaming_dm.py
```

### Integration Testing
End-to-end testing requires:
1. Backend streaming DM operational
2. Frontend WebSocket handlers implemented
3. Test campaign session with connected client

## Performance Considerations

### Streaming Benefits
- **Perceived Latency**: Players see response start in <1s instead of waiting 5-10s
- **Engagement**: Progressive reveal keeps players engaged
- **Bandwidth**: Chunks sent as generated, no buffering needed

### Trade-offs
- **API Calls**: 3 sequential calls vs. 1 (mitigated by immediate feedback)
- **Token Usage**: Similar total tokens, just split across calls
- **Complexity**: More moving parts, but better UX

## Future Enhancements

### Short Term
- Frontend WebSocket handlers
- End-to-end testing
- Streaming quality metrics

### Medium Term
- Adaptive streaming (adjust based on network conditions)
- Client-side caching for reconnection
- Streaming audio generation alongside text

### Long Term
- Multi-modal streaming (text + images + audio)
- Player-specific narrative personalization
- Real-time collaborative storytelling

## Migration Path

### Existing Code
- Old `run_dungeon_master()` method still works
- No breaking changes to existing flows
- Gradual migration supported

### New Code
- Use `run_dungeon_master_streaming()` for new features
- Frontend updates required for streaming support
- Toggle between streaming/non-streaming via config

## Related Files

- `backend/src/game/dnd_agents/streaming_dm_prompts.py` - Prompt definitions
- `backend/src/game/dnd_agents/streaming_dm_orchestrator.py` - Orchestration logic
- `backend/src/core/llm/streaming_llm_client.py` - LLM streaming client
- `backend/src/api/websocket/campaign_broadcaster.py` - WebSocket broadcasting
- `backend/src/core/session/campaign_runner.py` - Integration point
- `backend/test/test_streaming_dm.py` - Test suite

## Support

For questions or issues with streaming DM:
1. Check logs at `src/logs/gaia_all.log`
2. Verify WebSocket connections in browser console
3. Test with non-streaming DM to isolate issues
4. Review this documentation for expected behavior
