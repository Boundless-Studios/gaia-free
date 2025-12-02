# Proposal: Correct Character Tracking, Turn Actor Semantics, and Scene Rosters

Status: Draft

Owner: Gameplay/Backend

Summary: Fix turn actor semantics and establish a minimal, reliable character and scene roster pipeline that feeds CombatInitiator and future combat agents. No new complex models; focus on correctness and deterministic updates.

## Goals

- Use `Turn.character_id` to encode the acting entity type and identity: `dm`, `npc:<slug>`, or `pc:<character_id>`.
- Use `Turn.character_name` as a display-only, human-readable name.
- Track which characters are present in each scene (PCs and NPCs) and persist this with scenes.
- Build `CombatantInfo` from canonical character data (CharacterManager), filtered by the scene roster.
- Deterministically update persisted characters after each agent completes.

## Scope (minimal, low-risk)

- No wholesale character model redesign.
- No enforcement of all rules; only ensure presence, identity, and basic stats for combat.
- Backward-compatible with existing saved turns (`player_id` legacy).

---

## Immediate Fixes

1) Turn actor semantics

- Replace hardcoded `character_id="player_main"` and `character_name="user"` with a resolver that maps to:
  - `dm` for narrator turns
  - `npc:<slug>` for NPC/creature turns
  - `pc:<character_id>` for player character turns
- Keep `character_name` as display-only (e.g., “Dungeon Master”, “Goblin Scout”, “Elara”).

Implementation touchpoint:

- `backend/src/core/session/campaign_runner.py:361` (create new turn)
  - Add `_resolve_acting_character(user_input, campaign_id) -> tuple[str, str]` that returns `(character_id, character_name)`.
  - Strategy:
    - If a single PC exists, default to that PC.
    - If multiple PCs, prefer the one named in `user_input`; else the first PC.
    - For narrator-only flows we explicitly create, use `dm`.
    - For NPC-initiated actions, set `npc:<slug>` and NPC display name.

2) Field naming alignment

- Continue using `character_name` (not `player_id`).
- Backward compat already exists in `Turn.from_dict` mapping `player_id` → `character_name`.
  - `backend/src/core/models/turn.py` (legacy mapping preserved)

3) Turn type inference

- Confirmed behavior in `TurnManager._infer_turn_type`:
  - `dm` → `TurnType.NARRATIVE`
  - `npc...` → `TurnType.NPC`
  - everything else (e.g., `pc:<id>`) → `TurnType.PLAYER`
- Optionally document the `pc:`/`npc:` conventions in the method docstring.

---

## Scene Roster (Present Characters)

Add explicit per-scene roster so we know who is present.

1) Add PCs present to `SceneInfo`

- Extend `SceneInfo` with `pcs_present: List[str]` alongside existing `npcs_involved`.
- Update `to_dict`/`from_dict` to persist `pcs_present`.
- In `SceneUpdater.create_from_analysis(...)`, add `_extract_pcs(...) -> List[str]` (heuristic from analysis + fallback to CharacterManager PCs) and set `scene_info.pcs_present` accordingly.

Files to touch:

- `backend/src/core/models/scene_info.py`
- `backend/src/core/session/scene/scene_updater.py`

2) Provide roster in turn context

- `SceneIntegration.get_turn_scene_context(...)` should include both:
  - `'pcs': current_scene.get("pcs_present", [])`
  - `'npcs': current_scene.get("npcs_present", [])` (already present as `npcs_present` in scene summaries)

File to touch:

- `backend/src/core/session/scene/scene_integration.py`

3) Carry forward roster between scenes

- On transition (`SceneIntegration.process_scene_transition(...)`), seed `pcs_present` for the new scene with the previous scene’s `pcs_present`; adjust with analysis deltas if available.
- If unclear, default to all PCs from `CharacterManager`.

---

## CombatantInfo: Deterministic Combatant Construction

Build `CombatantInfo` from canonical character data (not ad-hoc analysis snippets).

- In `_build_combat_initiation_request(...)`, source PCs from `CharacterManager.get_player_characters()`.
- If `pcs_present` exists in scene context, filter to those PCs; otherwise include all PCs.
- Map fields to `CombatantInfo`:
  - `name`, `type="player"`, `class_or_creature`, `level`, `hp_current`, `hp_max`, `armor_class`, `initiative_bonus`.
- Continue to include NPCs/enemies, preferring the scene’s `npcs_present` when available.

File to touch:

- `backend/src/core/agent_orchestration/smart_router.py`

---

## Deterministic Character Updates After Each Turn

Short-term deterministic sink that updates persisted character state without adding a new complex agent.

1) Direct update via CharacterManager

- Right after `structured_data` is finalized and before completing the turn:
  - If `self.character_manager` and `structured_data.get("characters")` exist:
    - Call `self.character_manager.update_character_from_dm(structured_data)`
    - Then `self.character_manager.persist_characters()`

File to touch:

- `backend/src/core/session/campaign_runner.py` (near where `turn_info` is added)

2) Optional: narrow “CharacterUpdateAgent” pass (future improvement)

- Wrap the existing `character_updater` tool in a small agent to process the final `structured_data` and emit tool calls for robust updates.
- You already register persistence hooks (`register_tool_hooks`) that will save updates; run this agent at the end of `run_turn` asynchronously.

---

