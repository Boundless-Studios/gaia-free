# WebSocket-Based DM-Player Synchronization Specification

## Overview
This specification outlines a WebSocket-based push notification system to replace having to manually refresh the page to get updates between DM and Player views. The solution provides real-time updates, eliminates server overhead, and ensures consistent state synchronization.

## Proposed Solution: WebSocket Broadcasting System

### Architecture Overview

**Core Components:**
1. **CampaignBroadcaster**: Central WebSocket connection manager
2. **Player WebSocket Endpoint**: `/ws/campaign/player` - receives updates
3. **DM WebSocket Endpoint**: `/ws/campaign/dm` - triggers broadcasts (optional)
4. **Event Integration**: Hooks into orchestrator for automatic broadcasting
5. **Frontend WebSocket Client**: Real-time update handling in PlayerPage

### Technical Implementation

#### Backend Implementation

**1. WebSocket Infrastructure (`backend/src/api/main.py`)**

```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict
import json
import logging
from datetime import datetime

class CampaignBroadcaster:
    """Manages WebSocket connections for campaign state broadcasting."""

    def __init__(self):
        self.player_connections: List[WebSocket] = []
        self.dm_connection: Optional[WebSocket] = None
        self.logger = logging.getLogger(__name__)

    async def connect_player(self, websocket: WebSocket, player_id: str = None):
        """Connect a player to receive campaign updates."""
        await websocket.accept()
        self.player_connections.append(websocket)
        self.logger.info(f"Player connected. Total connections: {len(self.player_connections)}")

        # Send current campaign state if available
        if hasattr(orchestrator, 'active_campaign_id') and orchestrator.active_campaign_id:
            current_state = await self._get_current_campaign_state()
            if current_state:
                await self._send_to_connection(websocket, {
                    "type": "campaign_active",
                    "campaign_id": orchestrator.active_campaign_id,
                    "structured_data": current_state,
                    "timestamp": datetime.now().isoformat()
                })

    async def connect_dm(self, websocket: WebSocket):
        """Connect DM for optional bidirectional communication."""
        await websocket.accept()
        self.dm_connection = websocket
        self.logger.info("DM connected to campaign WebSocket")

    async def disconnect_player(self, websocket: WebSocket):
        """Remove player connection."""
        if websocket in self.player_connections:
            self.player_connections.remove(websocket)
            self.logger.info(f"Player disconnected. Remaining connections: {len(self.player_connections)}")

    async def disconnect_dm(self):
        """Remove DM connection."""
        self.dm_connection = None
        self.logger.info("DM disconnected from campaign WebSocket")

    async def broadcast_campaign_update(self, event_type: str, data: Dict):
        """Broadcast campaign updates to all connected players."""
        if not self.player_connections:
            return

        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data
        }

        # Send to all player connections
        disconnected = []
        for connection in self.player_connections:
            try:
                await self._send_to_connection(connection, message)
            except Exception as e:
                self.logger.warning(f"Failed to send to player connection: {e}")
                disconnected.append(connection)

        # Remove failed connections
        for connection in disconnected:
            await self.disconnect_player(connection)

    async def _send_to_connection(self, websocket: WebSocket, data: Dict):
        """Send data to specific WebSocket connection."""
        await websocket.send_json(data)

    async def _get_current_campaign_state(self) -> Optional[Dict]:
        """Get current campaign structured data."""
        if not orchestrator or not orchestrator.active_campaign_id:
            return None

        try:
            # Get campaign state without side effects
            campaign_data = await campaign_service.load_simple_campaign_readonly(
                orchestrator.active_campaign_id
            )
            return campaign_data.get('structured_data')
        except Exception as e:
            self.logger.error(f"Failed to get campaign state: {e}")
            return None

# Global broadcaster instance
campaign_broadcaster = CampaignBroadcaster()

@app.websocket("/ws/campaign/player")
async def campaign_player_endpoint(websocket: WebSocket, player_id: str = None):
    """WebSocket endpoint for players to receive campaign updates."""
    await campaign_broadcaster.connect_player(websocket, player_id)
    try:
        while True:
            # Keep connection alive, handle any player messages
            message = await websocket.receive_text()
            # Optional: Handle player status messages (typing, ready, etc.)

    except WebSocketDisconnect:
        await campaign_broadcaster.disconnect_player(websocket)
    except Exception as e:
        logger.error(f"Error in player WebSocket: {e}")
        await campaign_broadcaster.disconnect_player(websocket)

@app.websocket("/ws/campaign/dm")
async def campaign_dm_endpoint(websocket: WebSocket):
    """Optional WebSocket endpoint for DM bidirectional communication."""
    await campaign_broadcaster.connect_dm(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            # Handle DM-specific messages if needed

    except WebSocketDisconnect:
        await campaign_broadcaster.disconnect_dm()
    except Exception as e:
        logger.error(f"Error in DM WebSocket: {e}")
        await campaign_broadcaster.disconnect_dm()
```

