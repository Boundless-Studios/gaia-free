# Streaming DM Frontend Integration Guide

## Overview

This document describes how to integrate the backend streaming DM with the frontend React components. The backend now sends narrative, player responses, and options as separate streaming chunks via WebSocket.

## Backend WebSocket Events

The backend sends four new WebSocket message types:

### 1. narrative_chunk
```json
{
  "type": "narrative_chunk",
  "content": "The tavern falls silent as you enter...",
  "is_final": false,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### 2. player_response_chunk
```json
{
  "type": "player_response_chunk",
  "content": "You notice a hooded figure watching you...",
  "is_final": false,
  "timestamp": "2025-01-15T10:30:02Z"
}
```

### 3. player_options
```json
{
  "type": "player_options",
  "options": [
    "Approach the hooded figure",
    "Order a drink and observe",
    "Search for exits"
  ],
  "timestamp": "2025-01-15T10:30:05Z"
}
```

### 4. metadata_update
```json
{
  "type": "metadata_update",
  "metadata": {
    "environmental_conditions": "Dimly lit, crowded, noisy",
    "immediate_threats": "Unknown hooded figure",
    "story_progression": "Party entered inn",
    "scene_elements": {...}
  },
  "timestamp": "2025-01-15T10:30:06Z"
}
```

## Required Frontend Changes

### 1. PlayerPage.jsx - Add Streaming State

Add new state to track streaming chunks (around line 32):

```javascript
// Streaming DM state - tracks chunks as they arrive
const [streamingNarrativeBySession, setStreamingNarrativeBySession] = useState({});
const [streamingResponseBySession, setStreamingResponseBySession] = useState({});
const [streamingOptionsBy Session, setStreamingOptionsBySession] = useState({});
const [isNarrativeStreamingBySession, setIsNarrativeStreamingBySession] = useState({});
const [isResponseStreamingBySession, setIsResponseStreamingBySession] = useState({});
```

### 2. PlayerPage.jsx - Add WebSocket Handlers

Add new cases to `handleCampaignUpdate` switch statement (around line 593, before the `default` case):

```javascript
case 'narrative_chunk': {
  console.log('📖 Narrative chunk received:', update.content, 'final:', update.is_final);
  if (sessionId) {
    if (update.is_final && !update.content) {
      // Streaming complete
      setIsNarrativeStreamingBySession(prev => ({ ...prev, [sessionId]: false }));
    } else {
      // Accumulate chunk
      setStreamingNarrativeBySession(prev => ({
        ...prev,
        [sessionId]: (prev[sessionId] || '') + update.content
      }));
      setIsNarrativeStreamingBySession(prev => ({ ...prev, [sessionId]: true }));
    }
  }
  break;
}

case 'player_response_chunk': {
  console.log('💬 Response chunk received:', update.content, 'final:', update.is_final);
  if (sessionId) {
    if (update.is_final && !update.content) {
      // Streaming complete
      setIsResponseStreamingBySession(prev => ({ ...prev, [sessionId]: false }));
    } else {
      // Accumulate chunk
      setStreamingResponseBySession(prev => ({
        ...prev,
        [sessionId]: (prev[sessionId] || '') + update.content
      }));
      setIsResponseStreamingBySession(prev => ({ ...prev, [sessionId]: true }));
    }
  }
  break;
}

case 'player_options': {
  console.log('🎯 Player options received:', update.options);
  if (sessionId && update.options) {
    setStreamingOptionsBySession(prev => ({
      ...prev,
      [sessionId]: update.options
    }));

    // Update structured data with options for compatibility
    setSessionStructuredData(sessionId, (prevData) => ({
      ...prevData,
      player_options: update.options
    }));
  }
  break;
}