## Routing Integration (analysis_context)

Ensure the router can always build a valid combat request.

- Inject reliable lists into `analysis_context` before routing decisions:
  - `analysis_context["players"] = [...]` built from `CharacterManager` (filtered by `pcs_present` if available)
  - `analysis_context["npcs"] = [...]` from current scene summary (`npcs_present`), optionally enriched if we have NPC models

File to touch:

- `backend/src/core/agent_orchestration/smart_router.py` (right after building `analysis_context` in `analyze_and_route`)

---

## Persistence and Compatibility

- Characters remain persisted via `CharacterManager.persist_characters()` in `campaign_storage/.../characters`.
- Scene rosters persist in `data/scenes/*.json` via `EnhancedSceneManager`.
- `Turn.from_dict` continues to map legacy `player_id` → `character_name` for backward compatibility. New code should not emit `player_id`.

---

## Minimal Code Changes (surgical)

1) `backend/src/core/session/campaign_runner.py`

- Add `_resolve_acting_character(user_input, campaign_id)` and replace the hardcoded `character_id`/`character_name` at turn creation.
- After `structured_data` is created, invoke `CharacterManager.update_character_from_dm()` + `persist_characters()` if available.

2) `backend/src/core/models/scene_info.py`

- Add `pcs_present: List[str]`.
- Update `to_dict`/`from_dict` to include it.

3) `backend/src/core/session/scene/scene_updater.py`

- Add `_extract_pcs(...)` and set `scene_info.pcs_present` in `create_from_analysis(...)`.

4) `backend/src/core/session/scene/scene_integration.py`

- Include `'pcs'` in `get_turn_scene_context(...)` output; seed `pcs_present` on transitions.

5) `backend/src/core/agent_orchestration/smart_router.py`

- Populate `analysis_context["players"]` from `CharacterManager` and filter by `pcs_present` when available.
- Build `CombatantInfo` for PCs from CharacterManager data.

6) `backend/src/core/session/turn_manager.py` (doc-only)

- Document `character_id` conventions (`dm`, `npc:<slug>`, `pc:<character_id>`). Logic already aligns.

---

## Data Contracts to Standardize

- `Turn.character_id`: one of `dm`, `npc:<slug>`, `pc:<character_id>`
- `Turn.character_name`: display name of actor
- `SceneInfo.pcs_present`: list of PC `character_id` values present
- `analysis_context.players`: list of PC dicts suitable for `CombatantInfo` mapping
- `structured_data.characters`: dict or text; if dict, keys map to characters with fields for HP/status/effects; consumed by CharacterManager

---

## Risks / Assumptions

- Heuristics: `_resolve_acting_character` may mis-pick when multiple PCs are present and the input is ambiguous. Acceptable short-term; can be improved by explicit UI selection or per-turn memory of last actor.
- NPC metadata: We may not always have full NPC stats; `CombatantInfo` for NPCs can start minimal (name, type, hostile) and be enriched by agents.
- Backfill: Existing scenes lack `pcs_present`. On first update, we can default to all PCs or infer from recent history.

---

## Rollout Plan

1) Implement field and resolver changes behind small helpers (no API changes).
2) Add `pcs_present` field and start populating it on new scenes; don’t migrate old scenes initially.
3) Switch `CombatInitiation` building to CharacterManager-derived PCs.
4) Add deterministic character update call in `run_turn`.
5) Smoke-test with an existing campaign:
   - Ensure turn actor fields look correct in saved `turns/*.json`.
   - Confirm scene files now include `pcs_present`.
   - Trigger combat and verify `CombatantInfo` includes correct PCs and stats.

---

## Testing Plan

- Unit tests:
  - `Turn.from_dict` continues to map legacy `player_id` → `character_name`.
  - `_infer_turn_type` returns expected values for `dm`, `npc:*`, `pc:*`.
  - New `_resolve_acting_character` returns a valid `(character_id, character_name)` for single-PC, multi-PC (with and without name in input), and narrator cases.
- Integration tests:
  - Run a short campaign flow to produce a scene; assert `pcs_present` exists in `data/scenes/*.json`.
  - Trigger combat; assert `CombatantInfo` PCs match `pcs_present` and reflect CharacterManager stats.
  - Verify `CharacterManager.persist_characters()` updates files after a turn with `structured_data.characters`.

---

## File References (for implementation)

- Turn creation (replace hardcoded actor):
  - `backend/src/core/session/campaign_runner.py:361`
- Turn backward compatibility:
  - `backend/src/core/models/turn.py:137`
- Turn type inference:
  - `backend/src/core/session/turn_manager.py:82`
- Scene model:
  - `backend/src/core/models/scene_info.py`
- Scene creation/update:
  - `backend/src/core/session/scene/scene_updater.py`
- Scene assembly and context:
  - `backend/src/core/session/scene/scene_integration.py`
- Router and combat request:
  - `backend/src/core/agent_orchestration/smart_router.py`
- Character management:
  - `backend/src/core/character/character_manager.py`

---

## Next Steps

- If approved, I can open a small PR series implementing the above in 4–5 focused commits:
  1) Turn actor resolver + field fixes
  2) `SceneInfo.pcs_present` + scene updater/integration
  3) Router players injection + `CombatantInfo` from CharacterManager
  4) Deterministic character update in `run_turn`
  5) Tests and small docstrings

