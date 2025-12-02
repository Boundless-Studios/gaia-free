# Audio Queuing and Keyboard Integration Updates

## Overview
Updated the TTS controls to support audio queuing and integrated keyboard shortcuts to use the button queue systems for consistent behavior.

## Audio Queuing Features

### TTS Controls Updates
- **Queue Support**: Can now queue multiple audio selections
- **Queue Display**: Shows number of items in queue (e.g., "Playing (3 queued)")
- **Stop Clears Queue**: Stop button now clears all queued audio, not just current playback
- **Click Animation**: Button animates when clicked for visual feedback

### Implementation Details
- Uses `useRef` for queue management (prevents React re-render issues)
- Sequential playback with polling for completion
- Maintains processing state to prevent concurrent processing
- Automatic progression through queue

## Keyboard Shortcuts Integration

### Ctrl+G (Image Generation)
- Now triggers the ImageGenerateButton's queue system
- Shows click animation on the button
- Updates button state (loading, queue count)
- Uses same queue system as clicking the button

### Ctrl+A (Audio Playback)
- Now triggers the TTSControls' queue system
- Shows click animation on the play button
- Updates button state (playing, queue count)
- Uses same queue system as clicking the button

## Technical Changes

### Component Updates
1. **TTSControls.jsx**
   - Made a forwardRef component
   - Added queue management with useRef
   - Added click animation state
   - Exposed `playSelectedText` method via imperative handle

2. **ControlPanel.jsx**
   - Added ref for TTSControls
   - Exposed `triggerAudioPlayback` method
   - Maintains refs for both image and audio controls

3. **GameDashboard.jsx**
   - Exposed `triggerAudioPlayback` method
   - Forwards calls to ControlPanel

4. **useKeyboardShortcuts.js**
   - Updated to use button queue systems
   - Removed direct API calls
   - Uses dashboard ref to trigger buttons

### CSS Updates
- Added `.clicked` animation class to TTSControls.css
- Reuses the buttonClick animation from ImageGenerateButton

## Benefits
- Consistent behavior between clicking buttons and using keyboard shortcuts
- Visual feedback for all actions
- Proper queue management for both image and audio generation
- Clear queue functionality for audio playback
- No more infinite loops or state management issues

## Usage
- Select text and press Ctrl+G to generate image (queues if already generating)
- Select text and press Ctrl+A to play audio (queues if already playing)
- Click Stop button to stop audio and clear all queued audio
- Visual feedback shows when buttons are triggered via keyboard