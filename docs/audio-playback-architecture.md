# Audio Playback Architecture

## Overview

Synchronized radio-style audio playback where all clients hear the same audio simultaneously. Backend controls playback progression; frontend receives and plays streams.

## Key Concepts

- **Playback Request**: Group of audio chunks from one generation session (one DM message)
- **Audio Chunk**: Individual audio file (sentence/paragraph)
- **Auto-Advance**: Backend automatically starts next request when current completes
- **Late-Join**: Clients joining mid-stream sync to current position

## Architecture Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│ DM sends    │         │   Backend    │         │  Players    │
│  message    │────────►│              │────────►│  receive    │
└─────────────┘         │              │         │  audio      │
                        │              │         └─────────────┘
                        │  1. Generate │
                        │     text     │         WebSocket:
                        │              │         - audio_stream_started
                        │  2. Create   │         - audio_chunk_ready
                        │     playback │         - playback_queue_updated
                        │     request  │
                        │              │         HTTP:
                        │  3. Generate │         - GET /audio/stream/{id}
                        │     chunks   │         - POST /audio/played/{id}
                        │     (TTS)    │         - GET /campaigns/{id}/audio/queue
                        │              │
                        │  4. Broadcast│
                        │     WS event │
                        │              │
                        │  5. Auto-    │
                        │     advance  │
                        └──────────────┘
```

## Data Flow

### 1. Audio Generation

```python
# DM sends message
DM Message → StreamingDMRunner
           ↓
     PlaybackRequestWriter.create()
           ↓
     audio_playback_service.create_playback_request()
           ↓
     DB: audio_playback_requests (status=PENDING)
           ↓
     TTS generates chunks
           ↓
     PlaybackRequestWriter.add_chunk()
           ↓
     DB: audio_chunks (sequence 0,1,2...)
           ↓
     mark_request_started() → status=GENERATING
           ↓
     Broadcast: audio_stream_started
```

### 2. Client Playback

```javascript
// Frontend receives WebSocket event
audio_stream_started → AudioStreamContext.startStream()
                     ↓
              <audio src="/api/audio/stream/{id}" />
                     ↓
              Progressive streaming (yields chunks as generated)
                     ↓
              Audio ends → dispatch AUDIO_STREAM_COMPLETED_EVENT
                     ↓
              App.jsx sends audio_played WS message
```

### 3. Auto-Advance

```python
# Backend receives audio_played
mark_audio_played(chunk_id)
    ↓
Check if all chunks PLAYED
    ↓
mark_request_completed()
    ↓
_auto_advance_playback()
    ↓
get_next_pending_request()
    ↓
mark_request_started()
    ↓
Broadcast: audio_stream_started (next request)
```

## Components

### Backend

| Component | Purpose | Location |
|-----------|---------|----------|
| `audio_playback_service` | Request/chunk CRUD, state machine | `core/audio/audio_playback_service.py` |
| `PlaybackRequestWriter` | Create requests, persist chunks | `core/audio/playback_request_writer.py` |
| `campaign_broadcaster` | WebSocket events, auto-advance | `api/websocket/campaign_broadcaster.py` |
| `AudioCleanupTask` | Purge old chunks | `api/websocket/cleanup/audio_cleanup.py` |

### Frontend

| Component | Purpose | Location |
|-----------|---------|----------|
| `AudioStreamContext` | Manage playback state | `context/audioStreamContext.jsx` |
| `App.jsx` | Handle WS events, send ACKs | `App.jsx` |
| `useDMWebSocket` | DM WebSocket connection | `hooks/useDMWebSocket.js` |

### Database

| Table | Purpose |
|-------|---------|
| `audio_playback_requests` | Request lifecycle tracking |
| `audio_chunks` | Individual chunk metadata |
| `websocket_connections` | Connection registry |
| `connection_playback_states` | Per-connection delivery tracking |

## API Endpoints

### HTTP

- `GET /api/campaigns/{id}/audio/queue` - Full queue status
- `GET /api/audio/stream/{id}` - Progressive audio stream
- `POST /api/audio/played/{chunk_id}` - Mark chunk played (fallback)

### WebSocket

- `audio_stream_started` - New audio ready
- `audio_chunk_ready` - Chunk generated (informational)
- `playback_queue_updated` - Queue state changed
- `audio_played` (client→server) - Chunk acknowledgment

## Failure Modes & Recovery

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| TTS fails | Request marked FAILED | Next request auto-advances |
| Client disconnects | Audio continues for others | Late-join on reconnect |
| Generation stalls | 3min timeout → FAILED | Auto-advance to next |
| DB unavailable | In-memory fallback | Graceful degradation |

## Monitoring

- **Metrics**: Request counts by status, chunk generation latency
- **Logs**: `[AUDIO_DEBUG]` for playback events, `[AUDIO_CLEANUP]` for maintenance
- **Cleanup**: 60s intervals, 7-day retention for PLAYED chunks

## References

- State Machine: [audio-playback-state-machine.md](audio-playback-state-machine.md)
- WebSocket Protocol: [audio-websocket-protocol.md](audio-websocket-protocol.md)
- Connection Registry: [connection-registry-integration.md](../backend/docs/connection-registry-integration.md)
- Original Fix: [audio-playback-fix.md](audio-playback-fix.md)
