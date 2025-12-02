# Audio WebSocket Protocol

## Events (Backend → Client)

### `audio_stream_started`

Sent when a new audio request begins streaming.

```json
{
  "type": "audio_stream_started",
  "campaign_id": "campaign_123",
  "stream_url": "/api/audio/stream/campaign_123?request_id=...",
  "started_at": "2025-11-09T12:00:00Z",
  "position_sec": 0.0,
  "is_late_join": false,
  "chunk_ids": ["uuid1", "uuid2"],
  "request_id": "uuid",
  "text": "Narrative text preview..."
}
```

**Frontend Action**: Start audio playback via AudioStreamContext

### `audio_stream_stopped`

Sent when audio stream is manually stopped (rare).

```json
{
  "type": "audio_stream_stopped",
  "campaign_id": "campaign_123"
}
```

**Frontend Action**: Stop playback, clear state

### `audio_chunk_ready`

Sent when individual chunk is generated (informational).

```json
{
  "type": "audio_chunk_ready",
  "campaign_id": "campaign_123",
  "chunk": {
    "id": "uuid",
    "url": "/api/media/audio/...",
    "mime_type": "audio/mpeg",
    "size_bytes": 12345,
    "duration_sec": 3.5,
    "chunk_number": 2,
    "total_chunks": 5
  },
  "sequence_number": 2,
  "playback_group": "narrative",
  "request_id": "uuid"
}
```

**Frontend Action**: Optional progress display (not used for playback)

### `playback_queue_updated`

Sent when queue state changes.

```json
{
  "type": "playback_queue_updated",
  "campaign_id": "campaign_123",
  "pending_count": 3,
  "current_request": {
    "request_id": "uuid",
    "chunk_count": 5,
    "played_count": 2,
    "status": "generating"
  },
  "pending_requests": [
    {"request_id": "uuid2", "chunk_count": 3, "status": "pending"}
  ]
}
```

**Frontend Action**: Update queue UI (optional)

## Messages (Client → Backend)

### `audio_played`

Client acknowledges chunk completion.

```json
{
  "type": "audio_played",
  "campaign_id": "campaign_123",
  "chunk_ids": ["uuid1", "uuid2"],
  "connection_token": "optional-reconnect-token"
}
```

**Backend Action**: Mark chunks PLAYED, check for auto-advance

### `heartbeat`

Keep-alive ping (handled by connection registry).

```json
{
  "type": "heartbeat"
}
```

**Backend Action**: Update connection timestamp

## Connection Flow

```
1. Client connects → /ws/campaign/player or /ws/campaign/dm
2. Backend sends connection_token
3. Backend sends audio_stream_started (if audio ready)
4. Client starts playback
5. Client sends audio_played when chunks complete
6. Backend auto-advances to next request
7. Backend sends audio_stream_started for next audio
8. Repeat steps 4-7
```

## Reconnection

Client reconnects with `connection_token`:
- Backend sends current stream position
- Client joins at `position_sec` (late-join)
- Playback continues seamlessly

## References

- Broadcaster: [campaign_broadcaster.py](../backend/src/api/websocket/campaign_broadcaster.py)
- Audio Handler: [audio_websocket_handler.py](../backend/src/api/websocket/audio_websocket_handler.py)
- Frontend Context: [audioStreamContext.jsx](../frontend/src/context/audioStreamContext.jsx)
- App Handlers: [App.jsx](../frontend/src/App.jsx#L700-L760)
