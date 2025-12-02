# Audio Playback State Machine

## Request States

```
PENDING    → Queued, waiting for generation
GENERATING → Chunks being created in real-time
COMPLETED  → All chunks available
FAILED     → Error or timeout
```

### State Transitions

```
PENDING ──create_request()──► GENERATING ──all_chunks_ready()──► COMPLETED
   │                               │
   └──timeout(5min)───► FAILED ◄───┘ timeout(3min) or error
```

| From | To | Trigger | Method |
|------|-------|---------|---------|
| PENDING | GENERATING | First chunk starts | `mark_request_started()` |
| PENDING | FAILED | 5min timeout | Auto-cleanup |
| GENERATING | COMPLETED | All chunks validated | `mark_request_completed()` |
| GENERATING | FAILED | 3min timeout or error | Auto-cleanup |

## Chunk States

```
PENDING ──streamed──► PLAYING ──acknowledged──► PLAYED
```

| From | To | Trigger | Method |
|------|-------|---------|---------|
| PENDING | PLAYING | Sent to client | Implicit |
| PLAYING | PLAYED | Client ACK | `mark_chunk_played()` |

## Auto-Advance

When all chunks in a request are PLAYED:
1. Mark request COMPLETED
2. Fetch next PENDING request
3. Mark as GENERATING
4. Broadcast `audio_stream_started` to clients

## Cleanup

- **Timeout**: PENDING (5min), GENERATING (3min) → FAILED
- **Scheduled**: PLAYED chunks older than 7 days → Deleted
- **Frequency**: Every 60 seconds

## References

- Models: [audio_models.py](../backend/src/core/audio/audio_models.py)
- Service: [audio_playback_service.py](../backend/src/core/audio/audio_playback_service.py)
- Broadcaster: [campaign_broadcaster.py](../backend/src/api/websocket/campaign_broadcaster.py)
- Cleanup: [audio_cleanup.py](../backend/src/api/websocket/cleanup/audio_cleanup.py)
