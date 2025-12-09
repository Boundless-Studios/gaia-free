# Automatic SFX Detection & Click-to-Generate Feature

## Overview

This feature automatically detects sound effect-worthy phrases in DM narrative messages and renders them as clickable, underlined text. When clicked, these phrases trigger Eleven Labs SFX generation to enhance immersion.

**Current State**: Manual SFX generation via keyboard shortcut "9" (requires text selection)
**Target State**: Automatic detection with one-click generation from underlined phrases

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│ ChatMessage.jsx                                                  │
│ - Renders DM messages with structured_data.narrative            │
│ - Passes narrative text to SFXTextParser                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ SFXTextParser.jsx (NEW)                                          │
│ - Strips code blocks and OOC content                            │
│ - Calls sfxDetector.detectSFXPhrases(text)                      │
│ - Renders text with interleaved SFXTrigger components           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ sfxDetector.js (NEW)                                             │
│ - Loads sfx_catalog.json                                        │
│ - Builds Aho-Corasick trie for multi-pattern matching           │
│ - Implements detection pipeline:                                │
│   1. Normalize text with synonyms                               │
│   2. Exact phrase matching via trie (catalog entries)           │
│   3. Regex template matching (impacts, weather, magic, etc.)    │
│   4. Onomatopoeia detection                                     │
│   5. Score candidates by priority + heuristics                  │
│   6. Resolve overlaps (longest/highest priority wins)           │
│   7. Limit to top 3 per message                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ SFXTrigger.jsx (NEW)                                             │
│ - Renders clickable <span> with dotted underline               │
│ - onClick: Checks cache, then generates SFX via sfxContext      │
│ - Shows generating state with pulse animation                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ sfxContext.jsx (ENHANCED)                                        │
│ - New: sfxCache Map for deduplication                           │
│ - New: getCachedSFX(sfxId, phrase)                              │
│ - New: cacheSFX(sfxId, phrase, audioPayload)                    │
│ - Modified: generateSoundEffect() caches results                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detection Algorithm

### Multi-Stage Pipeline

**Stage 1: Text Normalization**
- Convert to lowercase
- Apply synonym replacements (e.g., "gate" → "door", "thunderclap" → "thunder")
- Preserve original text positions for rendering

**Stage 2: Catalog Matching (Aho-Corasick Trie)**
- Build trie from all `triggers` in sfx_catalog.json
- Find all exact phrase matches in O(n + m + z) time
  - n = text length
  - m = total pattern length
  - z = number of matches
- Longest match wins when overlaps occur

**Stage 3: Regex Template Matching**
```javascript
{
  impacts: /\b(door|gate|window|chest|portcullis|hatch)\b.{0,6}\b(slam|bang|crash|shut|close)s?\b/gi,
  weather: /\b(thunder|lightning|rain|storm|gale|howl|wind|snow|hail)\b/gi,
  magic: /\b(crackle|flare|burst|whoosh|arcane|chant|incantation|spell|magic|glow)\b/gi,
  creatures: /\b(roar|howl|hiss|screech|snarl|bellow|growl|chirp)\b/gi,
  ambience: /\b(footsteps|stomp|clank|clink|rustle|creak|drip|echo|whisper)\b/gi,
  combat: /\b(slash|strike|parry|clang|clash|hit|pierce|thud|clatter)\b/gi
}
```

**Stage 4: Onomatopoeia Detection**
- Match against comprehensive list:
  - `boom|crash|clang|thunk|sizzle|crackle|whoosh|thud|rumble|splash|bang|clank|hiss|screech|roar|howl|whisper|rustle|squelch|splat|clink|clunk|swoosh|zing|pop|fizz|buzz|hum|chirp|tweet`

**Stage 5: Scoring**
```javascript
score = basePriority (from catalog or default 5)
  + (catalogMatch ? 5 : 0)
  + min(phraseLength / 10, 3)
  + (hasNounVerbCombo ? 3 : 0)
```
- Accept candidates with score ≥ threshold (e.g., 8)

