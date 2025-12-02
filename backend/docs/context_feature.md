# Context Feature Documentation

## Overview
The context feature allows users to add background information, world-building details, or character notes to their campaign without triggering a DM response. This context is saved to the campaign history and will be used by the DM in future responses.

## Implementation

### Backend

1. **New API Endpoint** (`/api/proto/add-context`):
   - Accepts context messages via protobuf
   - Saves to campaign history without triggering DM response
   - Returns success/failure status

2. **Orchestrator Method** (`add_context`):
   - Loads campaign if not already active
   - Adds context with `[CONTEXT]` prefix
   - Saves to campaign history
   - Efficiently handles repeated context additions to same campaign

### Frontend

1. **Context Input Modal**:
   - Accessible via "Add Context" button
   - Allows multi-line context entry
   - Disabled when no campaign is active

2. **Protobuf Service**:
   - New `addContext` method
   - Sends context to backend
   - Handles success/error responses

3. **Visual Feedback**:
   - Context messages shown with `[CONTEXT]` prefix
   - Displayed in chat history
   - Marked with `isContext: true` flag

## Usage

### Adding Context
1. Click "Add Context" button in header
2. Enter context information (e.g., "The bartender's name is Tom and he has a secret past as a pirate")
3. Click "Add" to save
4. Context appears in chat with `[CONTEXT]` prefix
5. Context is saved to campaign history

### How DM Uses Context
- The DM sees all context messages in the conversation history
- Context influences future responses naturally
- DM incorporates details from context into narrative
- No immediate response is generated when context is added

## Benefits

1. **Persistent World-Building**: Add NPCs, locations, and lore that persists
2. **No Interruption**: Add details without breaking narrative flow
3. **Player Notes**: Players can add reminders or important information
4. **Campaign Customization**: Shape the world to your preferences

## Technical Details

### Message Format
```javascript
{
  role: "user",
  content: "[CONTEXT] The tavern has a secret basement...",
  timestamp: "2024-01-01T12:00:00Z"
}
```

### Storage
- Saved to `campaigns/{campaign_id}/logs/chat_history.json`
- Loaded with campaign history
- Treated as user messages with special prefix

## Examples

### World-Building Context
```
[CONTEXT] The city of Waterdeep has recently suffere