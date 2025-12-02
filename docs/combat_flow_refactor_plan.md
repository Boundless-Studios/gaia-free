# Combat Flow Refactor Plan

## Current Flow Snapshot

1. `CombatOrchestrator.build_combat_action_request` captures a snapshot of the session into `CombatActionRequest`.
2. `Combat.run_player_combat` / `Combat.run_npc_combat` invokes the action selector using that snapshot only.
3. `_resolve_combat_actions` loops over selected actions, calling `CombatEngine.process_action` which mutates the `CombatSession` in-place.
4. To keep track of deltas, `_resolve_combat_actions` mirrors HP/AP/status updates into `CombatAgentRunContext` (`hp_changes`, `ap_changes`, `damage_dealt`, etc.).
5. Turn resolution consults the run context for remaining AP but still calls `CombatEngine.resolve_turn_transition`, which reads `request.combatants` (the stale snapshot) to decide who is active.
6. Narration uses the run context plus the original request to build output; orchestrator later persists the mutated session and logs results.

### Resulting Issues

- **Stale snapshots:** `CombatActionRequest` is never rebuilt after mechanical resolution, so downstream logic relies on a mix of run-context mirrors and outdated views.
- **Duplicate state tracking:** `CombatAgentRunContext` duplicates HP/AP/status deltas already present in the session, increasing the risk of divergence (e.g., Marcus staying "active" after dropping to 0 HP).
- **Turn resolution fragility:** Because `resolve_turn_transition` looks at stale `combatants`, we had to add ad-hoc refresh logic to sync the snapshot before turn advancement.

## Target Flow After Refactor

1. Start from the authoritative `CombatSession` and build the initial `CombatActionRequest` (unchanged).
2. After action selection, `_resolve_combat_actions` should:
   - Execute each action via `CombatEngine.process_action` (mutating the session once).
   - Collect results into a new immutable `CombatRunResult` object (actions, deltas, effects, suggested turn transition).
3. Downstream steps use `CombatRunResult` instead of digging into `CombatAgentRunContext`.
4. When mechanics finish, rebuild `CombatActionRequest` from the updated session so any subsequent turn-resolution logic sees fresh `CombatantView` data.
5. Narration and formatting consume `CombatRunResult` + rebuilt request; orchestrator persists the session last.

### Benefits

- Single source of truth (the session) with snapshots rebuilt on demand.
- Eliminates manual HP/AP mirroring and the need for refresh hacks.
- Clear contract for mechanical resolution output, simplifying testing and future tooling.

