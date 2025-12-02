# Player-to-DM Suggestion System Specification

## Overview
This specification outlines the transformation of the player view from a direct LLM interaction model to a suggestion-based model where players provide input that is communicated to the DM for approval before progressing the campaign.

**Current Behavior (Problem):**
- Player view directly calls `/api/chat/compat` endpoint
- Player actions immediately trigger LLM and progress the scene
- DM has no control over when/how player actions affect the story

**Desired Behavior (Solution):**
- Player view sends suggestions to DM via WebSocket
- DM receives player suggestions in a dedicated UI panel
- DM reviews, edits, and manually submits suggestions to LLM
- Only DM can progress the campaign/scene

---

## Game Flow

### New Game Loop
```
1. DM interacts with LLM → Story progresses
2. Updates broadcast to Player View via WebSocket (already implemented)
3. Player selects options or enters text → Creates "suggestion"
4. Suggestion sent to DM via WebSocket (NEW)
5. DM views suggestion in UI panel (NEW)
6. DM reviews, edits, and submits to chat (NEW)
7. → Returns to step 1
```

---

## Current Implementation Analysis

### Player View - Direct LLM Interaction Points

**1. PlayerView.jsx (lines 46-74)**
```javascript
const handlePlayerAction = async (action) => {
  // ❌ REMOVE: Direct API call to LLM
  const response = await apiService.sendMessage(action.message, campaignId);
}
```
- **Location:** `frontend/src/components/player/PlayerView.jsx:56`
- **Action:** Remove this API call
- **Replacement:** Call parent callback to send suggestion

**2. PlayerPage.jsx (lines 267-291)**
```javascript
const handlePlayerAction = async (action) => {
  // ❌ REMOVE: Direct API call to LLM
  const response = await apiService.sendMessage(action.message, currentCampaignId);
}
```
- **Location:** `frontend/src/components/player/PlayerPage.jsx:279`
- **Action:** Remove this API call
- **Replacement:** Send suggestion via WebSocket

**3. PlayerNarrativeView.jsx (lines 31-38)**
```javascript
const handlePlayerOption = (option) => {
  // ✅ KEEP: Calls parent handler (PlayerView/PlayerPage)
  onPlayerAction({ type: 'player_option', message: option });
}
```
- **Location:** `frontend/src/components/player/PlayerNarrativeView/PlayerNarrativeView.jsx:31-38`
- **Action:** No changes needed (already uses callback pattern)

**4. PlayerControls.jsx (lines 79-86)**
```javascript
const handlePlayerOption = (option) => {
  // ✅ KEEP: Calls parent handler
  onPlayerAction({ type: 'player_option', message: option });
}
```
- **Location:** `frontend/src/components/player/PlayerControls/PlayerControls.jsx:79-86`
- **Action:** No changes needed (already uses callback pattern)

### API Service - Scene Progression Endpoints

**apiService.sendMessage() (apiService.js:203-217)**
- **Endpoint:** `POST /api/chat/compat`
- **Purpose:** Sends chat message to LLM
- **Action:** Player view must NOT call this endpoint
- **Location:** `frontend/src/services/apiService.js:203-217`

---

## Architecture Design

### WebSocket Communication

#### Existing: DM → Player
- ✅ Already implemented
- **Endpoint:** `/ws/campaign/player`
- **Events:** `campaign_updated`, `campaign_loaded`, `campaign_deactivated`
- **Implementation:** `backend/src/api/websocket/campaign_broadcaster.py`

#### New: Player → DM
- **Endpoint:** `/ws/campaign/dm` (already exists, needs enhancement)
- **Event Type:** `player_suggestion`
- **Payload Format:**
```json
{
  "type": "player_suggestion",
  "timestamp": "2025-01-15T10:30:00Z",
  "player_id": "player_123",
  "suggestion_id": "uuid-v4",
  "suggestion_type": "option" | "voice" | "dice_roll",
  "content": "I want to investigate the mysterious door",
  "metadata": {
    "character_name": "Gaius",
    "original_option": "Investigate the surroundings"
  }
}
```

### Backend Components

#### 1. Enhanced CampaignBroadcaster

