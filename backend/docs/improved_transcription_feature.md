# Improved Audio Transcription Feature

## Overview
The audio transcription feature has been significantly improved with better user experience, voice-based chunking, and enhanced controls.

## Key Improvements

### 1. Enhanced Pause Button
- **Feature**: Added intelligent pause/resume button to the transcription UI
- **Behavior**: 
  - When paused: Any audio with voice activity collected before pause is immediately transcribed
  - Microphone stays active when paused but new audio is not processed
  - Voice level indicator turns orange when paused
  - Button shows "⏸️ Pause" when active, "▶️ Resume" when paused
  - When resumed: Starts fresh recording without old audio

### 2. Cursor Position Preservation
- **Problem**: Previously, cursor would jump to end when new text was added
- **Solution**: Cursor position is saved and restored after text updates
- **Benefit**: Users can edit transcribed text while transcription continues

### 3. Voice-Based Chunking
- **Previous**: Fixed 5-second segments regardless of speech patterns
- **New**: Dynamic segments based on voice activity:
  - Segments end after 1.5 seconds of silence
  - Maximum segment duration: 30 seconds
  - Pre-voice buffer captures 1.5 seconds before voice detection
- **Benefits**:
  - Natural sentence and paragraph breaks
  - Better transcription accuracy
  - More efficient processing

### 4. Keyboard Shortcut (Ctrl+/)
- **Feature**: Global keyboard shortcut to start/stop transcription
- **Implementation**: Added to existing keyboard shortcuts system
- **Usage**: Press Ctrl+/ from anywhere in the app

### 5. Always Visible Transcription Panel
- **Change**: Transcription panel is now visible by default
- **Previous**: Required clicking "Show Transcription" button
- **Benefit**: Immediate access to transcription features

### 6. Dynamic Page Title
- **Feature**: Page title shows current campaign name
- **Format**: "{Campaign Name} - Gaia D&D"
- **Default**: "Gaia D&D Campaign Manager" when no campaign is active

### 7. Voice Detection Indicator
- **Feature**: Visual feedback when voice is detected
- **Appearance**: Green badge with "Voice Detected" text
- **Animation**: Pulsing wave effect shows active voice detection
- **Location**: Top-right corner of transcription area
- **Behavior**: Only shows when recording, voice detected, and not paused

## Technical Implementation

### Frontend Changes

#### ContinuousTranscription.jsx
- Converted to `forwardRef` component for imperative handle
- Added `isPaused` state and `isPausedRef` for pause functionality
- Implemented `cursorPositionRef` to track and restore cursor position
- Rewrote `startRecordingSegments` for voice-based chunking:
  - Continuous recording with 100ms chunks
  - Voice activity detection every 100ms
  - Segment boundaries based on silence duration
  - Immediate transcription on pause if voice detected
- Added `toggleRecording` method exposed via ref
- Added voice detection indicator with CSS animations

#### App.jsx
- Changed `showAudioRecorder` default to `true`
- Added effect to update `document.title` with campaign name
- Created `transcriptionRef` and passed to keyboard shortcuts

#### useKeyboardShortcuts.js
- Added Ctrl+/ handler
- Accepts `transcriptionRef` parameter
- Calls `toggleRecording()` on the transcription component

### Voice Detection Algorithm
```javascript
// Constants for voice detection
const SILENCE_THRESHOLD_MS = 1500;     // 1.5 seconds of silence
const CHUNK_INTERVAL_MS = 100;         // Check every 100ms
const MAX_SEGMENT_DURATION_MS = 30000; // Max 30 seconds per segment
const VOICE_THRESHOLD = 8;             // Volume threshold (0-100)
const VOICE_FREQ_LOW = 85;            // Hz - Lower bound
const VOICE_FREQ_HIGH = 3000;         // Hz - Upper bound
```

## Usage Guide

### Starting Transcription
1. **UI Button**: Click "🎤 Start Listening"
2. **Keyboard**: Press Ctrl+/
3. Grant microphone permissions when prompted

### During Transcription
- **Pause**: Click "⏸️ Pause" to temporarily stop transcription
- **Resume**: Click "▶️ Resume" to continue
- **Edit**: Click anywhere in text to edit while recording continues
- **Voice Indicator**: Shows real-time voice detection status

### Ending Transcription
1. **UI Button**: Click "⏹️ Stop Listening"
2. **Keyboard**: Press Ctrl+/
3. Audio stream and processing stop completely

## Best Practices

1. **Natural Speech**: Speak naturally with normal pauses
2. **Sentence Breaks**: Pause briefly (1.5s) between sentences for paragraph breaks
3. **Editing**: Feel free to edit text while recording - cursor position is preserved
4. **Pausing**: Use pause when:
   - System audio/TTS is playing
   - Background noise is high
   - You need to think without transcribing

## Testing

Run the test script to verify functionality:
```bash
python3 scripts/claude_helpers/test_improved_transcription.py
```

The script tests:
- WebSocket connection and continuous transcription
- Voice activity patterns
- Provides manual test instructions for UI features