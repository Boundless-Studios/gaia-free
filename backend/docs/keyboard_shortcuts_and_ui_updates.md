# Keyboard Shortcuts and UI Updates

## Keyboard Shortcuts

### Ctrl+G - Generate Image
- Select any text in the narrative
- Press Ctrl+G to generate an image
- Image will popup for 5 seconds and be added to the gallery

### Ctrl+A - Play Audio
- Select any text in the narrative  
- Press Ctrl+A to play audio using TTS
- Uses the currently selected voice from TTS controls

## UI Updates

### Image Gallery
- Moved above the narrative section
- Shows 480x480 pixel thumbnails
- Displays up to 5 recent images
- Click any thumbnail to view full-size
- Latest image marked with "LATEST" badge

### Generate Image Button
- Now supports queuing multiple requests
- Can click while generating to queue more images
- Shows queue count when processing multiple requests
- No longer blocks UI while generating

### Layout Changes
- Control Panel at top
- Image Gallery below controls
- Narrative section below gallery
- Removed environment and player options panes
- Removed instruction text from control panel

### New Features
- Keyboard shortcuts help button (⌨️ Shortcuts)
- Shows available keyboard shortcuts in a modal
- Images automatically popup for 5 seconds when generated
- All images use full backend URLs for proper loading

## Technical Implementation

### Files Added
- `/src/frontend/hooks/useKeyboardShortcuts.js` - Keyboard shortcut handler
- `/src/frontend/components/KeyboardShortcutsHelp.jsx` - Help modal component
- `/src/frontend/components/KeyboardShortcutsHelp.css` - Help modal styles

### Files Modified
- `/src/frontend/app/App.jsx` - Added keyboard shortcuts hook and help modal
- `/src/frontend/components/ImageGenerateButton.jsx` - Added queue support
- `/src/frontend/components/GameDashboard.jsx` - Reordered layout
- `/src/frontend/components/ImageGallery.jsx` - Fixed image URLs
- `/src/frontend/components/ImagePopup.jsx` - Fixed image URLs

## Usage Tips
- Select text carefully before using shortcuts
- Queue multiple images by clicking Generate Image repeatedly
- Use Ctrl+A to preview how text will sound in the game
- Click the ⌨️ Shortcuts button to see available shortcuts