**Stage 6: Overlap Resolution**
- Sort by priority DESC, then length DESC
- Greedy selection: Pick highest-scoring non-overlapping spans
- Track used character positions to prevent conflicts

**Stage 7: Limit Output**
- Return top 3 matches per message
- Prevents UI clutter in lengthy narratives

---

## Data Structures

### SFX Catalog (`sfx_catalog.json`)

Location: `frontend/src/data/sfx_catalog.json`

```json
{
  "entries": [
    {
      "id": "door_slam",
      "triggers": [
        "door slams",
        "door slam",
        "gate slams",
        "iron-banded door slams",
        "slam shut",
        "slams shut",
        "door bangs",
        "door crashes"
      ],
      "label": "Door Slam",
      "priority": 10,
      "category": "impact"
    },
    {
      "id": "thunderclap",
      "triggers": [
        "thunderclap",
        "thunder",
        "thunder rumbles",
        "thunder booms",
        "thunder crashes",
        "lightning strikes",
        "lightning flash"
      ],
      "label": "Thunder",
      "priority": 8,
      "category": "weather"
    },
    {
      "id": "sword_clash",
      "triggers": [
        "swords clash",
        "blades clash",
        "steel rings",
        "metal clashes",
        "weapons collide"
      ],
      "label": "Sword Clash",
      "priority": 9,
      "category": "combat"
    }
    // ... 100+ total entries
  ],
  "onomatopoeia": [
    "boom", "crash", "clang", "thunk", "sizzle", "crackle",
    "whoosh", "thud", "rumble", "splash", "bang", "clank",
    "hiss", "screech", "roar", "howl", "whisper", "rustle",
    "squelch", "splat", "clink", "clunk", "swoosh", "zing",
    "pop", "fizz", "buzz", "hum", "chirp", "tweet"
  ],
  "synonyms": {
    "thunder": ["storm", "lightning", "thunderclap"],
    "door": ["gate", "portal", "entrance", "hatch", "portcullis"],
    "slam": ["bang", "crash", "shut", "close"],
    "footsteps": ["steps", "footfalls", "treads"],
    "sword": ["blade", "steel", "weapon"],
    "fire": ["flame", "blaze", "inferno"],
    "water": ["stream", "river", "brook"],
    "wind": ["gale", "breeze", "gust"]
  }
}
```

**Catalog Categories** (100+ entries planned):
1. **Impacts** (20): Doors, chests, gates, windows, falling objects
2. **Weather** (15): Thunder, rain, wind, snow, storms
3. **Magic** (20): Spells, arcane effects, magical bursts
4. **Combat** (25): Weapons, armor, shields, hits
5. **Creatures** (15): Roars, growls, screeches, animal sounds
6. **Ambience** (10): Footsteps, creaking, dripping, echoes
7. **Destruction** (10): Breaking, shattering, crumbling
8. **Liquids** (5): Pouring, splashing, bubbling
9. **Fire** (5): Crackling, roaring flames
10. **Misc** (10): Bells, horns, chains, etc.

### Detection Result Format

```javascript
{
  phrase: "door slams shut",    // Original matched text
  startIdx: 45,                  // Character position in original text
  endIdx: 61,                    // End position
  sfxId: "door_slam",           // Catalog entry ID (null if regex/ono match)
  priority: 10,                  // From catalog or default
  category: "impact",            // For styling (optional)
  score: 18                      // Calculated score
}
```

---

## UI Components

### SFXTextParser.jsx

**Purpose**: Parse narrative text and render with SFX triggers

**Props**:
- `text` (string): Raw narrative content
- `sessionId` (string): Current game session ID

**Algorithm**:
1. Strip code blocks: `\`\`\`...\`\`\``
2. Strip OOC content: `((OOC: ...))`
3. Call `sfxDetector.detectSFXPhrases(cleanText)`
4. Build JSX array:
   - Interleave plain text segments with `<SFXTrigger>` components
   - Preserve original text rendering

