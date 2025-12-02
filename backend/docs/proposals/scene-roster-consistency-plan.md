# Scene & Character Roster Consistency Plan

## Context
- Dungeon Master (DM) and Combat Initiator reliably return participant lists, but we lose fidelity translating that into `SceneInfo`, turn records, and combat sessions.
- `SceneInfo` tracks NPCs via string fields (`npcs_involved`, `npcs_present`, `npcs_added`, `npcs_removed`) that aren’t authoritative and drift from combat/turn data.
- Combat setup infers NPC information ad-hoc, leading to mismatched IDs, `is_player` flags, and turn types (e.g., Imperial Guards labeled as players).
- Character origination belongs to DM/Combat Initiator, persistence to `CharacterManager`, but we lack a dedicated layer that keeps the scene roster synchronized with campaign characters and combats.

## Goals
1. Establish a canonical participant roster for every scene, persisted as structured participants rather than string lists.
2. Ensure combat, turn, and narrative systems derive character presence from the same roster.
3. Introduce NPC profile management so narrative NPCs can graduate to full combatants without schema churn.
4. Provide validation contracts so systems assert required capabilities (combat stats, narrative metadata) before use.
5. Migrate existing scenes and maintain backward compatibility for incremental rollout.

## Architecture Overview
```
DM / Combat Initiator ──┐
                        ▼
                  CharacterManager (primary store)
                        │
                        ▼
                SceneRosterManager (new)
                ├── Scene participants
                ├── Roster deltas (join/leave)
                └── Capability validation contracts
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    Combat / Turn systems      Narrative agents
```

## Planned Work Items

### 1. Core Models & Capability Contracts
- Create `CharacterRole` enum (`player`, `npc_combatant`, `npc_support`, `summon`, …) and `CharacterCapabilities` bitset/flags.
- Add `character_role` and `capabilities` to `CharacterInfo`, ensuring serialization handles defaults.
- Introduce `SceneParticipant` dataclass capturing `character_id`, display label, `CharacterRole`, presence status, capability flags, and join/leave timestamps.
- Provide helper functions in `backend/src/core/session/scene/validation.py` for capability assertions (`require_capability`, `has_capability`).
- Update `SceneInfo` to store `participants: List[SceneParticipant]`; keep legacy `pcs_present`/`npcs_present` as derived properties for existing consumers.

### 2. Scene Roster Manager
- Add `SceneRosterManager` under `backend/src/core/session/scene/scene_roster_manager.py` to:
  - Reconcile DM/agent `characters` payloads with `CharacterManager` entries.
  - Maintain participant lifecycle (join/leave) and emit diffs for persistence.
  - Offer lookup APIs (`get_combat_participants`, `lookup_role`, `sync_from_turn`).
- Refactor `SceneIntegration` to own a roster manager instance per campaign, delegating all participant logic to it.
- Simplify `SceneUpdater`: focus on narrative/objective fields; call roster manager for participant changes.
- Update `EnhancedSceneManager` summaries to expose `participants` plus derived arrays.

### 3. Character Pipeline Enhancements
- Introduce `NpcProfile` dataclass (id, display name, role tag, relationships, notes, `has_full_sheet`).
- Implement `NpcUpdater` (`backend/src/core/character/npc_updater.py`) to parse DM structured responses, update `NpcProfile`, and escalate to full `CharacterInfo` when needed.
- Adjust persistence hooks so both character and NPC updates route through `NpcUpdater`, then notify `SceneRosterManager`.
- Scaffold `NPCCombatantCreator` (`backend/src/core/combat/npc_combatant_creator.py`) with methods for creating/upgrading NPC combatants using roster information and template stats.

### 4. Combat & Turn Alignment
- Modify `CharacterSetupManager` to:
  - Pull combat-ready participants from `SceneRosterManager`.
  - Use `NPCCombatantCreator` for NPC stat generation instead of inline logic.
- Update combat orchestration (`combat_state_manager.py`, `combat_orchestrator.py`) to set `is_player`/`is_npc` based on `CharacterRole`.
- Enhance `TurnManager._infer_turn_type` to consult `SceneRosterManager` for authoritative roles before fallback heuristics.
- Ensure `smart_router.py` and other agents filter/action on participants via roster data.

### 5. Migration, Testing, Documentation
- Write migration script to convert existing scenes to the new participant model while preserving legacy lists for consumers.
- Add unit tests for:
  - `SceneRosterManager` (join/leave, capability validation).
  - `NpcUpdater`/`NpcProfile` lifecycle.
  - `NPCCombatantCreator` generation rules.
- Expand integration tests (e.g., `test_dungeon_master_scene_flow.py`, campaign 72 fixtures) to assert consistent participant roles across scene, combat, and turn.
- Document the new ownership pipeline in `backend/docs/character-tracking` (or update existing docs) and note migration steps.

## Rollout Strategy
1. Implement model changes with backward-compatible serialization; gate new roster manager behind feature flag/config.
2. Ship `SceneRosterManager` and `NpcUpdater` while preserving legacy fields; run migration in staging with snapshots.
3. Update combat/turn systems to consume roster data once validation passes.
4. Remove deprecated `npcs_*` fields after verifying no call sites depend on them.

## Validation & Testing Roadmap
- Add unit tests for `SceneRosterManager`, `NpcUpdater`, and `NPCCombatantCreator` covering join/leave deltas, profile promotion, and combatant overrides.
- Extend combat integration tests (campaign 72 fixture) to assert that roster roles drive `is_player`/`is_npc` flags and turn typing.
- Add a regression suite verifying that legacy scenes without participants are auto-upgraded via the roster manager when loaded.
- Exercise the new `scripts/report_scene_roster_status.py` utility as part of pre-release checks to ensure campaigns have been touched by the new pipeline.

## Migration Notes
- Historical scenes do not require an offline migration. When loaded, `SceneInfo.from_dict` and the roster manager seed `participants` from the legacy `pcs_present` / `npcs_present` arrays.
- The reporting script (`python scripts/report_scene_roster_status.py`) highlights any scenes still missing participants so they can be opened in the current campaign flow to trigger seeding.
- Campaign continuation: existing campaigns can proceed without interruption; once a DM turn processes under the new code, rosters are persisted alongside the legacy lists for backwards compatibility.

## Open Questions
- How should we version scene files to indicate participant-aware schema? (Likely embed `_metadata.version` bump.)
- Do we need per-scene overrides for NPC hostility/faction beyond `CharacterInfo` defaults?
- Should capability validation raise hard errors or log warnings in production when data is missing?

## Next Steps
1. Confirm `CharacterRole` values and capability bitset with stakeholders.
2. Prototype `SceneParticipant` + `SceneRosterManager` to expose dependencies early.
3. Iterate on migration script with a small campaign (e.g., campaign 72) before full rollout.