case 'metadata_update': {
  console.log('📊 Metadata update received:', Object.keys(update.metadata || {}));
  if (sessionId && update.metadata) {
    // Merge metadata into structured data
    setSessionStructuredData(sessionId, (prevData) => ({
      ...prevData,
      ...update.metadata
    }));
  }
  break;
}
```

### 3. PlayerPage.jsx - Pass Streaming Props

Update the PlayerView component call to pass streaming data (around line 900+):

```javascript
<PlayerView
  structuredData={latestStructuredData}
  campaignMessages={campaignMessages}
  playerFeedback={playerFeedback}
  onAction={handlePlayerAction}
  error={error}
  isConnected={isConnected}
  isLoading={isLoading}
  enableAudio={enableAudio}
  needsUserGesture={needsUserGesture}
  sessionId={currentCampaignId}
  sessionName={sessionNames[currentCampaignId] || currentCampaignId}
  onSelectCampaign={handleSelectCampaign}
  imageRefreshTrigger={imageRefreshTriggersBySession[currentCampaignId]}
  // New streaming props
  streamingNarrative={streamingNarrativeBySession[currentCampaignId] || ''}
  streamingResponse={streamingResponseBySession[currentCampaignId] || ''}
  streamingOptions={streamingOptionsBySession[currentCampaignId] || []}
  isNarrativeStreaming={isNarrativeStreamingBySession[currentCampaignId] || false}
  isResponseStreaming={isResponseStreamingBySession[currentCampaignId] || false}
/>
```

### 4. Create StreamingNarrativeView Component

Create `src/components/player/StreamingNarrativeView.jsx`:

```javascript
import React from 'react';
import './StreamingNarrativeView.css';