**Example Output**:
```jsx
<>
  The iron-banded
  <SFXTrigger phrase="door slams shut" sfxId="door_slam" category="impact" />
   behind you. You hear a
  <SFXTrigger phrase="thunderclap" sfxId="thunderclap" category="weather" />
   in the distance.
</>
```

---

### SFXTrigger.jsx

**Purpose**: Clickable underlined span that generates SFX

**Props**:
- `phrase` (string): Text to display and send to API
- `sfxId` (string|null): Catalog ID for caching
- `category` (string): Visual category for styling
- `sessionId` (string): Game session

**State**:
- `isGenerating` (boolean): Show loading state

**Behavior**:
- **onClick**:
  1. Check `getCachedSFX(sfxId || phrase)`
  2. If cached: Play immediately via `playSfx()`
  3. If not cached: Call `generateSoundEffect(phrase, sessionId, sfxId)`
  4. Show pulse animation during generation
- **Hover**: Enhance underline visibility (handled by CSS)
- **Title**: Tooltip showing "Click to generate sound effect: {phrase}"

**Styling** (dotted underline, always visible, subtle):
```css
.sfx-trigger {
  cursor: pointer;
  color: inherit;
  position: relative;
  text-decoration: underline dotted;
  text-decoration-thickness: 2px;
  text-underline-offset: 0.18em;
  text-decoration-color: rgba(124, 58, 237, 0.85);
  background: linear-gradient(
    120deg,
    rgba(124, 58, 237, 0.12),
    rgba(56, 189, 248, 0.12)
  );
  border-radius: 4px;
  box-shadow: inset 0 -0.25em rgba(124, 58, 237, 0.16);
  transition:
    color 0.2s ease,
    text-decoration-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.sfx-trigger:hover {
  color: #4c1d95;
  text-decoration-color: #4c1d95;
  box-shadow:
    inset 0 -0.35em rgba(124, 58, 237, 0.26),
    0 0.35em 1em rgba(76, 29, 149, 0.18);
  background: linear-gradient(
    120deg,
    rgba(124, 58, 237, 0.2),
    rgba(56, 189, 248, 0.2)
  );
}

.sfx-trigger.generating {
  animation: pulse 1s ease-in-out infinite;
  text-decoration-style: solid;
  text-decoration-thickness: 3px;
}
```

The base gradient and inset shadow create a light highlight on matched phrases even before hover, while the thicker underline and richer hover state make the triggers easy to spot at a glance.

---

## Caching System

### Purpose
Avoid duplicate API calls for identical SFX phrases within a session.

### Implementation in `sfxContext.jsx`

**New State**:
```javascript
const [sfxCache, setSfxCache] = useState(new Map());
```

**Cache Key Generation**:
```javascript
const cacheKey = (sfxId, phrase) => {
  return sfxId || phrase.toLowerCase().trim();
};
```

**Cache Operations**:
```javascript
// Retrieve from cache
const getCachedSFX = (sfxId, phrase) => {
  const key = cacheKey(sfxId, phrase);
  return sfxCache.get(key);
};

// Store in cache after generation
const cacheSFX = (sfxId, phrase, audioPayload) => {
  const key = cacheKey(sfxId, phrase);
  setSfxCache(prev => new Map(prev).set(key, audioPayload));
};
```

**Modified `generateSoundEffect()`**:
```javascript
const generateSoundEffect = async (text, sessionId, sfxId = null) => {
  // ... existing API call logic ...

  // After successful response:
  const audioPayload = response.data.audio;
  cacheSFX(sfxId, text, audioPayload);

  return audioPayload;
};
```

**Cache Lifecycle**:
- Persists for duration of session
- Cleared on page refresh
- Future enhancement: Could persist to localStorage with TTL

---

## Integration Points

### ChatMessage.jsx

**Current Narrative Rendering**:
```javascript
<div className="message-narrative">
  <div className="label">📖 Narrative</div>
  <div className="content">
    {getNarrativeText()}
  </div>
  {/* Play/Stop buttons */}
</div>
```