**2. Orchestrator Integration (`backend/src/core/agent_orchestration/orchestrator.py`)**

```python
class Orchestrator:
    def __init__(self):
        # ... existing initialization ...
        self.active_campaign_id = None
        self._campaign_broadcaster = None  # Will be injected

    def set_campaign_broadcaster(self, broadcaster):
        """Inject campaign broadcaster for WebSocket notifications."""
        self._campaign_broadcaster = broadcaster

    async def activate_campaign(self, campaign_id: str) -> bool:
        """Activate campaign and notify all players."""
        result = self._original_activate_campaign(campaign_id)  # Original logic

        if result and self._campaign_broadcaster:
            # Get structured data for broadcast
            structured_data = await self._get_structured_campaign_data(campaign_id)

            # Broadcast to all connected players
            await self._campaign_broadcaster.broadcast_campaign_update(
                "campaign_loaded",
                {
                    "campaign_id": campaign_id,
                    "structured_data": structured_data
                }
            )

        return result

    async def process_chat_message(self, message: str) -> Dict:
        """Process chat and broadcast updates."""
        result = await self._original_process_chat(message)  # Original logic

        if self._campaign_broadcaster and 'structured_data' in result:
            # Broadcast updated game state
            await self._campaign_broadcaster.broadcast_campaign_update(
                "campaign_updated",
                {
                    "campaign_id": self.active_campaign_id,
                    "structured_data": result['structured_data']
                }
            )

        return result
```

**3. Main App Integration**

```python
# In main.py startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global orchestrator, campaign_broadcaster

    # Initialize orchestrator
    orchestrator = Orchestrator()

    # Inject broadcaster into orchestrator
    orchestrator.set_campaign_broadcaster(campaign_broadcaster)

    yield

    # Shutdown - cleanup WebSocket connections
    # Any cleanup if needed

app = FastAPI(lifespan=lifespan)
```

#### Frontend Implementation

**PlayerPage WebSocket Integration (`frontend/src/components/player/PlayerPage.jsx`)**

```javascript
const PlayerPage = () => {
  const [currentCampaignId, setCurrentCampaignId] = useState(null);
  const [latestStructuredData, setLatestStructuredData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const { getAccessTokenSilently } = useAuth0();

  // WebSocket connection management
  const connectWebSocket = useCallback(async () => {
    try {
      // Get auth token if available
      let token = null;
      if (getAccessTokenSilently) {
        try {
          token = await getAccessTokenSilently();
        } catch (e) {
          console.log('No auth token available, connecting without auth');
        }
      }

      const wsUrl = token
        ? `${WS_BASE_URL}/ws/campaign/player?token=${token}`
        : `${WS_BASE_URL}/ws/campaign/player`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('🎮 Player WebSocket connected');
        setIsConnected(true);
        setError(null);

        // Clear any pending reconnection
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const update = JSON.parse(event.data);
          handleCampaignUpdate(update);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = (event) => {
        console.log('🎮 Player WebSocket disconnected:', event.code);
        setIsConnected(false);

        // Attempt reconnection after delay
        if (!reconnectTimeoutRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('🎮 Attempting WebSocket reconnection...');
            connectWebSocket();
          }, 5000);
        }
      };

      ws.onerror = (error) => {
        console.error('🎮 WebSocket error:', error);
        setError('Connection error - attempting to reconnect...');
      };

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setError(`Failed to connect: ${error.message}`);
    }
  }, [getAccessTokenSilently]);

  // Handle campaign updates from WebSocket
  const handleCampaignUpdate = (update) => {
    console.log('🎮 Received campaign update:', update.type);

    switch (update.type) {
      case 'campaign_active':
      case 'campaign_loaded':
        if (update.campaign_id !== currentCampaignId) {
          console.log('🎮 Campaign changed to:', update.campaign_id);
          setCurrentCampaignId(update.campaign_id);
        }

        if (update.structured_data) {
          const transformedData = transformStructuredData(update.structured_data);
          setLatestStructuredData(transformedData);
        }
        break;

      case 'campaign_updated':
        if (update.structured_data && update.campaign_id === currentCampaignId) {
          const transformedData = transformStructuredData(update.structured_data);
          setLatestStructuredData(transformedData);
        }
        break;

      case 'campaign_deactivated':
        console.log('🎮 Campaign deactivated');
        setCurrentCampaignId(null);
        setLatestStructuredData(null);
        break;

      default:
        console.log('🎮 Unknown update type:', update.type);
    }
  };

  // Transform structured data for PlayerView components
  const transformStructuredData = (structData) => {
    return {
      narrative: structData.narrative || '',
      all_narratives: structData.all_narratives || null,
      turn: structData.turn || '',
      status: structData.status || '',
      characters: structData.characters || '',
      turn_info: structData.turn_info || null,
      environmental_conditions: structData.environmental_conditions || '',
      immediate_threats: structData.immediate_threats || '',
      story_progression: structData.story_progression || ''
    };
  };

  // Initialize WebSocket connection
  useEffect(() => {
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []); // Remove auth dependency to prevent reconnection loops

  // Connection status indicator
  const ConnectionStatus = () => (
    <div className={`fixed top-4 right-4 px-3 py-1 rounded-full text-sm flex items-center gap-2 ${
      isConnected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
    }`}>
      <div className={`w-2 h-2 rounded-full ${
        isConnected ? 'bg-green-400' : 'bg-red-400'
      }`} />
      {isConnected ? 'Live' : 'Reconnecting...'}
    </div>
  );

  return (
    <div className="min-h-screen bg-gaia-dark text-white">
      <ConnectionStatus />

      {error && (
        <div className="bg-red-900 border border-red-700 text-red-300 p-4 m-4 rounded">
          {error}
        </div>
      )}

      {!currentCampaignId && (
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center bg-gaia-light rounded-lg p-8 max-w-md">
            <h2 className="text-xl font-bold text-white mb-4">No Active Campaign</h2>
            <p className="text-gaia-muted mb-6">
              Waiting for DM to load a campaign. You'll be automatically connected when a campaign starts.
            </p>
            {!isConnected && (
              <p className="text-yellow-400 text-sm">
                Connection status: Reconnecting...
              </p>
            )}
          </div>
        </div>
      )}

      {currentCampaignId && (
        <div className="p-4">
          <PlayerView
            campaignId={currentCampaignId}
            latestStructuredData={latestStructuredData}
            isConnected={isConnected}
          />
        </div>
      )}
    </div>
  );
};
```

