# Player View Implementation Specification

## Project Overview

This specification outlines the implementation of a **Player View** component for Gaia, an AI-powered D&D roleplaying game. The Player View provides a streamlined interface for individual players to join and participate in ongoing campaigns, distinct from the more comprehensive Dungeon Master View.

## Objectives

- **Barrier-Free Player Experience**: Enable players to join campaigns with minimal setup
- **Focused Functionality**: Provide only essential player tools (character sheet, narrative view, voice input)
- **Voice-First Design**: Prioritize voice interaction to match Gaia's accessibility goals
- **Visual Immersion**: Large narrative displays with generated scene imagery
- **Mobile-Responsive**: Ensure playability across devices

## Design Analysis

Based on the provided mockup (`player-view.png`), the interface consists of three main sections:

### Left Panel: Character Sheet
- Character portrait and identity
- Core D&D stats (STR, DEX, CON, INT, WIS, CHA)
- Expandable abilities section
- Clean, card-based layout

### Center Panel: Narrative Display
- Large scene image with dramatic fantasy artwork
- Text overlay with current narrative content
- Progress indicator for story/turn progression
- Modal-style presentation with close button

### Bottom Panel: Player Controls
- Prominent voice input microphone
- Recording indicator and user avatar
- Simplified media gallery with thumbnails
- Dice rolling functionality
- Settings access

## Technical Architecture

### Component Hierarchy
```
PlayerView (Main Container)
├── CharacterSheet (Left Panel)
│   ├── CharacterPortrait
│   ├── CharacterInfo (name, class)
│   ├── StatsDisplay (D&D ability scores)
│   └── AbilitiesPanel (expandable)
├── PlayerNarrativeView (Center Panel)
│   ├── SceneImageDisplay (large background image)
│   ├── NarrativeTextOverlay (story content)
│   └── ProgressIndicator (turn/story progress)
└── PlayerControls (Bottom Panel)
    ├── VoiceInputPanel (primary interaction)
    ├── PlayerMediaGallery (scene thumbnails)
    ├── DiceRoller (D20 + modifiers)
    └── SettingsButton (player preferences)
```

### File Structure
```
frontend/src/components/player/
├── PlayerView.jsx                    # Main container
├── PlayerView.css                    # Primary styles
├── CharacterSheet/
│   ├── CharacterSheet.jsx
│   ├── CharacterSheet.css
│   ├── CharacterPortrait.jsx
│   ├── StatsDisplay.jsx
│   └── AbilitiesPanel.jsx
├── PlayerNarrativeView/
│   ├── PlayerNarrativeView.jsx
│   ├── PlayerNarrativeView.css
│   ├── SceneImageDisplay.jsx
│   └── ProgressIndicator.jsx
└── PlayerControls/
    ├── PlayerControls.jsx
    ├── PlayerControls.css
    ├── VoiceInputPanel.jsx
    ├── DiceRoller.jsx
    └── PlayerMediaGallery.jsx
```

## Component Specifications

### PlayerView.jsx (Main Component)
**Purpose**: Root container managing player state and layout
**Props**:
- `campaignId`: Current campaign identifier
- `playerId`: Unique player identifier
- `characterData`: Player's character information
- `latestStructuredData`: Game state from DM
- `onPlayerAction`: Callback for player actions

**Key Features**:
- Responsive grid layout (CSS Grid)
- State management for player actions
- Integration with existing apiService
- Auth0 authentication integration

### CharacterSheet Component
**Purpose**: Display player's character information and stats
**Features**:
- D&D 5e ability scores display
- Character portrait (generated or uploaded)
- Basic character info (name, class, level)
- Expandable abilities/spells section
- Real-time stat updates from game state

### PlayerNarrativeView Component
**Purpose**: Immersive story display with generated imagery
**Features**:
- Large background scene images
- Narrative text overlay with proper typography
- Progress indicator for turn management
- Modal-style presentation
- Integration with ImageGalleryWithPolling system

### PlayerControls Component
**Purpose**: Primary interaction panel for player actions
**Features**:
- Voice input with WebSocket integration
- Visual recording indicators
- Simplified media gallery (4-6 recent images)
- D20 dice roller with modifiers
- Settings access for player preferences

## Integration Points

### API Integration
- **Existing Services**: Leverage current `apiService.js` for all backend communication
- **Campaign Joining**: New endpoint for players to join campaigns via code/link
- **Player Actions**: Send player inputs through existing chat API with player context
- **Character Management**: Character creation/loading through existing character system

### Voice System Integration
- **STT Integration**: Use existing `ContinuousTranscription` component
- **TTS Playback**: Player-specific audio controls and voice selection
- **Voice Activity**: Visual indicators for when player is speaking/listening

### State Management
- **Campaign State**: Subscribe to campaign updates via polling/WebSocket
- **Player State**: Manage individual player progress and character data
- **Synchronization**: Ensure player view stays synchronized with DM view

## User Experience Flow

