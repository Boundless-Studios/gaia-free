# F5-TTS Integration

This document describes the integration of F5-TTS (Few-Shot Fast Speech Synthesis) into the Gaia D&D Campaign Manager.

## Overview

F5-TTS is a high-quality text-to-speech system that can clone voices from just a few seconds of reference audio. The integration provides local TTS capabilities without requiring external API keys.

## Features

- **Local TTS Server**: Automatically launches a Gradio server on port 7860
- **Voice Cloning**: Uses reference audio files to clone specific voices
- **Fallback Logic**: Handles cases where the server is already running
- **Connection Validation**: Verifies server connectivity and displays status
- **Automatic Cleanup**: Properly shuts down the TTS server when Gaia exits

## Installation

F5-TTS is automatically installed when you run `python gaia_launcher.py` for the first time. The dependency is included in `requirements.txt`:

```
f5-tts>=0.1.0
```

## Configuration

The TTS server configuration is defined in `speakers_config.toml`:

```toml
[settings]
gradio_url = "http://localhost:7860"  # Local Gradio server URL and port
```

## Voice Configuration

Voices are configured in `speakers_config.toml` with reference audio files:

```toml
[speakers.dm]
name = "DM Narrator"
description = "Calm and authoritative dungeon master voice"
reference_audio = "audio_samples/dm-narrator-nathaniel-calm.mp3"
reference_text = "The town square seems to shift slightly as you speak your name, as if the very stones recognize the touch of magic."
style = "narrator"
gender = "male"
```

## Startup Process

When you run `python gaia_launcher.py`, the following happens:

1. **Dependency Check**: Verifies f5-tts is installed
2. **Server Detection**: Checks if TTS server is already running on port 7860
3. **Server Launch**: If not running, launches `f5-tts_infer-gradio --port 7860`
4. **Connection Validation**: Tests connectivity and displays status
5. **Status Reporting**: Shows ✅ for success or ❌ for failure

## Status Messages

The startup process displays clear status messages:

- `✅ TTS server already running on port 7860` - Server detected
- `✅ TTS server started successfully` - Server launched successfully
- `✅ Local TTS is ready` - Connection validated
- `❌ f5-tts_infer-gradio command not found` - Installation required
- `❌ Cannot connect to TTS server` - Connection failed

## Testing

You can test the f5-tts installation independently:

```bash
python test_f5_tts_installation.py
```

This script will:
- Verify the `f5-tts_infer-gradio` command is available
- Test server startup and connectivity
- Display detailed status messages

## Troubleshooting

### Server Already Running

If you see "TTS server already running", the system will:
1. Detect the existing server
2. Validate the connection
3. Continue without starting a new instance

### Installation Issues

If f5-tts is not installed:
1. Run `pip install f5-tts`
2. Restart Gaia with `python gaia_launcher.py`

### Port Conflicts

If port 7860 is in use:
1. The system will attempt to kill existing processes
2. If that fails, you may need to manually stop the conflicting service
3. Restart Gaia to try again

### Connection Failures

If the server starts but doesn't respond:
1. Check if the port is blocked by firewall
2. Verify no other service is using port 7860
3. Check system resources (CPU/memory)

## Integration with TTS Service

The TTS service automatically detects and uses the local F5-TTS server:

```python
from src.core.audio.tts_service import tts_service

# Check if local TTS is available
if tts_service.is_provider_available(VoiceProvider.LOCAL):
    # Use local TTS for synthesis
    audio_data = await tts_service.synthesize_speech(text, voice="dm")
```

## Server Management

The TTS server is managed by `TTSServerManager` in `src/core/audio/tts_server_manager.py`:

- **Automatic Startup**: Launched during Gaia startup
- **Process Management**: Proper cleanup on shutdown
- **Health Monitoring**: Connection validation
- **Error Handling**: Graceful fallbacks for failures

## Performance

- **Startup Time**: ~5-10 seconds for server initialization
- **Synthesis Speed**: Real-time voice cloning
- **Memory Usage**: Moderate (depends on model size)
- **CPU Usage**: Varies based on synthesis complexity

## Security

- **Local Only**: No external API calls required
- **No Data Transmission**: All processing happens locally
- **Port Binding**: Server only binds to localhost
- **Process Isolation**: Runs in separate process from main application 