const StreamingNarrativeView = ({
  narrative,
  playerResponse,
  options,
  isNarrativeStreaming,
  isResponseStreaming,
  onSelectOption
}) => {
  return (
    <div className="streaming-narrative-container">
      {/* Narrative Section */}
      {narrative && (
        <div className="narrative-section">
          <h3 className="narrative-header">Scene</h3>
          <div className="narrative-content">
            {narrative}
            {isNarrativeStreaming && <span className="streaming-cursor">▮</span>}
          </div>
        </div>
      )}

      {/* Player Response Section */}
      {playerResponse && (
        <div className="response-section">
          <div className="response-content">
            {playerResponse}
            {isResponseStreaming && <span className="streaming-cursor">▮</span>}
          </div>
        </div>
      )}

      {/* Player Options Section */}
      {options && options.length > 0 && !isNarrativeStreaming && !isResponseStreaming && (
        <div className="options-section">
          <h3 className="options-header">What do you do?</h3>
          <div className="options-list">
            {options.map((option, index) => (
              <button
                key={index}
                className="option-button"
                onClick={() => onSelectOption?.(option)}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StreamingNarrativeView;
```

### 5. Create Streaming Styles

Create `src/components/player/StreamingNarrativeView.css`:

```css
.streaming-narrative-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1rem;
  background: var(--bg-primary, #1a1a1a);
  border-radius: 8px;
  color: var(--text-primary, #e0e0e0);
}

.narrative-section,
.response-section {
  padding: 1rem;
  background: var(--bg-secondary, #2a2a2a);
  border-radius: 6px;
}

.narrative-header,
.options-header {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text-accent, #8b9dc3);
}

.narrative-content,
.response-content {
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.streaming-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--accent-primary, #64b5f6);
  font-weight: bold;
  margin-left: 2px;
}

@keyframes blink {
  50% { opacity: 0; }
}

.options-section {
  margin-top: 1rem;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.option-button {
  padding: 0.875rem 1.25rem;
  background: var(--bg-tertiary, #3a3a3a);
  border: 2px solid var(--border-color, #4a4a4a);
  border-radius: 6px;
  color: var(--text-primary, #e0e0e0);
  font-size: 0.95rem;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.option-button:hover {
  background: var(--bg-hover, #4a4a4a);
  border-color: var(--accent-primary, #64b5f6);
  transform: translateX(4px);
}

.option-button:active {
  transform: translateX(2px);
}
```

### 6. Update PlayerView.jsx

Modify `PlayerView.jsx` to use the new StreamingNarrativeView component:

```javascript
import StreamingNarrativeView from './StreamingNarrativeView.jsx';

// Add to props
const PlayerView = ({
  // ... existing props
  streamingNarrative,
  streamingResponse,
  streamingOptions,
  isNarrativeStreaming,
  isResponseStreaming,
  onAction
}) => {

  const handleOptionSelect = (option) => {
    if (onAction) {
      onAction({
        type: 'action',
        message: option,
        originalOption: option
      });
    }
  };

  return (
    <div className="player-view">
      {/* Replace existing narrative display with streaming version */}
      <StreamingNarrativeView
        narrative={streamingNarrative}
        playerResponse={streamingResponse}
        options={streamingOptions}
        isNarrativeStreaming={isNarrativeStreaming}
        isResponseStreaming={isResponseStreaming}
        onSelectOption={handleOptionSelect}
      />

      {/* Keep other existing components */}
      {/* ... */}
    </div>
  );
};
```

## Testing the Integration

1. **Start Backend with Streaming Enabled**
   ```bash
   docker compose --profile dev up backend-dev -d
   docker logs -f gaia-backend-dev
   ```

2. **Start Frontend**
   ```bash
   docker compose --profile dev up frontend-dev -d
   docker logs -f gaia-frontend-dev
   ```

3. **Test Streaming Flow**
   - Open player view in browser
   - Send a message/action
   - Watch for:
     - Narrative chunks appearing progressively
     - Blinking cursor during streaming
     - Player response chunks after narrative
     - Options appearing when both are complete
   - Check browser console for WebSocket messages

4. **Verify WebSocket Messages**
   ```javascript
   // In browser console
   // You should see:
   // 📖 Narrative chunk received: ...
   // 💬 Response chunk received: ...
   // 🎯 Player options received: [...]
   ```

## Debugging

### No Streaming Chunks Appearing

1. Check WebSocket connection:
   ```javascript
   // In browser console
   console.log('WS State:', wsRef.current?.readyState);
   // 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
   ```

2. Check backend logs:
   ```bash
   docker logs --tail 100 gaia-backend-dev | grep "streaming\|narrative_chunk"
   ```

3. Verify backend is using streaming method:
   - Check if `run_dungeon_master_streaming()` is being called
   - Look for log messages like "🎬 Starting streaming DM generation"

### Chunks Not Accumulating

1. Check state updates in React DevTools
2. Verify sessionId matches between chunks
3. Check console for state update errors

### Audio Not Playing with Streaming

Audio generation is integrated with the existing audio system. It should work automatically once chunks complete. If not:

1. Check `auto_tts_service.enabled` and `client_audio_enabled`
2. Verify audio chunks in WebSocket messages
3. Check audio queue in browser

## Migration Strategy

### Phase 1: Backend Only (DONE)
- ✅ Streaming DM orchestrator implemented
- ✅ WebSocket message types defined
- ✅ Campaign broadcaster updated
- ✅ Campaign runner integrated

### Phase 2: Frontend Integration (IN PROGRESS)
- ⏳ Add WebSocket handlers to PlayerPage
- ⏳ Create Streaming NarrativeView component
- ⏳ Update PlayerView to use streaming

### Phase 3: Testing & Refinement
- ⏳ End-to-end testing
- ⏳ Performance optimization
- ⏳ Error handling improvements
- ⏳ Visual polish

## Future Enhancements

1. **Progressive Audio Generation**
   - Generate audio for narrative while player_response streams
   - Overlap audio playback with text streaming

2. **Typing Indicators**
   - Show "DM is thinking..." before first chunk
   - Animate options appearing

3. **Chunk Interpolation**
   - Smooth character-by-character reveal
   - Configurable streaming speed

4. **Retry Logic**
   - Handle network interruptions mid-stream
   - Resume streaming from last chunk

5. **Offline Support**
   - Cache incomplete streams
   - Resume when reconnected

## Related Files

**Backend:**
- `backend/src/game/dnd_agents/streaming_dm_orchestrator.py`
- `backend/src/core/llm/streaming_llm_client.py`
- `backend/src/api/websocket/campaign_broadcaster.py`
- `backend/src/core/session/campaign_runner.py`
- `backend/STREAMING_DM.md`

**Frontend:**
- `frontend/src/components/player/PlayerPage.jsx`
- `frontend/src/components/player/PlayerView.jsx`
- `frontend/src/components/player/StreamingNarrativeView.jsx` (to be created)
- `frontend/src/components/player/StreamingNarrativeView.css` (to be created)

## Support

For questions or issues:
1. Check backend logs: `docker logs gaia-backend-dev`
2. Check frontend logs: `docker logs gaia-frontend-dev`
3. Check browser console for WebSocket messages
4. Review `backend/STREAMING_DM.md` for backend details
5. Review this document for frontend integration
