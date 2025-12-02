# STT Multiplexed Connection Pool Architecture

## Status: Proposed

## Problem Statement

The current STT (Speech-to-Text) implementation maintains a 1:1 mapping between frontend clients and ElevenLabs Scribe V2 WebSocket connections:

```
Current: 100 users × 1 ElevenLabs connection each = 100 connections needed
Reality: At any moment, maybe 5 users are actually speaking
```

This approach:
- Wastes API connections on silent users
- Hits ElevenLabs rate limits with fewer total users
- Scales poorly (N users = N connections)

## Proposed Solution

Implement a **multiplexed connection pool** where the backend maintains a small number of persistent ElevenLabs connections and routes audio from multiple clients through them based on voice activity.

```
Proposed: 100 users → Backend Router → 5 persistent ElevenLabs connections
```

### Key Insight

Users spend most of their time:
- Listening to TTS playback
- Reading narrative text
- Thinking about their response
- Waiting for their turn

Only during active speech do they need an ElevenLabs connection. A single connection can time-multiplex between users during their silent periods.

## Architecture

### Components

```
┌─────────────┐     ┌─────────────────────────────────────────────┐
│ Frontend 1  │────▶│                                             │
├─────────────┤     │           Backend STT Router                │
│ Frontend 2  │────▶│                                             │
├─────────────┤     │  ┌─────────────────────────────────────┐   │
│ Frontend 3  │────▶│  │     Per-Client Audio Buffers        │   │
├─────────────┤     │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │   │
│     ...     │     │  │  │ C1  │ │ C2  │ │ C3  │ │ ... │   │   │
├─────────────┤     │  │  └─────┘ └─────┘ └─────┘ └─────┘   │   │
│ Frontend N  │────▶│  └─────────────────────────────────────┘   │
└─────────────┘     │                    │                        │
                    │                    ▼                        │
                    │  ┌─────────────────────────────────────┐   │
                    │  │      Voice Activity Detector        │   │
                    │  │   (Detects speech start/end)        │   │
                    │  └─────────────────────────────────────┘   │
                    │                    │                        │
                    │                    ▼                        │
                    │  ┌─────────────────────────────────────┐   │
                    │  │     Speech Session Manager          │   │
                    │  │  - Acquires connection on speech    │   │
                    │  │  - Routes audio to connection       │   │
                    │  │  - Routes results back to client    │   │
                    │  │  - Releases connection on silence   │   │
                    │  └─────────────────────────────────────┘   │
                    │                    │                        │
                    └────────────────────┼────────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────────┐
                    │     ElevenLabs Connection Pool (5)          │
                    │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
                    │  │ WS1 │ │ WS2 │ │ WS3 │ │ WS4 │ │ WS5 │   │
                    │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │
                    └─────────────────────────────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  ElevenLabs API     │
                              │  (Scribe V2)        │
                              └─────────────────────┘
```

### Component Details

#### 1. Per-Client Audio Buffer
- Circular buffer per connected frontend
- Stores incoming PCM audio chunks
- Size limit to prevent memory bloat (e.g., 30 seconds max)
- Discards old audio when limit reached

```python
class ClientAudioBuffer:
    def __init__(self, client_id: str, max_duration_seconds: float = 30.0):
        self.client_id = client_id
        self.buffer: deque = deque(maxlen=calculated_max_chunks)
        self.sample_rate = 16000

    def add_chunk(self, chunk: bytes):
        self.buffer.append(chunk)

    def get_all(self) -> bytes:
        return b''.join(self.buffer)

    def clear(self):
        self.buffer.clear()
```

#### 2. Voice Activity Detector (VAD)
- Runs on backend for each client's audio stream
- Reuses existing `voice_detection.py` service
- Detects speech onset and offset
- Triggers connection acquisition/release

```python
class BackendVAD:
    def process_chunk(self, client_id: str, chunk: bytes) -> VADEvent:
        # Returns: SPEECH_START, SPEECH_CONTINUE, SPEECH_END, SILENCE
        ...
```

#### 3. Speech Session Manager
- Coordinates between VAD events and connection pool
- Maintains mapping: client_id → active_connection
- Handles connection lifecycle per speech segment

```python
class SpeechSessionManager:
    async def on_speech_start(self, client_id: str):
        # Acquire connection from pool
        connection = await self.pool.acquire()
        self.active_sessions[client_id] = connection
        # Start streaming buffered audio

    async def on_speech_end(self, client_id: str):
        # Wait for final transcription
        # Release connection back to pool
        connection = self.active_sessions.pop(client_id)
        await self.pool.release(connection)
```