**Updated with SFX Parser**:
```javascript
import SFXTextParser from './SFXTextParser';

<div className="message-narrative">
  <div className="label">📖 Narrative</div>
  <div className="content">
    <SFXTextParser
      text={getNarrativeText()}
      sessionId={sessionId}
    />
  </div>
  {/* Play/Stop buttons */}
</div>
```

**Scope**: Only applied to narrative sections, NOT answer sections or player messages.

---

## Quality Guards

### 1. Code Block Exclusion
Skip detection in code fences:
```javascript
text = text.replace(/```[\s\S]*?```/g, '');
```

### 2. OOC Content Exclusion
Skip out-of-character annotations:
```javascript
text = text.replace(/\(\(OOC:.*?\)\)/gi, '');
```

### 3. Deduplication Within Message
The overlap resolution algorithm ensures no duplicate or overlapping highlights within a single message.

### 4. Limit Highlights Per Message
Hard cap of 3 SFX triggers per message to prevent visual clutter.

### 5. Cache Hit Check
Always check cache before making API calls to reduce costs and latency.

---

## File Structure

### New Files
```
frontend/
├── src/
│   ├── components/
│   │   ├── SFXTextParser.jsx          # Parser component
│   │   ├── SFXTrigger.jsx             # Clickable trigger component
│   │   └── SFXTrigger.css             # Styling
│   ├── services/
│   │   └── sfxDetector.js             # Detection algorithm
│   └── data/
│       └── sfx_catalog.json           # Curated catalog (100+ entries)
```

### Modified Files
```
frontend/
├── src/
│   ├── components/
│   │   └── ChatMessage.jsx            # Add SFXTextParser integration
│   └── context/
│       └── sfxContext.jsx             # Add caching system
```

---

## Testing Strategy

### Unit Tests (sfxDetector.js)

**Test Cases**:
1. **Catalog Exact Match**
   - Input: "The door slams shut behind you."
   - Expected: Match "door slams shut" with sfxId="door_slam"

2. **Regex Template Match**
   - Input: "You hear a chest bang open."
   - Expected: Match "chest bang" via impacts regex

3. **Onomatopoeia Match**
   - Input: "BOOM! The explosion echoes."
   - Expected: Match "BOOM" from onomatopoeia list

4. **Synonym Normalization**
   - Input: "The gate crashes shut."
   - Expected: Normalize "gate" → "door", match "door crashes"

5. **Overlap Resolution**
   - Input: "The door slams with a loud crash."
   - Expected: "door slams" (priority 10, longer) wins over "crash" (priority 5)

6. **Limit Enforcement**
   - Input: Text with 5 potential matches
   - Expected: Return only top 3

7. **Code Block Exclusion**
   - Input: "You see ```door slams``` in the code."
   - Expected: No matches

8. **Case Insensitivity**
   - Input: "THUNDERCLAP echoes overhead."
   - Expected: Match "THUNDERCLAP"

### Integration Tests

**Test Cases**:
1. **Render with SFX Triggers**
   - Verify dotted underlines appear in narrative
   - Check hover effects work

2. **Click Generates SFX**
   - Click trigger → API call → audio plays
   - Verify WebSocket broadcast to all session clients

3. **Cache Prevents Duplicate Calls**
   - Click same phrase twice
   - Verify only one API call made

4. **Generating State Animation**
   - Click trigger → pulse animation appears
   - Animation stops when audio ready

5. **Multiple Triggers in One Message**
   - Render message with 3+ potential SFX
   - Verify all are clickable and independent

### Manual Testing in Docker

**Setup**:
```bash
# Ensure containers running
docker ps | grep gaia-frontend-dev

# View logs
docker logs -f gaia-frontend-dev
```

**Test Scenarios**:
1. Send DM message: "The iron-banded door of the Weeping Willow slams shut behind you. You hear a thunderclap in the distance."
2. Verify underlines appear on "slams shut" and "thunderclap"
3. Click each trigger, verify SFX plays
4. Click again, verify cache hit (no duplicate API call in logs)
5. Test edge cases: Very long narrative, no matches, code blocks