### Event Types Specification

**WebSocket Message Types:**

1. **`campaign_active`**: Sent when player connects and campaign is already loaded
2. **`campaign_loaded`**: Broadcast when DM loads/activates a new campaign
3. **`campaign_updated`**: Broadcast when campaign state changes (chat responses)
4. **`campaign_deactivated`**: Broadcast when DM closes/switches campaigns
5. **`player_joined`**: Optional - notify when new player connects
6. **`heartbeat`**: Keep-alive messages

**Message Format:**
```json
{
  "type": "campaign_updated",
  "timestamp": "2025-01-15T10:30:00Z",
  "campaign_id": "campaign_123",
  "structured_data": {
    "narrative": "...",
    "turn": "...",
    "status": "...",
    "characters": "..."
  }
}
```

### Advantages Over Polling

1. **Real-time Updates**: Instant notification when DM makes changes
2. **Zero Server Overhead**: No constant HTTP requests
3. **Bidirectional**: Players could send status back to DM
4. **Event-Driven**: Only updates when actual changes occur
5. **Scalable**: Efficient for multiple players
6. **No Side Effects**: Pure push-based, no interference with DM operations
7. **Connection Aware**: Know when players are connected/disconnected

### Implementation Phases

#### Phase 1: Core WebSocket Infrastructure
- [ ] Add WebSocket dependencies to backend
- [ ] Implement CampaignBroadcaster class
- [ ] Create WebSocket endpoints
- [ ] Basic connection management

#### Phase 2: Orchestrator Integration
- [ ] Inject broadcaster into orchestrator
- [ ] Hook campaign activation events
- [ ] Hook chat response events
- [ ] Handle campaign deactivation

#### Phase 3: Frontend Integration
- [ ] Replace PlayerPage refresh with WebSocket
- [ ] Add connection state management
- [ ] Implement automatic reconnection
- [ ] Add connection status indicator

#### Phase 4: Enhanced Features
- [ ] Player presence indicators
- [ ] Bidirectional communication (player status to DM)
- [ ] Connection health monitoring
- [ ] Rate limiting and security

### Security Considerations

1. **Authentication**: Integrate with existing Auth0 system
2. **Authorization**: Verify players can access campaign data
3. **Rate Limiting**: Prevent WebSocket abuse
4. **Connection Limits**: Max connections per campaign
5. **Message Validation**: Validate all incoming WebSocket messages

### Error Handling & Resilience

1. **Automatic Reconnection**: Frontend handles disconnections gracefully
2. **Fallback Mechanism**: Option to fall back to polling if WebSocket fails
3. **Connection Health**: Heartbeat messages to detect dead connections
4. **Graceful Degradation**: System works even if WebSocket unavailable

### Testing Strategy

1. **Unit Tests**: Test CampaignBroadcaster class methods
2. **Integration Tests**: Test WebSocket endpoints
3. **Load Tests**: Multiple concurrent player connections
4. **Disconnect Tests**: Handle network failures gracefully
5. **Campaign Switching**: Test campaign change scenarios

### Monitoring & Observability

1. **Connection Metrics**: Track active WebSocket connections
2. **Message Metrics**: Monitor broadcast frequency and size
3. **Error Tracking**: Log WebSocket connection failures
4. **Performance**: Monitor message delivery latency

This specification provides a comprehensive WebSocket-based solution that eliminates polling inefficiencies while providing true real-time synchronization between DM and Player views.