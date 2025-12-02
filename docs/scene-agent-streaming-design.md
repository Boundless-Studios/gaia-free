# Scene Agent Streaming Design

## Overview

Scene agents currently return structured JSON via tool calls. To support streaming, they need a dual-mode architecture that can operate in either sync (JSON) or streaming (plain text) mode.

## Current Architecture

### Scene Agent Response Flow

1. **Scene agents** (DialogAgent, PerceptionAgent, etc.) return structured JSON:
   ```json
   {
     "npc_dialog": "...",
     "perception_results": [...],
     "environmental_details": "..."
   }
   ```

2. **SmartRouter._format_scene_response()** combines JSON fields into `answer`:
   ```python
   # Combines dialog, perception, environmental details
   answer = self._format_scene_response(result)
   ```

3. **Final output** sent to player via HTTP response

## Proposed Dual-Mode Architecture

### Mode Selection

Scene agents should accept a `streaming` parameter that determines their output mode:

```python
class BaseSceneAgent:
    async def run(
        self,
        user_input: str,
        context: Dict[str, Any],
        streaming: bool = False,
        broadcaster = None
    ) -> Union[Dict[str, Any], str]:
        """
        Args:
            streaming: If True, return plain text directly. If False, return JSON.
            broadcaster: WebSocket broadcaster for streaming chunks (if streaming=True)

        Returns:
            Dict[str, Any] if streaming=False (JSON for processing)
            str if streaming=True (plain text for direct player consumption)
        """
```

### Sync Mode (streaming=False)

**Current behavior - no changes needed:**
- Agent returns structured JSON via tool calls
- SmartRouter._format_scene_response() combines fields
- JSON provides structured data for game state updates

### Streaming Mode (streaming=True)

**New behavior:**
- Agent uses different system prompt instructing plain text output
- Agent directly generates the final player-facing text
- Output is based on how SmartRouter currently combines JSON fields
- Text is streamed via StreamingLLMClient
- Chunks sent to broadcaster for WebSocket delivery

## Implementation Changes

### 1. BaseSceneAgent Modifications

```python
class BaseSceneAgent:
    def _get_instructions(self, streaming: bool = False) -> str:
        """Return different instructions based on mode."""
        if streaming:
            return self._get_streaming_instructions()
        else:
            return self._get_sync_instructions()

    def _get_sync_instructions(self) -> str:
        """Current JSON-based instructions."""
        # Return existing tool-based instructions
        pass

    def _get_streaming_instructions(self) -> str:
        """Plain text instructions for streaming mode."""
        # Return instructions that produce final player text directly
        pass
```

### 2. Example: DialogAgent

**Sync Mode Instructions (current):**
```
Use the dialog_agent tool to:
- Return npc_dialog field
- Return environmental_details field
- Return perception_results array
```

**Streaming Mode Instructions (new):**
```
You are the DM describing an NPC interaction. Provide a narrative response that includes:
1. What the NPC says (in quotes)
2. How they say it (tone, body language)
3. Environmental details relevant to the conversation
4. Any perception checks the players notice

Format as flowing narrative text, not JSON. Write directly to the player.

Example:
"The innkeeper leans across the bar, lowering his voice. 'You're not from around here, are you?' His eyes dart nervously to the door. Behind him, you notice the shelves are mostly empty - unusual for a busy tavern. [Perception DC 12: You spot fresh scratches on the doorframe]"
```

### 3. SmartRouter Integration

```python
class SmartRouter:
    async def route(
        self,
        user_input: str,
        context: Dict[str, Any],
        broadcaster = None
    ) -> Tuple[str, str]:
        """Route to appropriate agent."""

        # Determine if streaming
        streaming = broadcaster is not None

        # Get appropriate agent
        agent = self._select_agent(user_input, context)

        if streaming:
            # Agent returns plain text directly
            response_text = await agent.run(
                user_input,
                context,
                streaming=True,
                broadcaster=broadcaster
            )
            return response_text, agent_type
        else:
            # Agent returns JSON, we format it
            result = await agent.run(user_input, context, streaming=False)
            answer = self._format_scene_response(result)
            return answer, agent_type
```

### 4. Streaming Execution

```python
class SceneAgent:
    async def run(self, user_input, context, streaming=False, broadcaster=None):
        if streaming:
            # Use StreamingLLMClient
            chunks = []
            async for chunk in self.streaming_llm_client.stream_completion(
                messages=self._build_messages(user_input, context, streaming=True),
                model=self.model
            ):
                chunks.append(chunk)
                if broadcaster:
                    await broadcaster.send_narrative_chunk(
                        session_id=context.get("campaign_id"),
                        content=chunk,
                        is_final=False
                    )

            final_text = "".join(chunks)
            if broadcaster:
                await broadcaster.send_narrative_chunk(
                    session_id=context.get("campaign_id"),
                    content="",
                    is_final=True
                )
            return final_text
        else:
            # Use regular LLM client with tools
            return await self.llm_client.run_with_tools(...)
```

## Prompt Design Strategy

For each scene agent type, the streaming prompt should produce text equivalent to what `_format_scene_response()` currently generates:

### DialogAgent
- Combines `npc_dialog` + `environmental_details` + `perception_results`
- Streaming prompt: "Narrate the NPC interaction with environment and perception details woven in"

### PerceptionAgent
- Combines `perception_results` array into formatted checks
- Streaming prompt: "Describe what the players notice, including DC checks where relevant"

### CombatActionAgent
- Combines `action_result` + `damage` + `effects`
- Streaming prompt: "Narrate the combat action result with mechanical outcomes"

### EnvironmentalAgent
- Combines `description` + `details` + `hazards`
- Streaming prompt: "Describe the environment with all relevant details"

## Testing Strategy

1. **Unit Tests**: Each agent in both modes
2. **Integration Tests**: SmartRouter routing to streaming agents
3. **Comparison Tests**: Verify streaming output quality matches sync output semantics
4. **WebSocket Tests**: Verify chunks are properly broadcast

## Migration Path

1. ✅ Implement dual-mode in BaseSceneAgent
2. ✅ Add streaming prompts for each agent type
3. ✅ Wire streaming parameter through SmartRouter
4. ✅ Test with DM already using streaming
5. ✅ Deploy streaming mode when broadcaster available
6. ✅ Keep sync mode as default for backward compatibility

## Benefits

- **Faster perceived response**: Users see content streaming in
- **Better UX**: Progressive disclosure instead of waiting for full response
- **Validation**: Parallel execution lets us validate streaming matches sync
- **Backward compatible**: Sync mode remains unchanged for non-WebSocket clients

## Notes

- Streaming mode produces plain text, no JSON parsing needed
- Sync mode remains source of truth during validation phase
- Scene agents join DM in supporting dual execution paths
- WebSocket connection required for streaming; HTTP clients get sync mode