### Joining a Campaign
1. Player receives campaign invite (code/link)
2. Enter campaign code or click join link
3. Select/create character (streamlined process)
4. Enter player view with current game state

### Gameplay Loop
1. **Listen**: Receive DM narration via audio/text
2. **View**: See current scene and character status
3. **Act**: Input action via voice or text
4. **React**: See results and updated game state

### Voice-First Interaction
1. Press and hold microphone button
2. Speak action ("I search the room")
3. Visual feedback during recording
4. Auto-send when recording stops
5. Receive DM response via TTS

## Design Guidelines

### Visual Design
- **Dark Gaming Theme**: Consistent with existing Gaia aesthetic
- **High Contrast**: Ensure readability over scene images
- **Mobile-First**: Touch-friendly controls and responsive layout
- **Accessibility**: Screen reader support and keyboard navigation

### Color Palette (Tailwind)
- `gaia-dark`: #0a0a0a (background)
- `gaia-light`: #1a1a1a (panels)
- `gaia-accent`: #8b5cf6 (primary purple)
- `gaia-character`: #3b82f6 (character info blue)
- `gaia-narrative`: #f59e0b (narrative highlights)

### Typography
- **Headers**: Inter font, semibold weights
- **Body Text**: Inter font, regular weight
- **Narrative**: Larger font sizes for immersion
- **Stats**: Monospace for consistency

## Implementation Phases

### Phase 1: Core Layout (Week 1)
- [ ] Create PlayerView main component
- [ ] Implement responsive grid layout
- [ ] Basic routing and authentication
- [ ] Connect to existing API services

### Phase 2: Character Sheet (Week 1)
- [ ] Build CharacterSheet component
- [ ] Implement StatsDisplay with D&D scores
- [ ] Add CharacterPortrait component
- [ ] Create expandable AbilitiesPanel

### Phase 3: Narrative Display (Week 2)
- [ ] Create PlayerNarrativeView component
- [ ] Implement SceneImageDisplay with overlay
- [ ] Add ProgressIndicator for turn tracking
- [ ] Connect to campaign image generation

### Phase 4: Player Controls (Week 2)
- [ ] Build PlayerControls component
- [ ] Implement VoiceInputPanel with recording
- [ ] Create DiceRoller component
- [ ] Add simplified PlayerMediaGallery

### Phase 5: Integration & Testing (Week 3)
- [ ] Connect voice system (STT/TTS)
- [ ] Implement campaign joining workflow
- [ ] Add real-time synchronization
- [ ] Mobile responsive testing
- [ ] Accessibility testing

## Technical Considerations

### Performance Optimization
- **Image Loading**: Lazy loading for scene images
- **State Updates**: Debounced API calls for real-time sync
- **Audio Management**: Efficient TTS queue management
- **Mobile Performance**: Optimized touch interactions

### Security & Privacy
- **Authentication**: Auth0 integration for secure access
- **Campaign Access**: Role-based access control (player vs DM)
- **Voice Data**: Secure handling of voice recordings
- **Character Data**: Encrypted character information storage

### Scalability
- **Multiple Players**: Support for 2-6 players per campaign
- **Concurrent Campaigns**: Multiple active campaigns per player
- **Real-time Updates**: Efficient WebSocket or polling for game state
- **Image Storage**: CDN integration for generated scene images

## Testing Strategy

### Unit Testing
- Component rendering tests
- State management validation
- API integration tests
- Voice system functionality

### Integration Testing
- Player joining workflow
- DM-Player synchronization
- Cross-device compatibility
- Voice input/output flow

### User Experience Testing
- New player onboarding
- Voice interaction usability
- Mobile device testing
- Accessibility compliance

## Success Metrics

### Technical Metrics
- Page load time < 2 seconds
- Voice input latency < 500ms
- 99% uptime for player sessions
- Cross-browser compatibility

### User Experience Metrics
- Player onboarding completion rate > 90%
- Average session duration > 30 minutes
- Voice interaction success rate > 95%
- Mobile usage percentage > 40%

## Future Enhancements

### Advanced Features
- **Character Customization**: Avatar editor and appearance options
- **Inventory Management**: Visual inventory with drag-and-drop
- **Combat Interface**: Dedicated combat mode with initiative tracking
- **Social Features**: Player-to-player communication and emotes

### Platform Extensions
- **Mobile App**: Native iOS/Android applications
- **VR Integration**: Virtual reality campaign experiences
- **Tablet Optimization**: Large-screen optimized layouts
- **Offline Mode**: Limited offline functionality for character viewing

## Dependencies

### Existing Gaia Components
- `apiService.js`: Backend communication
- `ContinuousTranscription`: Voice input system
- `ImageGalleryWithPolling`: Image display system
- Tailwind components and styling utilities

### New Dependencies
- Character data models and validation
- Player session management utilities
- Dice rolling algorithms and animations
- Real-time synchronization infrastructure

---

This specification serves as the foundation for implementing the Player View feature in Gaia, ensuring a cohesive, accessible, and immersive experience for players joining D&D campaigns.