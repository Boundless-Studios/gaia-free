# Connection Registry

## Overview

The Connection Registry separates three distinct lifecycles in the audio playback system:

1. **Generation lifecycle** - Backend creating audio chunks
2. **Connection lifecycle** - WebSocket connections (connect/disconnect/heartbeat)
3. **Playback lifecycle** - Per-connection tracking of what was sent/played

## Problem Solved

Previously, session-level state was conflated with connection-level state, causing:
- Multiple clients sharing playback state (race conditions)
- Reconnecting clients getting wrong resume positions
- No tracking of what each connection received

## Solution

Connection-scoped tracking where each WebSocket connection has independent playback state.

## Database Schema

### `websocket_connections`
Tracks WebSocket connection instances with lifecycle state, connection tokens for resume, and heartbeat monitoring.

### `connection_playback_states`
Tracks per-connection audio chunk delivery: `sent_to_client`, `acknowledged_by_client`, `played_by_client`.

## Implementation Status

✅ **Fully Integrated** - All WebSocket handlers (`/ws/campaign/player`, `/ws/campaign/dm`) use connection registry.

### Key Features
- **Connection tokens** sent to clients for reconnection resume
- **Heartbeat protocol** updates registry timestamps
- **Per-connection audio tracking** in `broadcast_campaign_update()`
- **Background cleanup** removes old connections (24h threshold, 1h interval)

### Integration Points

**WebSocket Handlers** (`backend/src/api/main.py`)
- `campaign_player_websocket()` - Creates connection on connect
- `campaign_dm_websocket()` - Creates connection on connect

**Broadcaster** (`backend/src/api/websocket/campaign_broadcaster.py`)
- `connect_player()` - Registers connection, sends token
- `connect_dm()` - Registers connection, sends token
- `disconnect_player()` / `disconnect_dm()` - Marks disconnected
- `broadcast_campaign_update()` - Tracks chunk delivery

**Heartbeat** (`backend/src/api/websocket/ws_helpers.py`)
- `handle_common_ws_message()` - Updates registry heartbeat

**Cleanup** (`backend/src/api/websocket/cleanup/`)
- `ConnectionCleanupTask` - Removes old connections every 1 hour
- `AudioCleanupTask` - Removes old audio chunks every 60 seconds

## Migration

Run migration 11 to create tables:
```bash
psql $DATABASE_URL -f db/migrations/11-create-connection-registry-tables.sql
```

## Testing

```bash
python3 gaia_launcher.py test backend/test/websocket/test_connection_registry.py
```

## Benefits

✅ Independent playback position per client
✅ Reliable reconnection with resume tokens
✅ Per-connection acknowledgment tracking
✅ Better debugging and monitoring
✅ Automatic cleanup of stale connections