---

## Performance Considerations

### Aho-Corasick Trie Efficiency
- **Build Time**: O(m) where m = total length of all patterns
- **Search Time**: O(n + z) where n = text length, z = matches
- Built once on component mount, reused for all detections

### Regex Optimization
- Precompile all regex patterns at module load
- Use non-greedy quantifiers (`.{0,6}`) to minimize backtracking
- Limit context window (max 6 chars between noun and verb)

### Rendering Optimization
- SFXTextParser returns memoized JSX (React.memo)
- Only re-renders if text or sessionId changes
- Minimal DOM manipulation (interleaved text/components)

### Caching Benefits
- Eliminates redundant API calls (typical session may have 30% duplicate phrases)
- Reduces latency (instant playback for cached SFX)
- Lowers Eleven Labs API costs

---

## Future Enhancements

### Phase 2 (Optional)
1. **User Preferences**: Toggle auto-detection on/off in settings
2. **Custom Catalog**: Allow DMs to add custom SFX entries per campaign
3. **Confidence Scores**: Show visual indicator (single vs double underline) for high/low confidence matches
4. **Context-Aware Detection**: Use previous message history to improve accuracy
5. **Batch Generation**: Preemptively generate SFX for all detected phrases in background
6. **LocalStorage Cache**: Persist cache across sessions with TTL (e.g., 24 hours)

### Phase 3 (Advanced)
1. **LLM Classifier**: Optional backend endpoint for ambiguous phrases
2. **User Feedback Loop**: "Was this a good SFX?" thumbs up/down to train catalog
3. **Analytics**: Track most-clicked SFX to optimize catalog priorities
4. **Keyboard Navigation**: Tab through underlined phrases, Enter to generate

---

## Implementation Checklist

- [ ] Create `sfx_catalog.json` with 100+ entries across 10 categories
- [ ] Implement `sfxDetector.js` with Aho-Corasick trie
- [ ] Implement regex templates and onomatopoeia detection
- [ ] Implement scoring and overlap resolution
- [ ] Create `SFXTextParser.jsx` component
- [ ] Create `SFXTrigger.jsx` component and CSS
- [ ] Add caching to `sfxContext.jsx`
- [ ] Integrate `SFXTextParser` into `ChatMessage.jsx` (narrative only)
- [ ] Write unit tests for `sfxDetector.js`
- [ ] Test in Docker container with sample narratives
- [ ] Verify cache prevents duplicate API calls
- [ ] Verify WebSocket broadcast works for multiplayer sessions
- [ ] Test edge cases (long text, code blocks, OOC content)
- [ ] Performance testing with 100+ message history

---

## Success Criteria

✅ **Detection Accuracy**: 80%+ of obvious SFX phrases detected (door slams, thunder, etc.)
✅ **False Positive Rate**: <10% of underlines are inappropriate
✅ **Performance**: No visible lag when rendering messages with SFX
✅ **Cache Hit Rate**: 30%+ cache hits in typical 20-minute session
✅ **User Experience**: Dotted underlines are subtle, hover/click feel responsive
✅ **Multiplayer**: SFX broadcasts correctly to all players in session

---

## References

### Existing Files
- `frontend/src/components/ChatMessage.jsx` - Message rendering
- `frontend/src/components/ControlPanel.jsx:281-285` - Keyboard shortcut "9"
- `frontend/src/context/sfxContext.jsx` - SFX state management
- `frontend/src/services/sfxService.js` - API client
- `backend/src/gaia/infra/audio/sfx_service.py` - Eleven Labs integration
- `backend/src/gaia/api/routes/sound_effects.py` - SFX endpoints
- `backend/src/gaia/api/schemas/chat.py` - Message data structures

### Documentation
- `backend/docs/keyboard_shortcuts_and_ui_updates.md`
- `backend/docs/audio_queuing_and_keyboard_integration.md`