**File:** `backend/src/api/websocket/campaign_broadcaster.py`

**Existing Methods (Keep):**
- `broadcast_to_dm()` - lines 178-210 (already exists, will be used)
- `connect_dm()` - lines 94-111
- `disconnect_dm()` - lines 123-131

**New Additions:**

```python
class CampaignBroadcaster:
    def __init__(self):
        # ... existing code ...
        self.pending_suggestions: Dict[str, List[Dict]] = {}  # campaign_id -> [suggestions]

    async def add_player_suggestion(self, campaign_id: str, suggestion: Dict):
        """Store player suggestion and broadcast to DM.

        Args:
            campaign_id: Campaign identifier
            suggestion: Player suggestion data
        """
        if campaign_id not in self.pending_suggestions:
            self.pending_suggestions[campaign_id] = []

        self.pending_suggestions[campaign_id].append(suggestion)

        # Broadcast to DM
        await self.broadcast_to_dm("player_suggestion", {
            "campaign_id": campaign_id,
            "suggestion": suggestion
        })

        logger.info(f"📩 Player suggestion added for campaign {campaign_id}: {suggestion.get('content')[:50]}...")

    def get_pending_suggestions(self, campaign_id: str) -> List[Dict]:
        """Get all pending suggestions for a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            List of pending suggestions
        """
        return self.pending_suggestions.get(campaign_id, [])

    def clear_suggestion(self, campaign_id: str, suggestion_id: str):
        """Remove a suggestion after DM processes it.

        Args:
            campaign_id: Campaign identifier
            suggestion_id: Suggestion to remove
        """
        if campaign_id in self.pending_suggestions:
            self.pending_suggestions[campaign_id] = [
                s for s in self.pending_suggestions[campaign_id]
                if s.get("suggestion_id") != suggestion_id
            ]
            logger.info(f"🗑️  Cleared suggestion {suggestion_id} from campaign {campaign_id}")
```

#### 2. WebSocket Endpoint Enhancement

**File:** `backend/src/api/main.py`

**Modify Existing Player WebSocket Endpoint:**

```python
@app.websocket("/ws/campaign/player")
async def campaign_player_endpoint(websocket: WebSocket, player_id: str = None):
    """WebSocket endpoint for players to receive campaign updates and send suggestions."""
    connection = await campaign_broadcaster.connect_player(websocket, player_id)
    try:
        while True:
            # Receive messages from player
            message = await websocket.receive_text()
            data = json.loads(message)

            # NEW: Handle player suggestions
            if data.get("type") == "player_suggestion":
                suggestion = {
                    "suggestion_id": str(uuid.uuid4()),
                    "player_id": player_id or "unknown",
                    "timestamp": datetime.now().isoformat(),
                    "suggestion_type": data.get("suggestion_type", "voice"),
                    "content": data.get("content", ""),
                    "metadata": data.get("metadata", {})
                }

                campaign_id = data.get("campaign_id")
                if campaign_id:
                    await campaign_broadcaster.add_player_suggestion(campaign_id, suggestion)

                    # Send acknowledgment back to player
                    await websocket.send_json({
                        "type": "suggestion_received",
                        "suggestion_id": suggestion["suggestion_id"],
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    logger.warning(f"Player suggestion missing campaign_id: {data}")

            # Handle ping/pong for connection health
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        await campaign_broadcaster.disconnect_player(connection)
    except Exception as e:
        logger.error(f"Error in player WebSocket: {e}")
        await campaign_broadcaster.disconnect_player(connection)
```

#### 3. Optional REST API Endpoint (Fallback)

**File:** `backend/src/api/main.py`

**New Endpoint:**

```python
@app.get("/api/campaigns/{campaign_id}/suggestions")
async def get_player_suggestions(campaign_id: str):
    """Get pending player suggestions for a campaign.

    Fallback endpoint if WebSocket not available.
    """
    suggestions = campaign_broadcaster.get_pending_suggestions(campaign_id)
    return {
        "success": True,
        "campaign_id": campaign_id,
        "suggestions": suggestions,
        "count": len(suggestions)
    }

@app.delete("/api/campaigns/{campaign_id}/suggestions/{suggestion_id}")
async def clear_player_suggestion(campaign_id: str, suggestion_id: str):
    """Clear a processed suggestion."""
    campaign_broadcaster.clear_suggestion(campaign_id, suggestion_id)
    return {
        "success": True,
        "message": "Suggestion cleared"
    }
```

