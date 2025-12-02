# Audio Playback Guide

## Overview

Gaia supports flexible audio playback with automatic environment detection and the ability to switch between Unix and Windows audio output methods. This is particularly useful for:
- Native Unix/Linux audio playback
- Windows/WSL audio with invisible playback for Discord screen sharing
- MP3 and WAV format support

## Configuration

The audio output method is controlled by the `AUTO_TTS_OUTPUT` environment variable:

```bash
# Auto-detect environment (default)
export AUTO_TTS_OUTPUT=auto

# Force Unix audio players (paplay, aplay, ffplay, etc.)
export AUTO_TTS_OUTPUT=unix

# Force Windows invisible audio (for screen sharing)
export AUTO_TTS_OUTPUT=windows
```

## Audio Methods

### Auto (Default)
- Automatically detects if running in Windows, WSL, or native Unix
- Uses appropriate method for the detected environment
- WSL → Windows invisible playback
- Native Linux/macOS → Unix audio players

### Unix
- Uses native Unix audio players in order of preference:
  - paplay (PulseAudio)
  - aplay (ALSA)
  - ffplay, mpv, mplayer, play, afplay, cvlc
- Best for native Linux/macOS environments

### Windows
- Invisible playback perfect for Discord screen sharing
- WAV files: PowerShell with System.Media.SoundPlayer
- MP3 files: VBScript with Windows Media Player ActiveX
- No windows appear during playback
- Audio is capturable by screen recording/sharing tools

## File Format Support

### WAV Files
- **Unix**: All audio players support WAV
- **Windows**: System.Media.SoundPlayer (invisible)

### MP3 Files
- **Unix**: Supported by ffplay, mpv, mplayer, vlc
- **Windows**: Windows Media Player ActiveX via VBScript (invisible)

## Testing Audio Playback

```bash
# Test all output methods
python3 test_audio_output_methods.py

# Test with specific method
AUTO_TTS_OUTPUT=unix python3 test_audio_output_methods.py
AUTO_TTS_OUTPUT=windows python3 test_audio_output_methods.py

# Test MP3 playback
python3 generate_test_mp3.py  # Generate test MP3
python3 test_mp3_playback.py  # Test playback
```

## Troubleshooting

### No Audio on Unix
- Install audio players: `sudo apt install pulseaudio-utils alsa-utils ffmpeg mpv`
- Check audio permissions and PulseAudio status

### No Audio on Windows/WSL
- Ensure Windows audio service is running
- Check Windows volume and mute status
- Verify WSL has Windows interop enabled
- Run `python3 diagnose_audio.py` for detailed diagnostics

### MP3 Not Playing
- **Unix**: Install ffmpeg or mpv
- **Windows**: Windows Media Player components should be pre-installed

## Integration with Auto-TTS

The Auto-TTS system is always on unless you explicitly disable it with `GAIA_AUDIO_DISABLED`. You can still override the output routing when necessary:

```bash
# Force Windows output for screen sharing
export AUTO_TTS_OUTPUT=windows

# Use Unix output for local listening
export AUTO_TTS_OUTPUT=unix
```

## Developer Notes

### Adding New Audio Players

To add support for new audio players:

1. **Unix**: Add to the `audio_players` list in `play_audio_unix()`
2. **Windows**: Modify `play_through_windows()` in `windows_audio_utils.py`

### Audio Queue System

The audio queue manager (`audio_queue_manager.py`) automatically uses the configured output method when playing queued audio files.

### File Paths

- Windows paths are automatically converted from WSL paths
- Audio files are temporarily copied to `C:\Windows\Temp\gaia_audio\` for Windows playback
- Old files are automatically cleaned up after 30 minutes
