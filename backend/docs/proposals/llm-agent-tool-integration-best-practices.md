# LLM Agent Tool Integration Best Practices

This proposal captures the patterns we added while hardening the Combat Initiator agent so we can apply them consistently across other agents and tools.

## 1. Separate Narrative From Authoritative State
- Treat tool output as the source of truth for structured data (`initiative_order`, HP changes, etc.).
- Allow the LLM to narrate around those facts, but never let the raw model response overwrite deterministic values.
- During normalization, reconstruct the final payload from the persisted tool data and use the LLM response only for optional flavor fields.

## 2. Persist Tool Results In A Run Context
- Provide each agent run with a lightweight context object (e.g. `CombatInitiatorRunContext`).
- Expose helper methods such as `record_initiative_roll()` that tool handlers call to stash normalized results.
- Pass the run context into `AgentRunner.run(...)` so every tool invocation has access to shared state via `ctx.context`.
- During normalization, read from the run context first and use those values to fill or override LLM emitted structures.

### When To Use Run Context
- Any tool that produces data we need to trust later (dice rolls, resource costs, state transitions).
- Multi-step workflows where one tool’s result feeds another tool or downstream agent logic.
- Situations where replay/determinism is important for auditing or re-simulation.

## 3. Normalize Through Data Models, Not Dict Munging
- Add model-level defaults and `model_validator` hooks inside our Pydantic objects (e.g. `CombatNarrative`, `BattlefieldConfig`).
- Provide convenience methods like `apply_context_defaults()` so caller code supplies fallbacks without duplicating logic.
- Always call `Model.model_validate(...)` on incoming blobs before mutation. This ensures type coercion and centralizes schema changes.
- Prefer returning model instances to `dict` whenever possible; convert to dict only at the serialization boundary.

## 4. Tool Handler Guidelines
- Accept both dicts and JSON strings; raise clear errors for invalid payloads.
- Coerce relevant fields (e.g. `int(total)`) and compute derived values (dex score) before persisting.
- Log tool actions in a consistent format for debugging (`🎲 {name} rolls initiative ...`).
- Return compact JSON payloads for the LLM, but rely on the run context for authoritative storage.

## 5. Normalization Pipeline Checklist
1. Extract structured data with `_extract_output_data()` to guard against strings or legacy wrappers.
2. Validate narrative/battlefield/conditions via their data models and apply contextual fallbacks.
3. Build a `combatant_lookup` map for easy enrichment (player flags, initiative modifiers).
4. Merge any LLM-provided initiative entries with run-context rolls, dedupe by name, and sort once at the end.
5. Fall back to minimal scaffolds (`_build_minimal_initiation`) if validation fails, but still backfill initiative via context.

## 6. Testing & Validation
- Provide quick Python snippets or scripts that instantiate the agent, inject run-context data, and call `_normalize_output()`.
- Test cases should confirm that:
  - Missing initiative entries are filled from the run context.
  - Narrative and battlefield defaults respect scene/player action context.
  - The final `CombatInitiation` passes `.model_validate()`.
- Where possible, add campaign-specific regression scripts (e.g. `scripts/test_combat_initiator_campaign41.py`).

## 7. Applying To Other Agents
- Identify other agents with structured outputs (DM formatter, exploration, combat turn engine).
- Audit each tool to see if its results should be captured via run-context hooks.
- Move repetitive default handling (status summaries, scene metadata) into shared data models with helper methods.
- Write a short “normalization helper” per agent that consumes run-context state, not raw LLM output.

## Action Items
1. Create run-context scaffolds for other agents relying on deterministic tool outputs (e.g. Combat Agent, Rule Enforcer).
2. Gradually migrate existing dict-based normalization logic to rely on model validators and helper methods.
3. Document per-agent expectations for what must come from tools versus what can be generated freely by the LLM.
4. Add regression scripts/tests that assert run-context values override LLM-provided ones.

Adopting these patterns keeps the LLM focused on narration while our code maintains authoritative state, leading to reproducible, debuggable agent behavior.
