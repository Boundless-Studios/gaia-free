# Audio Debug Page

A development-only page for testing the audio playback system without requiring TTS generation.

## Access

**Local development only**: http://localhost:5173/debug/audio

**Production**: Not accessible (route only available in dev mode)

## Features

### 1. Queue Audio Items
- **Session ID**: Set the campaign/session ID for testing
- **Number of Items**: Queue 1-10 audio items at once
- **Uses Sample MP3s**: Uses existing audio files from `backend/audio_samples/`

### 2. Playback Status
Real-time display of:
- Current session ID
- Streaming status (playing/idle)
- Mute status
- Pending chunk count
- User gesture button (if autoplay blocked)

### 3. WebSocket Messages
- Live monitoring of WebSocket messages
- Captures `[AUDIO_DEBUG]` logs
- Shows `audio_stream_started` / `audio_stream_stopped` events
- Clear button to reset message history

## Usage

### Basic Test Flow

1. **Navigate to debug page**
   ```
   http://localhost:5173/debug/audio
   ```

2. **Queue audio items**
   - Set session ID (default: `debug-session`)
   - Choose number of items (1-10)
   - Click "Queue N Audio Items"

3. **Monitor playback**
   - Watch WebSocket messages section for `audio_stream_started`
   - Check playback status for streaming state
   - Audio should play automatically (if not blocked by browser)

4. **Handle autoplay blocking**
   - If browser blocks autoplay, click "Resume Playback" button
   - This provides the required user gesture

### Backend Endpoint

The debug page calls:
```
POST /api/debug/queue-audio-test
{
  "session_id": "debug-session",
  "num_items": 3,
  "use_sample_mp3s": true
}
```

**No authentication required** - this is a debug-only endpoint.

## Sample MP3 Files

Located in `backend/audio_samples/`:
- `warrior-caleb-confident.mp3`
- `mysterious-almee-whisper.mp3`
- `dm-narrator-nathaniel-calm.mp3`
- `wise-sage-moderate.mp3`
- `adventurer-jen-soft.mp3`
- `noble-cornelius-distinguished.mp3`
- `merchant-alice-clear.mp3`
- `innkeeper-priyanka-warm.mp3`

The endpoint cycles through these files when queueing multiple items.

## Testing with Playwright

Run the automated test suite:

```bash
# From frontend directory
npx playwright test audio-debug.spec.js --headed

# Run with UI
npx playwright test audio-debug.spec.js --ui

# Run specific test
npx playwright test audio-debug.spec.js -g "should queue audio items"
```

## Troubleshooting

### No Audio Playing
1. **Check browser console** for WebSocket messages
2. **Look for autoplay blocking** - click Resume button if shown
3. **Verify backend is running** - check http://localhost:8000/api/health
4. **Check WebSocket connection** - look for connection logs in Network tab

### WebSocket Not Connecting
1. **Verify DM WebSocket is connected** - check console for connection logs
2. **Check session ID matches** - ensure same ID for queue and WebSocket
3. **Restart frontend** - Sometimes WebSocket needs reconnection

### Backend Errors
1. **Check sample MP3s exist** - verify `backend/audio_samples/*.mp3` files
2. **Check backend logs** - look for `[DEBUG][audio]` messages
3. **Verify database is running** - audio chunks are stored in DB

## Development Notes

### File Structure
```
frontend/src/components/debug/
├── AudioDebugPage.jsx       # Main component
├── AudioDebugPage.css        # Styles
└── README.md                 # This file

frontend/e2e/
└── audio-debug.spec.js       # Playwright tests

backend/src/api/routes/
└── debug.py                  # Backend endpoint
```

### Environment Checks
The debug route is only available when:
- `isProduction === false` (localhost, 127.0.0.1, or 192.168.x.x)
- OR `import.meta.env.VITE_REQUIRE_AUTH !== 'true'`
- OR Auth0 is not configured

This ensures the debug page is never exposed in production.

### WebSocket Message Interception
The debug page intercepts `console.log` calls to capture WebSocket messages:
- Only captures audio-related messages
- Keeps last 50 messages
- Displays with timestamps
- Monospace font for readability

## Common Use Cases

### Testing Queue System
Queue multiple items to test:
- Sequential playback
- Auto-advance to next item
- Chunk acknowledgment
- Request completion

### Testing Frontend Playback
Use existing MP3s to test:
- Audio element behavior
- Stream URL authentication
- Progressive delivery
- Late-join support

### Testing WebSocket Broadcasting
Monitor messages to verify:
- `audio_stream_started` is received
- Chunk IDs are included
- Stream URL is correct
- Timing of broadcasts

### Debugging Audio Issues
When audio doesn't play:
1. Queue items from debug page
2. Watch WebSocket messages
3. Check playback status
4. Compare expected vs actual behavior
5. Share console logs with team