#### 4. ElevenLabs Connection Pool
- Maintains N persistent WebSocket connections
- Connections are long-lived, not per-speech-segment
- Handles connection health/reconnection

```python
class PersistentConnectionPool:
    def __init__(self, size: int = 5):
        self.connections: List[ElevenLabsConnection] = []
        self.available: asyncio.Queue = asyncio.Queue()

    async def initialize(self):
        # Create N persistent connections at startup
        for i in range(self.size):
            conn = await self._create_connection()
            self.connections.append(conn)
            await self.available.put(conn)

    async def acquire(self) -> ElevenLabsConnection:
        return await self.available.get()

    async def release(self, conn: ElevenLabsConnection):
        # Reset connection state for next user
        await conn.reset_session()
        await self.available.put(conn)
```

## Data Flow

### Speech Start Flow
```
1. Frontend sends audio chunk
2. Backend buffers chunk for client
3. VAD processes chunk, detects speech start
4. SpeechSessionManager acquires connection from pool
5. Buffered audio (with pre-roll) is sent to ElevenLabs
6. Subsequent chunks are streamed directly
```

### Speech End Flow
```
1. VAD detects silence threshold exceeded
2. Send end-of-speech signal to ElevenLabs
3. Wait for final committed transcript
4. Route transcript back to correct frontend client
5. Release connection back to pool
6. Clear client's audio buffer
```

### Transcription Routing
```
1. ElevenLabs sends partial/committed transcript
2. SpeechSessionManager looks up client_id for this connection
3. Routes transcript to correct frontend WebSocket
4. Frontend displays transcript
```

## Configuration

```python
@dataclass
class MultiplexedSTTConfig:
    # Connection pool
    pool_size: int = 5
    connection_timeout_seconds: float = 30.0

    # Audio buffering
    max_buffer_duration_seconds: float = 30.0
    pre_roll_duration_ms: float = 500.0  # Audio before speech start

    # VAD settings
    speech_start_threshold_db: float = -40.0
    speech_end_silence_ms: float = 1000.0

    # Session management
    max_speech_duration_seconds: float = 120.0  # Force commit after 2 min
    idle_connection_reset_seconds: float = 300.0  # Reset unused connections
```

## Considerations

### ElevenLabs Session Context
- Scribe V2 may build context over a session
- When switching users on a connection, we may lose context
- Mitigation: Reset session state between users
- Trade-off: Slightly lower accuracy for first few words

### Latency
- Small delay (~100-500ms) while acquiring connection
- Pre-roll buffering captures audio before VAD triggers
- Net effect: Similar perceived latency to 1:1 model

### Connection Health
- Persistent connections may disconnect
- Pool must detect and replace dead connections
- Health check with periodic pings

### Memory Management
- Per-client buffers consume memory
- Must limit buffer size and client count
- Consider Redis for buffer storage at scale

### Fairness
- If all connections busy, new speakers wait
- Priority queue by wait time ensures fairness
- Consider priority tiers (DM > Players)

## Migration Path

### Phase 1: Current Implementation (Done)
- 1:1 connection mapping
- Simple connection pool with queueing
- Max 20 concurrent connections

### Phase 2: Backend VAD Integration
- Add VAD processing on backend
- Continue 1:1 mapping but only connect on speech
- Disconnect after silence threshold

### Phase 3: Multiplexed Pool
- Implement persistent connection pool
- Per-client audio buffering
- Full multiplexing with routing

### Phase 4: Optimization
- Redis-backed buffers for scale
- Priority queuing
- Metrics and monitoring

## Files to Modify

### New Files
- `speech-to-text/src/services/persistent_pool.py` - Persistent connection pool
- `speech-to-text/src/services/audio_buffer.py` - Per-client audio buffering
- `speech-to-text/src/services/speech_session.py` - Session management
- `speech-to-text/src/services/backend_vad.py` - Backend VAD wrapper

### Modified Files
- `speech-to-text/src/websocket_handlers.py` - Use new multiplexed architecture
- `speech-to-text/src/main.py` - Initialize persistent pool on startup
- `speech-to-text/src/config.py` - Add multiplexed config options

## Success Metrics

- **Connection efficiency**: N users / M connections ratio
- **P50/P95 latency**: Time from speech start to first partial
- **Transcription accuracy**: Word error rate compared to 1:1 model
- **Memory usage**: Per-client buffer overhead
- **Connection stability**: Reconnection frequency

## Open Questions

1. Should we maintain separate pools for DM vs Players?
2. What's the optimal pool size for typical game sessions (4-6 players)?
3. Should we pre-warm connections or create on-demand?
4. How do we handle overlapping speech from multiple users?
