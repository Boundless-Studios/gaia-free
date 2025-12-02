# Campaign Resume Feature

## Overview
When loading a campaign where the last message was from the user (player), the system displays a "Resume Adventure" button instead of the normal chat input. This gives users explicit control over when to continue their adventure while making it clear that the AI is waiting for them to resume.

## Implementation Details

### Backend Changes

1. **Campaign Endpoints** (`src/api/campaign_endpoints.py`):
   - Added `needs_response` field to campaign loading response
   - Checks if the last message in the campaign history is from the user
   - Sets `needs_response: true` when AI should respond

```python
# Check if the last message was from the user (needs AI response)
needs_response = False
if messages and messages[-1].get("role") == "user":
    needs_response = True
    logger.info(f"📝 Last message was from user, campaign needs AI response")
```

### Frontend Changes

2. **App Component** (`src/frontend/app/App.jsx`):
   - Checks the `needs_response` flag when loading campaigns
   - Shows a "Resume Adventure" button instead of the normal chat input
   - Works for both simple and structured campaigns
   - Resets to normal input after clicking resume

```javascript
// Check if we need to show resume button
if (data.needs_response) {
  console.log('🤖 Campaign needs AI response, showing resume button...');
  setNeedsResume(true);
}
```

3. **Resume Button UI**:
   - Replaces the entire chat input area with a prominent button
   - Styled with gradient background for visibility
   - Sends continuation message when clicked
   - Returns to normal chat input after clicking

## User Experience

1. User loads a campaign that ended with their message
2. System detects this and shows the campaign history
3. Instead of the chat input, a prominent "Resume Adventure" button appears
4. User clicks the button when ready to continue
5. System sends "Continue the adventure from where we left off."
6. DM responds naturally, picking up from where the conversation ended
7. Normal chat input returns for continued interaction

## Benefits

- **User Control**: Players decide when to resume, not forced immediately
- **Clear Visual Cue**: Prominent button makes it obvious the game is waiting
- **Seamless Continuation**: No need to remember context or manually prompt
- **Natural Flow**: The continuation message is clear but non-intrusive
- **Consistent Experience**: Works across all campaign types
- **Smart Detection**: Only shows resume button when actually needed

## Testing

Run the test script to verify functionality:
```bash
python3 scripts/claude_helpers/test_campaign_auto_response.py
```

Open the HTML test file to see the frontend behavior:
```bash
open scripts/claude_helpers/test_frontend_auto_response.html
```