# Audio Playback Fix - Synchronized Streaming

## Problem Summary

Audio chunks were being generated on the backend but not playing on the frontend. The issue was that the `StreamingAudioBuffer` class (used by the DM for real-time audio generation) was generating chunks but never triggering the synchronized audio stream.

## Root Cause

There were **two different audio generation systems** in the codebase:

1. **`generate_audio_progressive()`** - Newer approach that generates audio after text completes
   - ✅ Already had synchronized streaming trigger
   - ❌ Not being used by the DM streaming path

2. **`StreamingAudioBuffer`** - Older approach that generates audio in real-time during text streaming
   - ✅ Being actively used by DM
   - ❌ **Missing synchronized streaming trigger** ← ROOT CAUSE

## Files Changed

### [backend/src/core/audio/streaming_audio_buffer.py](../backend/src/core/audio/streaming_audio_buffer.py)

**Line 53**: Added tracking flag
```python
self.stream_triggered = False  # Track if synchronized stream has been started
```

**Lines 212-229**: Added synchronized stream trigger
```python
# Trigger synchronized streaming on first successful chunk
if not self.stream_triggered:
    self.stream_triggered = True
    try:
        from src.config.api import API_CONFIG
        stream_url = f"{API_CONFIG.BASE_URL}/api/audio/stream/{self.session_id}"
        await self.broadcaster.start_synchronized_stream(self.session_id, stream_url)
        logger.info(
            "[StreamAudio] Session %s: Started synchronized audio stream: %s",
            self.session_id,
            stream_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[StreamAudio] Session %s: Failed to start synchronized audio stream: %s",
            self.session_id,
            exc,
        )
```

## How It Works Now

### Backend Flow
1. DM generates narrative text (streaming)
2. `StreamingAudioBuffer` detects sentence boundaries
3. Generates audio chunk for each sentence
4. **On first chunk**:
   - Broadcasts `audio_chunk_ready` WebSocket message
   - Calls `broadcaster.start_synchronized_stream()` ← **NEW**
   - Sends `audio_stream_started` WebSocket message ← **NEW**
5. Subsequent chunks are broadcast as they're generated

### Frontend Flow
1. Receives `audio_stream_started` WebSocket message
2. `AudioStreamProvider` context starts the audio stream
3. Creates `<audio>` element with source: `/api/audio/stream/{campaign_id}`
4. Progressive stream endpoint yields chunks as they become available
5. Audio plays automatically (or after user gesture if required by browser)

## Manual Testing

### Prerequisites
- Backend and frontend containers running
- A campaign loaded in the DM view

### Test Steps

1. **Monitor backend logs**:
   ```bash
   ./scripts/test_audio_playback.sh campaign_157
   ```
   Or manually:
   ```bash
   docker logs -f gaia-backend-dev | grep -E "(StreamAudio|audio_stream)"
   ```

2. **Send a message in the DM view**

3. **Verify in backend logs**:
   ```
   ✅ [StreamAudio] Session campaign_XXX: Generating audio chunk 0
   ✅ [StreamAudio] Session campaign_XXX: Broadcast audio chunk 0
   ✅ [StreamAudio] Session campaign_XXX: Started synchronized audio stream
   ```

4. **Verify in frontend**:
   - Open browser console (F12)
   - Look for: `🎵 [AUDIO STREAM] Received audio_stream_started`
   - Look for: `[AUDIO_STREAM] Starting stream`
   - Audio should play automatically (or show "Click to enable audio" if browser requires gesture)

### Expected Backend Logs
```
2025-11-08 XX:XX:XX,XXX - src.core.audio.streaming_audio_buffer - INFO - [StreamAudio] Session campaign_157: Generating audio chunk 0 (260 chars)
2025-11-08 XX:XX:XX,XXX - src.core.audio.streaming_audio_buffer - INFO - [StreamAudio] Session campaign_157: Broadcast audio chunk 0 (url=/api/audio/...)
2025-11-08 XX:XX:XX,XXX - src.core.audio.streaming_audio_buffer - INFO - [StreamAudio] Session campaign_157: Started synchronized audio stream: http://localhost:8000/api/audio/stream/campaign_157
2025-11-08 XX:XX:XX,XXX - src.core.audio.streaming_audio_buffer - INFO - [StreamAudio] Session campaign_157: Generating audio chunk 1 (267 chars)
```

### Expected Frontend Console Logs
```
🎵 [AUDIO STREAM] Received audio_stream_started: {campaign_id: "campaign_157", stream_url: "..."}
[AUDIO_STREAM] Starting stream: {sessionId: "campaign_157", position_sec: 0, isLateJoin: false}
[AUDIO_STREAM] Stream started successfully
```

## All Audio Paths Fixed

All three audio generation paths now trigger synchronized streaming:

1. ✅ **DM Streaming** ([streaming_dm_runner.py](../backend/src/core/session/streaming_dm_runner.py:446-513))
   - Uses `StreamingAudioBuffer` ← **FIXED**
   - Triggers stream on first chunk

2. ✅ **Scene Agent Streaming** ([scene_agent_runner.py](../backend/src/game/scene_agents/scene_agent_runner.py:294-342))
   - Uses `generate_audio_progressive()`
   - Triggers stream on first chunk

3. ✅ **Scene Agent Synchronous** ([campaign_runner.py](../backend/src/core/session/campaign_runner.py:805-844))
   - Uses `generate_audio_progressive()`
   - Triggers stream on first chunk

## Troubleshooting

### Audio Not Playing

1. **Check browser autoplay policy**:
   - Look for `[AUDIO_STREAM] Autoplay blocked - user gesture required`
   - Click anywhere on the page to enable audio

2. **Check WebSocket connection**:
   - Backend logs should show: `DM connected (session=campaign_XXX)`
   - Frontend console should show: `🎭 DM WebSocket connected`

3. **Check audio chunks are generated**:
   - Backend logs should show: `[StreamAudio] Session XXX: Generating audio chunk N`
   - If not, check TTS service configuration

4. **Check synchronized stream trigger**:
   - Backend logs should show: `[StreamAudio] Session XXX: Started synchronized audio stream`
   - If missing, the fix wasn't applied or backend needs restart

### Still Having Issues?

1. Restart backend: `docker restart gaia-backend-dev`
2. Clear browser cache and reload
3. Check browser console for errors
4. Verify audio element exists: `document.querySelectorAll('audio')`
5. Check audio element source: Look for `/api/audio/stream/{campaign_id}`

## Related Files

- [frontend/src/context/audioStreamContext.jsx](../frontend/src/context/audioStreamContext.jsx) - Synchronized audio context
- [frontend/src/hooks/useDMWebSocket.js](../frontend/src/hooks/useDMWebSocket.js) - WebSocket message handling
- [frontend/src/App.jsx](../frontend/src/App.jsx:446-488) - Audio stream event handlers
- [backend/src/api/routes/chat.py](../backend/src/api/routes/chat.py:915-982) - Progressive stream endpoint
- [backend/src/api/websocket/campaign_broadcaster.py](../backend/src/api/websocket/campaign_broadcaster.py) - WebSocket broadcaster

## Next Steps

- [x] Fix `StreamingAudioBuffer` to trigger synchronized streaming
- [ ] Manual testing to verify audio playback works
- [ ] Test in both DM and Player views
- [ ] Test late-join synchronization
- [ ] Commit changes if working