---

## Frontend Implementation

### Part 1: Remove Direct LLM Calls from Player View

#### Changes to PlayerView.jsx

**File:** `frontend/src/components/player/PlayerView.jsx`

**Current Code (lines 45-74):**
```javascript
const handlePlayerAction = async (action) => {
  if (!campaignId) {
    setError('No campaign ID provided');
    return;
  }

  setIsLoading(true);
  setError(null);

  try {
    const response = await apiService.sendMessage(action.message, campaignId);

    // Update game state with new response
    if (response.structuredData) {
      setGameState(response.structuredData);
    }

    // Notify parent component
    if (onPlayerAction) {
      onPlayerAction(response);
    }

  } catch (error) {
    console.error('Player action failed:', error);
    setError(error.message || 'Failed to process player action');
  } finally {
    setIsLoading(false);
  }
};
```

**New Code:**
```javascript
const handlePlayerAction = (action) => {
  if (!campaignId) {
    setError('No campaign ID provided');
    return;
  }

  // Send suggestion to parent (PlayerPage) instead of calling LLM
  if (onPlayerAction) {
    onPlayerAction(action);
  }

  // Show feedback to player
  console.log('📤 Player action sent as suggestion:', action);
};
```

#### Changes to PlayerPage.jsx

**File:** `frontend/src/components/player/PlayerPage.jsx`

**Current Code (lines 267-291):**
```javascript
const handlePlayerAction = async (action) => {
  if (!currentCampaignId) {
    setError('No campaign selected');
    return;
  }

  setIsLoading(true);
  setError(null);

  try {
    const response = await apiService.sendMessage(action.message, currentCampaignId);

    // Update game state with new response
    if (response.structuredData || response.structured_data) {
      const structData = response.structuredData || response.structured_data;
      const transformedData = transformStructuredData(structData);
      setLatestStructuredData(transformedData);
    }
  } catch (error) {
    console.error('Player action failed:', error);
    setError(error.message || 'Failed to process player action');
  } finally {
    setIsLoading(false);
  }
};
```

**New Code:**
```javascript
const [playerFeedback, setPlayerFeedback] = useState('');

const handlePlayerAction = (action) => {
  if (!currentCampaignId) {
    setError('No campaign selected');
    return;
  }

  // Send suggestion via WebSocket instead of calling LLM
  sendPlayerSuggestion(action);
};

const sendPlayerSuggestion = (action) => {
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    const suggestion = {
      type: "player_suggestion",
      campaign_id: currentCampaignId,
      suggestion_type: action.type || "voice",
      content: action.message,
      metadata: {
        character_name: demoCharacter?.name || "Player",
        original_option: action.originalOption,
        timestamp: new Date().toISOString()
      }
    };

    wsRef.current.send(JSON.stringify(suggestion));
    console.log('📤 Sent player suggestion to DM:', suggestion);

    // Show feedback to player
    setPlayerFeedback('✅ Suggestion sent to DM! Waiting for DM to progress the story...');

    // Clear feedback after 5 seconds
    setTimeout(() => setPlayerFeedback(''), 5000);
  } else {
    setError('Not connected to game server. Please refresh the page.');
  }
};
```

**Add Feedback UI (in PlayerPage render):**
```javascript
{/* Player Feedback Message */}
{playerFeedback && (
  <div className="player-feedback-banner">
    {playerFeedback}
  </div>
)}
```

**Add CSS:**
```css
.player-feedback-banner {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  padding: 1rem 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
  z-index: 1000;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
```

### Part 2: DM View - Player Suggestion Panel

#### New Component: PlayerSuggestionPanel.jsx

**File:** `frontend/src/components/dm/PlayerSuggestionPanel.jsx`

