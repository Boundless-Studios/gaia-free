# Image Generation Refactor Plan

## Objective
Split the current D&D image generator agent into two deterministic stages: an agent that produces a structured image generation plan, and a separate executor that performs image rendering and persistence. This removes side effects from the agent and makes execution predictable, allowing downstream systems to control when images are fetched or persisted.

## Work Breakdown

### 1. Define the plan contract
- Create `ImageGenerationPlan` (and optional `ImageGenerationResult`) in `backend/src/core/image/image_generation_plan.py`.
- Include fields: `enhanced_prompt`, `image_type`, `style`, `size`, `session_id`, and optional metadata dict.
- Provide helpers to convert to/from JSON dicts so agent payloads remain tool-friendly.

### 2. Refactor planner tool (`backend/src/game/dnd_agents/image_generator.py`)
- Rename the existing `generate_image_tool` to a planner function that only returns an `ImageGenerationPlan`.
- Remove direct calls to `get_image_service_manager` and `image_artifact_store`.
- Update the tool schema and `run_with_tools` / `run_without_tools` paths to emit the plan (no file IO).
- Clean up logging to reflect “planning” rather than “generation”.

### 3. Implement deterministic executor
- Add `backend/src/core/image/image_generation_executor.py` with async `execute_plan(plan: ImageGenerationPlan) -> ImageGenerationResult`.
- Move current generation + persistence logic into the executor: call image service manager, persist via `image_artifact_store`, derive HTTP/proxy URLs, clean temporary files, and record provider info.
- Differentiate planning vs execution errors for clearer retries.

### 4. Update orchestrators and helpers
- Adjust `backend/src/core/agent_orchestration/orchestrator.py`, `.../combat_orchestrator.py`, and `backend/src/core/character/portrait_generator.py` to:
  1. request a plan from the agent,
  2. handle planning failures early,
  3. pass the plan to the executor and return the execution result.
- Ensure return payloads still include expected fields (`image_url`, `proxy_url`, `storage_path`, etc.).

### 5. API and consumer adjustments
- Review endpoints such as `backend/src/api/routes/chat.py` (and websocket broadcasters) to consume the new two-stage flow.
- Surface plan details when execution fails if useful for retries or UI messaging.

### 6. Testing
- Add unit tests in `backend/test/core/image/test_image_generation_executor.py` that stub the image service manager/artifact store to verify persistence, cleanup, and error paths.
- Update agent/orchestrator tests (e.g., `backend/test/agents/test_dungeon_master_agent.py`, combat agent tests) to expect plan-first behavior or to mock the executor.
- Supply fixtures/mocks so tests don’t call real providers.

### 7. Documentation and scripts
- Refresh `docs/character-portrait-creator.md` and any other guides mentioning the agent saving images so they describe the plan → execute split.
- Update helper scripts like `backend/scripts/claude_helpers/test_image_types.py` to run both stages or stub the executor when validating prompts.

### 8. Cleanup
- Remove unused imports (e.g., `image_artifact_store`) from the planner module once refactored.
- Ensure new modules are exported via `backend/src/core/image/__init__.py` if required.
- Run targeted test suites (`python run_tests.py --markers "not slow and not integration"`) and document any follow-up integration coverage needs.

## Risks & Follow-ups
- Downstream callers may assume immediate URLs; verify all call sites handle plan-only responses before execution.
- Need to confirm the executor runs in environments with access to the image services (local, staging, prod).
- Consider adding caching or deduplication of identical plans in future iterations.