```javascript
import React, { useState, useEffect } from 'react';
import './PlayerSuggestionPanel.css';

const PlayerSuggestionPanel = ({ campaignId, dmWebSocket, onInsertSuggestion }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [hasNewSuggestions, setHasNewSuggestions] = useState(false);

  // Listen for player suggestions from WebSocket
  useEffect(() => {
    if (!dmWebSocket) return;

    const handleMessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'player_suggestion' && data.suggestion) {
        console.log('📩 Received player suggestion:', data.suggestion);

        setSuggestions(prev => [data.suggestion, ...prev]);
        setHasNewSuggestions(true);

        // Play notification sound (optional)
        playNotificationSound();

        // Auto-clear "new" badge after 5 seconds
        setTimeout(() => setHasNewSuggestions(false), 5000);
      }
    };

    dmWebSocket.addEventListener('message', handleMessage);

    return () => {
      dmWebSocket.removeEventListener('message', handleMessage);
    };
  }, [dmWebSocket]);

  const handleInsert = (suggestion) => {
    if (onInsertSuggestion) {
      onInsertSuggestion(suggestion.content);
    }

    // Remove from list
    setSuggestions(prev => prev.filter(s => s.suggestion_id !== suggestion.suggestion_id));
  };

  const handleDismiss = (suggestionId) => {
    setSuggestions(prev => prev.filter(s => s.suggestion_id !== suggestionId));
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins === 1) return '1 min ago';
    if (diffMins < 60) return `${diffMins} min ago`;
    return date.toLocaleTimeString();
  };

  const playNotificationSound = () => {
    // Optional: Play a subtle notification sound
    const audio = new Audio('/notification.mp3');
    audio.volume = 0.3;
    audio.play().catch(() => {});
  };

  return (
    <div className="player-suggestion-panel">
      <div className="panel-header">
        <h3>
          Player Suggestions
          {hasNewSuggestions && <span className="new-badge">NEW</span>}
        </h3>
        {suggestions.length > 0 && (
          <button
            className="clear-all-btn"
            onClick={() => setSuggestions([])}
            title="Clear all suggestions"
          >
            Clear All
          </button>
        )}
      </div>

      {suggestions.length === 0 ? (
        <div className="no-suggestions">
          <p>No player suggestions yet</p>
          <span className="no-suggestions-icon">💬</span>
        </div>
      ) : (
        <ul className="suggestion-list">
          {suggestions.map(suggestion => (
            <li key={suggestion.suggestion_id} className="suggestion-item">
              <div className="suggestion-header">
                <span className="character-name">
                  {suggestion.metadata?.character_name || 'Unknown Player'}
                </span>
                <span className="suggestion-time">
                  {formatTime(suggestion.timestamp)}
                </span>
              </div>

              <div className="suggestion-content">
                {suggestion.content}
              </div>

              {suggestion.metadata?.original_option && (
                <div className="suggestion-context">
                  <em>From option: {suggestion.metadata.original_option}</em>
                </div>
              )}

              <div className="suggestion-actions">
                <button
                  className="insert-btn"
                  onClick={() => handleInsert(suggestion)}
                  title="Insert suggestion into chat input"
                >
                  📝 Insert to Chat
                </button>
                <button
                  className="dismiss-btn"
                  onClick={() => handleDismiss(suggestion.suggestion_id)}
                  title="Dismiss this suggestion"
                >
                  ✕ Dismiss
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default PlayerSuggestionPanel;
```

#### Component CSS: PlayerSuggestionPanel.css

**File:** `frontend/src/components/dm/PlayerSuggestionPanel.css`

```css
.player-suggestion-panel {
  background: rgba(26, 26, 26, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1rem;
  margin-top: 1rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.panel-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #f59e0b;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.new-badge {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.clear-all-btn {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid #ef4444;
  color: #fecaca;
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-all-btn:hover {
  background: rgba(239, 68, 68, 0.3);
  transform: scale(1.05);
}

.no-suggestions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: #6b7280;
  text-align: center;
}

.no-suggestions-icon {
  font-size: 2rem;
  opacity: 0.5;
  margin-top: 0.5rem;
}

.suggestion-list {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 400px;
  overflow-y: auto;
}

.suggestion-item {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  transition: all 0.2s;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.suggestion-item:hover {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.5);
  transform: translateX(4px);
}

.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.character-name {
  font-weight: 600;
  color: #fbbf24;
  font-size: 0.9rem;
}

.suggestion-time {
  font-size: 0.75rem;
  color: #9ca3af;
  font-family: monospace;
}

.suggestion-content {
  color: #f3f4f6;
  font-size: 1rem;
  line-height: 1.5;
  margin-bottom: 0.75rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  border-left: 3px solid #3b82f6;
}

.suggestion-context {
  font-size: 0.85rem;
  color: #9ca3af;
  font-style: italic;
  margin-bottom: 0.75rem;
}

.suggestion-actions {
  display: flex;
  gap: 0.5rem;
}

.insert-btn,
.dismiss-btn {
  flex: 1;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.insert-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: 1px solid #10b981;
  color: white;
}

.insert-btn:hover {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
}

.dismiss-btn {
  background: rgba(107, 114, 128, 0.2);
  border: 1px solid #6b7280;
  color: #d1d5db;
}

.dismiss-btn:hover {
  background: rgba(107, 114, 128, 0.3);
  border-color: #9ca3af;
}

/* Scrollbar styling */
.suggestion-list::-webkit-scrollbar {
  width: 6px;
}

.suggestion-list::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 3px;
}

.suggestion-list::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5);
  border-radius: 3px;
}

.suggestion-list::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.7);
}
```

#### Integration into GameDashboard.jsx

**File:** `frontend/src/components/GameDashboard.jsx`

**Add import:**
```javascript
import PlayerSuggestionPanel from './dm/PlayerSuggestionPanel.jsx';
```

**Add below Player Options section (after line 149):**
```javascript
{/* Player Options Section */}
<div className="dashboard-player-options-panel">
  {((latestStructuredData.turn && String(latestStructuredData.turn).trim()) ||
    (latestStructuredData.player_options && String(latestStructuredData.player_options).trim())) && (
    <TurnView
      turn={latestStructuredData.player_options || latestStructuredData.turn}
      showHeader={true}
      onPlayStop={handlePlayStopOptions}
      isPlaying={isPlayingOptions}
    />
  )}
</div>

{/* Player Suggestion Panel - NEW */}
<div className="dashboard-player-suggestions-panel">
  <PlayerSuggestionPanel
    campaignId={campaignId}
    dmWebSocket={dmWebSocket}
    onInsertSuggestion={onInsertSuggestion}
  />
</div>
```

**Add props to GameDashboard component:**
```javascript
const GameDashboard = forwardRef(({
  latestStructuredData,
  latestDMData,
  onImageGenerated,
  campaignId,
  dmWebSocket,        // NEW
  onInsertSuggestion  // NEW
}) => {
```

#### Integration into App.jsx

**File:** `frontend/src/App.jsx`

**Add state for DM WebSocket:**
```javascript
const [dmWebSocket, setDmWebSocket] = useState(null);
const chatInputRef = useRef(null);
```

**Add DM WebSocket connection in useEffect:**
```javascript
useEffect(() => {
  // Connect to DM WebSocket for receiving player suggestions
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
  const wsUrl = `${wsProtocol}//${wsHost}/ws/campaign/dm`;

  console.log('🎭 Connecting DM WebSocket:', wsUrl);
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('🎭 DM WebSocket connected');
  };

  ws.onerror = (error) => {
    console.error('🎭 DM WebSocket error:', error);
  };

  ws.onclose = () => {
    console.log('🎭 DM WebSocket disconnected');
  };

  setDmWebSocket(ws);

  return () => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
  };
}, []);
```

**Add handler to insert suggestions into chat:**
```javascript
const handleInsertSuggestion = (suggestionText) => {
  // Insert into chat input field
  setInputMessage(suggestionText);

  // Focus chat input
  if (chatInputRef.current) {
    chatInputRef.current.focus();
  }

  console.log('📝 Inserted player suggestion into chat:', suggestionText);
};
```

**Pass props to GameDashboard:**
```javascript
<GameDashboard
  ref={gameDashboardRef}
  latestStructuredData={latestStructuredData}
  latestDMData={latestDMData}
  onImageGenerated={handleImageGenerated}
  campaignId={activeCampaignId}
  dmWebSocket={dmWebSocket}           // NEW
  onInsertSuggestion={handleInsertSuggestion}  // NEW
/>
```

**Add ref to chat input:**
```javascript
<input
  ref={chatInputRef}
  type="text"
  value={inputMessage}
  onChange={(e) => setInputMessage(e.target.value)}
  // ... other props
/>
```

---

## UI/UX Design

### Player View Changes

**Feedback States:**

1. **Suggestion Sent:**
```
┌─────────────────────────────────────┐
│  ✅ Suggestion sent to DM!          │
│  ⏳ Waiting for DM to continue...   │
└─────────────────────────────────────┘
```

2. **Not Connected:**
```
┌─────────────────────────────────────┐
│  ❌ Not connected to game server    │
│  Please refresh the page.           │
└─────────────────────────────────────┘
```

### DM View - Player Suggestion Panel

**Visual Design:**
```
┌─────────────────────────────────────┐
│  Player Suggestions    [NEW]        │
│                     [Clear All]     │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐ │
│  │ Gaius · 2 min ago             │ │
│  │ ┌─────────────────────────┐   │ │
│  │ │ I want to investigate   │   │ │
│  │ │ the mysterious door     │   │ │
│  │ └─────────────────────────┘   │ │
│  │ From option: Investigate...   │ │
│  │                               │ │
│  │ [📝 Insert to Chat] [✕ Dismiss]│ │
│  └───────────────────────────────┘ │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ Eldrin · 5 min ago            │ │
│  │ ┌─────────────────────────┐   │ │
│  │ │ I cast detect magic     │   │ │
│  │ └─────────────────────────┘   │ │
│  │                               │ │
│  │ [📝 Insert to Chat] [✕ Dismiss]│ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Remove Player → LLM Direct Access

**Estimated Time:** 2-3 hours

**Tasks:**
1. ✅ Modify `PlayerView.jsx`
   - Remove `apiService.sendMessage()` call (line 56)
   - Simplify `handlePlayerAction` to callback only

2. ✅ Modify `PlayerPage.jsx`
   - Remove `apiService.sendMessage()` call (line 279)
   - Implement `sendPlayerSuggestion()` function
   - Add WebSocket suggestion sending
   - Add player feedback state and UI

3. ✅ Add feedback banner CSS to PlayerPage

4. ✅ Testing
   - Verify player actions no longer call `/api/chat/compat`
   - Verify no console errors
   - Verify UI shows feedback message
   - Verify WebSocket sends suggestion (check browser DevTools)

### Phase 2: Backend - Player Suggestion System

**Estimated Time:** 3-4 hours

**Tasks:**
1. ✅ Modify `campaign_broadcaster.py`
   - Add `pending_suggestions` dict to `__init__`
   - Implement `add_player_suggestion()` method
   - Implement `get_pending_suggestions()` method
   - Implement `clear_suggestion()` method

2. ✅ Modify `main.py` - Player WebSocket
   - Enhance `/ws/campaign/player` endpoint
   - Add message receiving logic
   - Add `player_suggestion` type handling
   - Add acknowledgment response

3. ✅ Add REST fallback endpoints (optional)
   - `GET /api/campaigns/{id}/suggestions`
   - `DELETE /api/campaigns/{id}/suggestions/{id}`

4. ✅ Testing
   - Test WebSocket message flow
   - Test suggestion storage in memory
   - Test DM broadcast
   - Check logs for proper logging
   - Use test script or browser to send mock suggestions

### Phase 3: DM View - Suggestion Panel UI

**Estimated Time:** 4-5 hours

**Tasks:**
1. ✅ Create `PlayerSuggestionPanel.jsx`
   - Implement component with all features
   - Add WebSocket message listener
   - Add insert/dismiss handlers
   - Add time formatting
   - Add notification sound (optional)

2. ✅ Create `PlayerSuggestionPanel.css`
   - Style panel container
   - Style suggestion items
   - Add animations (slide in, pulse)
   - Add hover effects
   - Style scrollbar

3. ✅ Modify `GameDashboard.jsx`
   - Import PlayerSuggestionPanel
   - Add component below Player Options
   - Pass props (campaignId, dmWebSocket, onInsertSuggestion)
   - Update component signature

4. ✅ Modify `App.jsx`
   - Add DM WebSocket connection
   - Add `handleInsertSuggestion()` handler
   - Add chat input ref
   - Pass props to GameDashboard

5. ✅ Testing
   - Test DM WebSocket connection
   - Test suggestion display
   - Test insert to chat functionality
   - Test dismiss functionality
   - Test "Clear All" button
   - Test visual states (new badge, animations)

### Phase 4: Integration Testing

**Estimated Time:** 2-3 hours

**End-to-End Flow:**
1. ✅ Start backend server (`docker compose up backend-dev`)
2. ✅ Start frontend (`docker compose up frontend-dev`)
3. ✅ Open DM view (http://localhost:3000)
4. ✅ Start a campaign
5. ✅ Open player view in different tab (http://localhost:3000/player)
6. ✅ Player selects option or enters text
7. ✅ Check: DM receives suggestion within 1 second
8. ✅ Check: Suggestion appears in panel with correct data
9. ✅ Click "Insert to Chat" in DM view
10. ✅ Check: Text appears in chat input
11. ✅ Submit chat message as DM
12. ✅ Check: Campaign progresses
13. ✅ Check: Player view updates with new narrative

**Edge Cases:**
- ✅ Test WebSocket disconnection/reconnection
- ✅ Test multiple rapid suggestions (verify no duplicates)
- ✅ Test suggestion persistence during page refresh
- ✅ Test with multiple player views open
- ✅ Test dismiss and clear all functionality

---

## Security Considerations [Optional - DO NOT IMPLEMENT]

1. **Authentication**
   - Verify player WebSocket connections are authenticated
   - Validate campaign access before accepting suggestions
   - Rate limit: Max 1 suggestion per player per 5 seconds

2. **Input Validation**
   - Sanitize suggestion content before broadcasting
   - Limit suggestion content length (max 500 characters)
   - Validate suggestion_type enum values

3. **Authorization**
   - Only DM can call `/api/chat/compat` endpoint
   - Player suggestions cannot trigger LLM directly
   - Verify campaign_id matches active campaign

4. **Rate Limiting**
   - Prevent suggestion spam: 1 per 5 seconds per player
   - Prevent WebSocket abuse: Connection limits per IP
   - Clear old suggestions after 1 hour automatically

---

## Success Criteria

✅ Player view cannot directly progress campaign (API calls removed)
✅ Player suggestions appear in DM view within 1 second via WebSocket
✅ DM can insert suggestions to chat with one click
✅ Campaign only progresses when DM submits to LLM
✅ Player receives feedback: "Suggestion sent to DM"
✅ WebSocket reconnection handles pending suggestions gracefully
✅ No loss of suggestions during network issues (stored server-side)
✅ UI is intuitive and requires no documentation
✅ Performance: No lag or delays in suggestion delivery
✅ No console errors in browser or server logs

---

## Future Enhancements [Optional - DO NOT IMPLEMENT]

### Post-MVP
1. **Suggestion Templates**
   - Pre-defined action templates for common actions
   - Quick-select buttons for players
   - Customizable templates per campaign

2. **Multi-Player Voting**
   - Multiple players can vote on suggested actions
   - DM sees vote counts
   - Majority vote highlights suggestion

3. **Suggestion History**
   - View past suggestions and DM responses
   - Search/filter suggestion history
   - Export campaign log with all suggestions

4. **Rich Suggestions**
   - Include dice rolls in suggestions
   - Attach character stats/abilities
   - Link to inventory items

5. **Notification System**
   - Browser notifications for DM when suggestions arrive
   - Mobile notifications (if mobile app exists)
   - Configurable notification preferences

6. **Auto-Suggestion AI**
   - AI analyzes context and suggests player options
   - ML-powered action recommendations
   - Learns from DM approval patterns

7. **Suggestion Analytics**
   - Track which suggestions DMs use most
   - Player engagement metrics
   - Improve AI suggestions based on data

---

## File Structure Summary

### New Files
```
frontend/src/components/dm/
  ├── PlayerSuggestionPanel.jsx    (NEW)
  └── PlayerSuggestionPanel.css    (NEW)

docs/
  └── player-to-dm-suggestion-system.md  (THIS FILE)
```

### Modified Files
```
backend/src/api/
  ├── main.py                      (MODIFY: WebSocket endpoints)
  └── websocket/
      └── campaign_broadcaster.py  (MODIFY: Add suggestion methods)

frontend/src/
  ├── App.jsx                      (MODIFY: DM WebSocket, handlers)
  └── components/
      ├── GameDashboard.jsx        (MODIFY: Add PlayerSuggestionPanel)
      └── player/
          ├── PlayerView.jsx       (MODIFY: Remove API call)
          └── PlayerPage.jsx       (MODIFY: WebSocket suggestions)
```

---

## Testing Checklist

### Unit Tests
- [ ] Test `add_player_suggestion()` method
- [ ] Test `get_pending_suggestions()` method
- [ ] Test `clear_suggestion()` method
- [ ] Test WebSocket message parsing
- [ ] Test suggestion validation

### Integration Tests
- [ ] Test player → backend → DM message flow
- [ ] Test suggestion persistence across reconnects
- [ ] Test multiple concurrent suggestions
- [ ] Test rate limiting
- [ ] Test authentication/authorization

### E2E Tests
- [ ] Full game loop: DM → Player → Suggestion → DM → LLM
- [ ] Multi-player scenario
- [ ] Network failure recovery

### Performance Tests [Optional - DO NOT PERFORM]
- [ ] 10 concurrent player connections
- [ ] 100 suggestions per minute load test
- [ ] WebSocket memory leak test
- [ ] Suggestion storage scalability

---

## Dependencies

### Backend
- None (uses existing FastAPI WebSocket support)

### Frontend
- None (uses existing React hooks and WebSocket API)

### Optional [DO NOT IMPLEMENT]
- Notification sound file: `/public/notification.mp3` (for audio alerts)

---

## Documentation Updates Needed

1. Update `README.md` with new player flow
2. Add WebSocket API documentation
3. Create DM guide: "How to handle player suggestions"
4. Create player guide: "How your actions are processed"
5. Update architecture diagrams

---

## Risks & Mitigation

### Risk 1: WebSocket Connection Failures
**Impact:** Suggestions lost, players can't interact
**Mitigation:**
- Implement REST API fallback
- Store suggestions server-side
- Auto-reconnect logic with exponential backoff
- Show clear error messages to user

### Risk 2: Suggestion Spam [Optional - DO NOT IMPLEMENT]
**Impact:** DM overwhelmed with suggestions
**Mitigation:**
- Rate limiting: 1 suggestion per 5 seconds
- "Clear All" button for DM
- Auto-expire old suggestions (1 hour)
- Suggestion collapse/grouping

### Risk 3: DM Doesn't Check Suggestions
**Impact:** Players feel ignored, poor UX
**Mitigation:**
- Visual "NEW" badge and pulse animation
- Optional sound notification
- Auto-insert most recent suggestion after timeout (optional)
- Clear feedback to player: "Waiting for DM"

### Risk 4: Latency Issues [Optional - DO NOT IMPLEMENT]
**Impact:** Delayed suggestions, poor real-time feel
**Mitigation:**
- WebSocket for instant delivery (not polling)
- Show timestamp on suggestions
- Optimize WebSocket message size
- Monitor latency in production

---

## Conclusion

This specification provides a complete plan to transform the player view from direct LLM interaction to a DM-mediated suggestion system. The implementation is structured in clear phases, with detailed code examples, testing procedures, and risk mitigation strategies.

**Estimated Total Implementation Time:** 11-15 hours

**Key Benefits:**
- Full DM control over campaign progression
- Better game flow and pacing
- No unwanted scene changes from players
- Clear communication channel between players and DM
- Scalable architecture for future multiplayer features
