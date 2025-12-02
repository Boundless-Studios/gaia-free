# Gaia Backend Reorganization Migration Plan

## Overview

This document provides a step-by-step plan to reorganize the Gaia backend codebase for clean public/private separation and eventual open-source extraction.

**Goal**: Restructure from `src/` to `gaia/` (public) and `gaia_private/` (private subtree)

**Estimated Effort**: 4-6 hours of focused work

---

## Current vs Target Structure

```
CURRENT                              TARGET
─────────────────────────────────    ─────────────────────────────────
src/                                 gaia/                    [PUBLIC]
├── api/                             ├── api/
├── connection/                      ├── connection/
├── core/                            ├── infra/
│   ├── agent_orchestration/  →      │   ├── audio/
│   ├── agents/               →      │   ├── image/
│   ├── audio/                       │   ├── llm/
│   ├── campaign/                    │   └── storage/
│   ├── character/                   ├── models/
│   ├── combat/                      ├── mechanics/
│   ├── config/                      │   ├── combat/
│   ├── image/                       │   ├── character/
│   ├── llm/                         │   └── campaign/
│   ├── models/                      ├── engine/
│   ├── prompts/              →      ├── config/
│   ├── session/              →      ├── services/
│   ├── storage/                     └── utils/
│   └── utils/
├── engine/                          gaia_private/            [PRIVATE]
├── game/                     →      ├── agents/
├── prompts/                  →      │   ├── dungeon_master/
├── services/                        │   ├── combat/
└── utils/                           │   ├── scene/
                                     │   └── tools/
                                     ├── orchestration/
                                     ├── session/
                                     ├── extraction/
                                     └── prompts/
```

---

## Pre-Migration Checklist

- [ ] Ensure all tests pass: `python3 gaia_launcher.py test`
- [ ] Commit all current changes
- [ ] Create migration branch: `git checkout -b refactor/reorganize-for-extraction`
- [ ] Backup current structure: `cp -r backend/src backend/src_backup`

---

## Phase 1: Create Directory Structure

**Objective**: Create the new directory tree without moving files

### Commands

```bash
cd /home/user/Gaia/backend

# Create public package structure
mkdir -p src/gaia/api/routes
mkdir -p src/gaia/api/schemas
mkdir -p src/gaia/api/middleware
mkdir -p src/gaia/connection/websocket
mkdir -p src/gaia/connection/models
mkdir -p src/gaia/infra/audio/providers
mkdir -p src/gaia/infra/audio/models
mkdir -p src/gaia/infra/image/providers
mkdir -p src/gaia/infra/llm/providers
mkdir -p src/gaia/infra/storage
mkdir -p src/gaia/models/combat/mechanics
mkdir -p src/gaia/models/combat/persistence
mkdir -p src/gaia/models/character
mkdir -p src/gaia/mechanics/combat
mkdir -p src/gaia/mechanics/character
mkdir -p src/gaia/mechanics/campaign
mkdir -p src/gaia/engine
mkdir -p src/gaia/config
mkdir -p src/gaia/services/email
mkdir -p src/gaia/utils

# Create private package structure
mkdir -p src/gaia_private/agents/dungeon_master
mkdir -p src/gaia_private/agents/combat
mkdir -p src/gaia_private/agents/scene
mkdir -p src/gaia_private/agents/scene_analyzer
mkdir -p src/gaia_private/agents/tools/combat
mkdir -p src/gaia_private/agents/tools/formatters
mkdir -p src/gaia_private/orchestration
mkdir -p src/gaia_private/session/combat
mkdir -p src/gaia_private/session/scene
mkdir -p src/gaia_private/extraction
mkdir -p src/gaia_private/prompts

# Create __init__.py files
find src/gaia src/gaia_private -type d -exec touch {}/__init__.py \;
```

### Verification
```bash
tree src/gaia -d
tree src/gaia_private -d
```

---

## Phase 2: Move Files - PUBLIC Package (gaia/)

**Objective**: Move public infrastructure and mechanics files

### 2.1 API Layer

| Source | Destination |
|--------|-------------|
| `src/api/main.py` | `src/gaia/api/app.py` |
| `src/api/routes/*.py` | `src/gaia/api/routes/` |
| `src/api/schemas/*.py` | `src/gaia/api/schemas/` |
| `src/api/guards/*.py` | `src/gaia/api/middleware/` |
| `src/api/response_builder.py` | `src/gaia/api/` |
| `src/api/response_parser.py` | `src/gaia/api/` |
| `src/api/admin_endpoints.py` | `src/gaia/api/routes/admin.py` |
| `src/api/auth0_endpoints.py` | `src/gaia/api/routes/auth.py` |
| `src/api/campaign_generation.py` | `src/gaia/api/routes/campaign_generation.py` |
| `src/api/campaign_service.py` | `src/gaia/api/routes/campaigns.py` |
| `src/api/combat_routes.py` | `src/gaia/api/routes/combat.py` |
| `src/api/registration_endpoints.py` | `src/gaia/api/routes/registration.py` |
| `src/api/prompts_endpoints.py` | `src/gaia/api/routes/prompts.py` |
| `src/api/internal_endpoints.py` | `src/gaia/api/routes/internal.py` |
| `src/api/arena_setup.py` | `src/gaia/api/routes/arena.py` |

```bash
# API moves
git mv src/api/main.py src/gaia/api/app.py
git mv src/api/routes/chat.py src/gaia/api/routes/chat.py
git mv src/api/routes/debug.py src/gaia/api/routes/debug.py
git mv src/api/routes/room.py src/gaia/api/routes/room.py
git mv src/api/schemas/campaign.py src/gaia/api/schemas/campaign.py
git mv src/api/schemas/chat.py src/gaia/api/schemas/chat.py
git mv src/api/schemas/session.py src/gaia/api/schemas/session.py
git mv src/api/guards/room_access.py src/gaia/api/middleware/room_access.py
git mv src/api/response_builder.py src/gaia/api/response_builder.py
git mv src/api/response_parser.py src/gaia/api/response_parser.py
git mv src/api/admin_endpoints.py src/gaia/api/routes/admin.py
git mv src/api/auth0_endpoints.py src/gaia/api/routes/auth.py
git mv src/api/campaign_generation.py src/gaia/api/routes/campaign_generation.py
git mv src/api/campaign_service.py src/gaia/api/routes/campaigns.py
git mv src/api/combat_routes.py src/gaia/api/routes/combat.py
git mv src/api/registration_endpoints.py src/gaia/api/routes/registration.py
git mv src/api/prompts_endpoints.py src/gaia/api/routes/prompts.py
git mv src/api/internal_endpoints.py src/gaia/api/routes/internal.py
git mv src/api/arena_setup.py src/gaia/api/routes/arena.py
```

### 2.2 Connection Layer

| Source | Destination |
|--------|-------------|
| `src/connection/*.py` | `src/gaia/connection/` |
| `src/connection/websocket/*.py` | `src/gaia/connection/websocket/` |
| `src/connection/models/*.py` | `src/gaia/connection/models/` |
| `src/connection/cleanup/*.py` | `src/gaia/connection/cleanup/` |

```bash
# Connection moves
git mv src/connection/connection_playback_tracker.py src/gaia/connection/
git mv src/connection/connection_registry.py src/gaia/connection/
git mv src/connection/ws_helpers.py src/gaia/connection/
git mv src/connection/models/connection_playback_state.py src/gaia/connection/models/
git mv src/connection/models/connection_status.py src/gaia/connection/models/
git mv src/connection/models/websocket_connection.py src/gaia/connection/models/
git mv src/connection/websocket/audio_websocket_handler.py src/gaia/connection/websocket/
git mv src/connection/websocket/campaign_broadcaster.py src/gaia/connection/websocket/
git mv src/connection/websocket/collaborative src/gaia/connection/websocket/
git mv src/connection/cleanup src/gaia/connection/
```

### 2.3 Infrastructure - Audio

| Source | Destination |
|--------|-------------|
| `src/core/audio/*.py` (except models/) | `src/gaia/infra/audio/` |
| `src/core/audio/models/*.py` | `src/gaia/infra/audio/models/` |

```bash
# Audio infrastructure
git mv src/core/audio/audio_artifact_store.py src/gaia/infra/audio/
git mv src/core/audio/audio_models.py src/gaia/infra/audio/
git mv src/core/audio/audio_playback_service.py src/gaia/infra/audio/
git mv src/core/audio/audio_queue_manager.py src/gaia/infra/audio/
git mv src/core/audio/auto_tts_service.py src/gaia/infra/audio/
git mv src/core/audio/chunking_manager.py src/gaia/infra/audio/
git mv src/core/audio/f5_tts_config.py src/gaia/infra/audio/
git mv src/core/audio/playback_request_writer.py src/gaia/infra/audio/
git mv src/core/audio/provider_manager.py src/gaia/infra/audio/
git mv src/core/audio/streaming_audio_buffer.py src/gaia/infra/audio/
git mv src/core/audio/tts_service.py src/gaia/infra/audio/
git mv src/core/audio/voice_and_tts_config.py src/gaia/infra/audio/
git mv src/core/audio/voice_registry.py src/gaia/infra/audio/
git mv src/core/audio/webm_decoder.py src/gaia/infra/audio/
git mv src/core/audio/models/audio_chunk.py src/gaia/infra/audio/models/
git mv src/core/audio/models/audio_playback_request.py src/gaia/infra/audio/models/
git mv src/core/audio/models/playback_status.py src/gaia/infra/audio/models/
git mv src/core/audio/models/user_audio_queue.py src/gaia/infra/audio/models/
```

### 2.4 Infrastructure - Image

| Source | Destination |
|--------|-------------|
| `src/core/image/*.py` | `src/gaia/infra/image/` |

```bash
# Image infrastructure
git mv src/core/image/flux_local_image_service.py src/gaia/infra/image/providers/flux.py
git mv src/core/image/gemini_image_service.py src/gaia/infra/image/providers/gemini.py
git mv src/core/image/parasail_batch_image_service.py src/gaia/infra/image/providers/parasail_batch.py
git mv src/core/image/parasail_image_service.py src/gaia/infra/image/providers/parasail.py
git mv src/core/image/runware_image_service.py src/gaia/infra/image/providers/runware.py
git mv src/core/image/image_artifact_store.py src/gaia/infra/image/
git mv src/core/image/image_config.py src/gaia/infra/image/
git mv src/core/image/image_metadata.py src/gaia/infra/image/
git mv src/core/image/image_provider.py src/gaia/infra/image/
git mv src/core/image/image_service_manager.py src/gaia/infra/image/
```

### 2.5 Infrastructure - LLM

| Source | Destination |
|--------|-------------|
| `src/core/llm/*.py` | `src/gaia/infra/llm/` |

```bash
# LLM infrastructure
git mv src/core/llm/model_providers.py src/gaia/infra/llm/providers/
git mv src/core/llm/ollama_manager.py src/gaia/infra/llm/providers/ollama.py
git mv src/core/llm/agent_runner.py src/gaia/infra/llm/
git mv src/core/llm/model_manager.py src/gaia/infra/llm/
git mv src/core/llm/streaming_llm_client.py src/gaia/infra/llm/
```

### 2.6 Infrastructure - Storage

| Source | Destination |
|--------|-------------|
| `src/core/storage/*.py` | `src/gaia/infra/storage/` |

```bash
# Storage infrastructure
git mv src/core/storage/campaign_object_store.py src/gaia/infra/storage/
git mv src/core/storage/campaign_store.py src/gaia/infra/storage/
```

### 2.7 Models (Consolidated)

| Source | Destination |
|--------|-------------|
| `src/core/models/*.py` | `src/gaia/models/` |
| `src/core/models/combat/**/*.py` | `src/gaia/models/combat/` |
| `src/core/character/models/*.py` | `src/gaia/models/character/` |

```bash
# Core models
git mv src/core/models/campaign.py src/gaia/models/
git mv src/core/models/combat.py src/gaia/models/
git mv src/core/models/environment.py src/gaia/models/
git mv src/core/models/game_enums.py src/gaia/models/
git mv src/core/models/item.py src/gaia/models/
git mv src/core/models/narrative.py src/gaia/models/
git mv src/core/models/npc.py src/gaia/models/
git mv src/core/models/quest.py src/gaia/models/
git mv src/core/models/scene_info.py src/gaia/models/
git mv src/core/models/scene_participant.py src/gaia/models/
git mv src/core/models/turn.py src/gaia/models/

# Combat models - mechanics (public)
git mv src/core/models/combat/mechanics src/gaia/models/combat/

# Combat models - persistence (public)
git mv src/core/models/combat/persistence src/gaia/models/combat/

# Character models
git mv src/core/character/models/ability.py src/gaia/models/character/
git mv src/core/character/models/character_info.py src/gaia/models/character/
git mv src/core/character/models/character_profile.py src/gaia/models/character/
git mv src/core/character/models/character_setup.py src/gaia/models/character/
git mv src/core/character/models/enriched_character.py src/gaia/models/character/
git mv src/core/character/models/enums.py src/gaia/models/character/
git mv src/core/character/models/npc_profile.py src/gaia/models/character/
```

### 2.8 Mechanics - Combat (Public, non-AI)

| Source | Destination |
|--------|-------------|
| `src/core/combat/*.py` | `src/gaia/mechanics/combat/` |
| `src/core/session/combat/*.py` (mechanics only) | `src/gaia/mechanics/combat/` |

```bash
# Combat mechanics (formatting, setup, logging - NOT agents)
git mv src/core/combat/character_setup.py src/gaia/mechanics/combat/
git mv src/core/combat/combat_formatter.py src/gaia/mechanics/combat/
git mv src/core/combat/combat_logger.py src/gaia/mechanics/combat/
git mv src/core/combat/hostile_extraction.py src/gaia/mechanics/combat/
git mv src/core/combat/npc_combatant_creator.py src/gaia/mechanics/combat/

# Combat engine (state machine, HP, validation - NOT AI decision making)
git mv src/core/session/combat/action_validator.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_action_results.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_engine.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_event_log.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_json_encoder.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_logger.py src/gaia/mechanics/combat/combat_session_logger.py
git mv src/core/session/combat/combat_mechanics_structs.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_persistence.py src/gaia/mechanics/combat/
git mv src/core/session/combat/combat_state_manager.py src/gaia/mechanics/combat/
git mv src/core/session/combat/hp_manager.py src/gaia/mechanics/combat/
```

### 2.9 Mechanics - Character (Public, non-AI)

| Source | Destination |
|--------|-------------|
| `src/core/character/*.py` (except extraction/) | `src/gaia/mechanics/character/` |

```bash
# Character mechanics (NOT extraction which is AI)
git mv src/core/character/character_formatter.py src/gaia/mechanics/character/
git mv src/core/character/character_info_generator.py src/gaia/mechanics/character/
git mv src/core/character/character_manager.py src/gaia/mechanics/character/
git mv src/core/character/character_storage.py src/gaia/mechanics/character/
git mv src/core/character/character_translator.py src/gaia/mechanics/character/
git mv src/core/character/character_updater.py src/gaia/mechanics/character/
git mv src/core/character/id_utils.py src/gaia/mechanics/character/
git mv src/core/character/npc_profile_storage.py src/gaia/mechanics/character/
git mv src/core/character/npc_updater.py src/gaia/mechanics/character/
git mv src/core/character/portrait_generator.py src/gaia/mechanics/character/
git mv src/core/character/presence_formatter.py src/gaia/mechanics/character/
git mv src/core/character/profile_manager.py src/gaia/mechanics/character/
git mv src/core/character/profile_storage.py src/gaia/mechanics/character/
git mv src/core/character/profile_updater.py src/gaia/mechanics/character/
git mv src/core/character/utils.py src/gaia/mechanics/character/
git mv src/core/character/voice_pool.py src/gaia/mechanics/character/
```

### 2.10 Mechanics - Campaign (Public)

| Source | Destination |
|--------|-------------|
| `src/core/campaign/*.py` | `src/gaia/mechanics/campaign/` |

```bash
# Campaign mechanics
git mv src/core/campaign/campaign_summarizer.py src/gaia/mechanics/campaign/
git mv src/core/campaign/simple_campaign_manager.py src/gaia/mechanics/campaign/
```

### 2.11 Engine (Public)

| Source | Destination |
|--------|-------------|
| `src/engine/*.py` | `src/gaia/engine/` |

```bash
# Engine
git mv src/engine/dm_context.py src/gaia/engine/
git mv src/engine/game_configuration.py src/gaia/engine/
git mv src/engine/response_handler.py src/gaia/engine/
git mv src/engine/scene_manager.py src/gaia/engine/
```

### 2.12 Config, Services, Utils (Public)

```bash
# Config
git mv src/core/config/secrets.py src/gaia/config/

# Services
git mv src/services/email src/gaia/services/

# Utils
git mv src/utils/audio_utils.py src/gaia/utils/
git mv src/utils/dice.py src/gaia/utils/
git mv src/utils/dice_results.py src/gaia/utils/
git mv src/utils/google_auth_helpers.py src/gaia/utils/
git mv src/utils/json_utils.py src/gaia/utils/
git mv src/utils/logging_utils.py src/gaia/utils/
git mv src/utils/windows_audio_utils.py src/gaia/utils/
git mv src/core/utils/json_sanitizer.py src/gaia/utils/
git mv src/core/utils/singleton.py src/gaia/utils/
```

---

## Phase 3: Move Files - PRIVATE Package (gaia_private/)

**Objective**: Move AI agents, orchestration, session management, and prompts

### 3.1 Agents - Dungeon Master

| Source | Destination |
|--------|-------------|
| `src/game/dnd_agents/dungeon_master.py` | `src/gaia_private/agents/dungeon_master/agent.py` |
| `src/game/dnd_agents/streaming_dungeon_master.py` | `src/gaia_private/agents/dungeon_master/streaming.py` |
| `src/game/dnd_agents/streaming_dm_orchestrator.py` | `src/gaia_private/agents/dungeon_master/orchestrator.py` |
| `src/game/dnd_agents/streaming_dm_prompts.py` | `src/gaia_private/agents/dungeon_master/prompts.py` |

```bash
git mv src/game/dnd_agents/dungeon_master.py src/gaia_private/agents/dungeon_master/agent.py
git mv src/game/dnd_agents/streaming_dungeon_master.py src/gaia_private/agents/dungeon_master/streaming.py
git mv src/game/dnd_agents/streaming_dm_orchestrator.py src/gaia_private/agents/dungeon_master/orchestrator.py
git mv src/game/dnd_agents/streaming_dm_prompts.py src/gaia_private/agents/dungeon_master/prompts.py
```

### 3.2 Agents - Combat (AI parts)

| Source | Destination |
|--------|-------------|
| `src/game/dnd_agents/combat/*.py` | `src/gaia_private/agents/combat/` |
| `src/game/dnd_agents/combat_initiator.py` | `src/gaia_private/agents/combat/initiator.py` |

```bash
git mv src/game/dnd_agents/combat/combat.py src/gaia_private/agents/combat/
git mv src/game/dnd_agents/combat/combat_action_selection_agent.py src/gaia_private/agents/combat/action_selector.py
git mv src/game/dnd_agents/combat/combat_agent_models.py src/gaia_private/agents/combat/models.py
git mv src/game/dnd_agents/combat/combat_narrative_agent.py src/gaia_private/agents/combat/narrator.py
git mv src/game/dnd_agents/combat/combat_run_result.py src/gaia_private/agents/combat/run_result.py
git mv src/game/dnd_agents/combat_initiator.py src/gaia_private/agents/combat/initiator.py
```

### 3.3 Agents - Scene

| Source | Destination |
|--------|-------------|
| `src/game/scene_agents/*.py` | `src/gaia_private/agents/scene/` |
| `src/game/scene_agents/prompts/*.py` | `src/gaia_private/agents/scene/prompts/` |
| `src/game/scene_agents/tools/*.py` | `src/gaia_private/agents/scene/tools/` |

```bash
git mv src/game/scene_agents/action_resolver.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/base_scene_agent.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/character_extractor_agent.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/dialog_agent.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/exploration_agent.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/player_options_agent.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/scene_agent_runner.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/scene_describer.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/streaming_types.py src/gaia_private/agents/scene/
git mv src/game/scene_agents/prompts src/gaia_private/agents/scene/
git mv src/game/scene_agents/tools src/gaia_private/agents/scene/
```

### 3.4 Agents - Scene Analyzers

| Source | Destination |
|--------|-------------|
| `src/game/scene_analyzer_agents/*.py` | `src/gaia_private/agents/scene_analyzer/` |

```bash
git mv src/game/scene_analyzer_agents/base_analyzer.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/combat_exit_analyzer.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/complexity_analyzer.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/generic_output_tool.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/next_agent_recommender.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/parallel_scene_analyzer.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/scene_categorizer.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/special_considerations.py src/gaia_private/agents/scene_analyzer/
git mv src/game/scene_analyzer_agents/tool_selector.py src/gaia_private/agents/scene_analyzer/
```

### 3.5 Agents - Other DND Agents

| Source | Destination |
|--------|-------------|
| `src/game/dnd_agents/*.py` (remaining) | `src/gaia_private/agents/` |

```bash
git mv src/game/dnd_agents/campaign_generator.py src/gaia_private/agents/
git mv src/game/dnd_agents/campaign_persistence_agent.py src/gaia_private/agents/
git mv src/game/dnd_agents/character_generator.py src/gaia_private/agents/
git mv src/game/dnd_agents/image_generator.py src/gaia_private/agents/
git mv src/game/dnd_agents/scenario_analyzer.py src/gaia_private/agents/
git mv src/game/dnd_agents/scene_creator.py src/gaia_private/agents/
git mv src/game/dnd_agents/summarizer.py src/gaia_private/agents/
```

### 3.6 Agents - Tools

| Source | Destination |
|--------|-------------|
| `src/game/dnd_agents/tools/*.py` | `src/gaia_private/agents/tools/` |

```bash
git mv src/game/dnd_agents/tools/combat src/gaia_private/agents/tools/
git mv src/game/dnd_agents/tools/formatters src/gaia_private/agents/tools/
git mv src/game/dnd_agents/tools/persistence_hooks.py src/gaia_private/agents/tools/
```

### 3.7 Orchestration

| Source | Destination |
|--------|-------------|
| `src/core/agent_orchestration/*.py` | `src/gaia_private/orchestration/` |
| `src/core/agents/*.py` | `src/gaia_private/orchestration/agents/` |

```bash
git mv src/core/agent_orchestration/agent_types.py src/gaia_private/orchestration/
git mv src/core/agent_orchestration/combat_orchestrator.py src/gaia_private/orchestration/
git mv src/core/agent_orchestration/orchestrator.py src/gaia_private/orchestration/
git mv src/core/agent_orchestration/smart_router.py src/gaia_private/orchestration/

mkdir -p src/gaia_private/orchestration/agents
git mv src/core/agents/agent_as_tool.py src/gaia_private/orchestration/agents/
git mv src/core/agents/agent_config.py src/gaia_private/orchestration/agents/
git mv src/core/agents/agent_configurations.py src/gaia_private/orchestration/agents/
```

### 3.8 Session (Private)

| Source | Destination |
|--------|-------------|
| `src/core/session/*.py` | `src/gaia_private/session/` |
| `src/core/session/scene/*.py` | `src/gaia_private/session/scene/` |

```bash
# Session management
git mv src/core/session/campaign_data_extractor.py src/gaia_private/session/
git mv src/core/session/campaign_runner.py src/gaia_private/session/
git mv src/core/session/campaign_services.py src/gaia_private/session/
git mv src/core/session/campaign_state_manager.py src/gaia_private/session/
git mv src/core/session/compaction_manager.py src/gaia_private/session/
git mv src/core/session/context_manager.py src/gaia_private/session/
git mv src/core/session/history_manager.py src/gaia_private/session/
git mv src/core/session/logging_config.py src/gaia_private/session/
git mv src/core/session/room_service.py src/gaia_private/session/
git mv src/core/session/session_manager.py src/gaia_private/session/
git mv src/core/session/session_models.py src/gaia_private/session/
git mv src/core/session/session_registry.py src/gaia_private/session/
git mv src/core/session/session_storage.py src/gaia_private/session/
git mv src/core/session/streaming_dm_runner.py src/gaia_private/session/
git mv src/core/session/turn_manager.py src/gaia_private/session/

# Scene management
git mv src/core/session/scene/enhanced_scene_manager.py src/gaia_private/session/scene/
git mv src/core/session/scene/models.py src/gaia_private/session/scene/
git mv src/core/session/scene/objectives_extractor.py src/gaia_private/session/scene/
git mv src/core/session/scene/outcomes_extractor.py src/gaia_private/session/scene/
git mv src/core/session/scene/player_identifiers.py src/gaia_private/session/scene/
git mv src/core/session/scene/scene_integration.py src/gaia_private/session/scene/
git mv src/core/session/scene/scene_payloads.py src/gaia_private/session/scene/
git mv src/core/session/scene/scene_roster_manager.py src/gaia_private/session/scene/
git mv src/core/session/scene/scene_transition_detector.py src/gaia_private/session/scene/
git mv src/core/session/scene/scene_updater.py src/gaia_private/session/scene/
git mv src/core/session/scene/validation.py src/gaia_private/session/scene/
```

### 3.9 Character Extraction (AI)

| Source | Destination |
|--------|-------------|
| `src/core/character/extraction/*.py` | `src/gaia_private/extraction/` |

```bash
git mv src/core/character/extraction/character_descriptor.py src/gaia_private/extraction/
git mv src/core/character/extraction/character_extraction.py src/gaia_private/extraction/
git mv src/core/character/extraction/character_resolution.py src/gaia_private/extraction/
```

### 3.10 Prompts (All Private)

| Source | Destination |
|--------|-------------|
| `src/prompts/**/*.py` | `src/gaia_private/prompts/` |
| `src/core/prompts/*.py` | `src/gaia_private/prompts/` |

```bash
# Core prompts infrastructure
git mv src/core/prompts/migrate_prompts.py src/gaia_private/prompts/
git mv src/core/prompts/prompt_cache_mixin.py src/gaia_private/prompts/
git mv src/core/prompts/prompt_loader.py src/gaia_private/prompts/
git mv src/core/prompts/prompt_service.py src/gaia_private/prompts/
git mv src/core/prompts/models src/gaia_private/prompts/

# Standalone prompts module
git mv src/prompts/src/models.py src/gaia_private/prompts/prompt_models.py
```

### 3.11 Combat Agent IO Models (Private - AI interface)

| Source | Destination |
|--------|-------------|
| `src/core/models/combat/agent_io/**/*.py` | `src/gaia_private/models/combat/` |

```bash
mkdir -p src/gaia_private/models/combat
git mv src/core/models/combat/agent_io src/gaia_private/models/combat/
git mv src/core/models/combat/character src/gaia_private/models/combat/
git mv src/core/models/combat/orchestration src/gaia_private/models/combat/
```

---

## Phase 4: Update Imports

**Objective**: Update all import statements to reflect new paths

### 4.1 Create Import Mapping File

Create `scripts/migration/import_mappings.py`:

```python
IMPORT_MAPPINGS = {
    # API
    "from src.api.": "from gaia.api.",
    "from src.api import": "from gaia.api import",

    # Connection
    "from src.connection.": "from gaia.connection.",
    "from src.connection import": "from gaia.connection import",

    # Infrastructure
    "from src.core.audio.": "from gaia.infra.audio.",
    "from src.core.image.": "from gaia.infra.image.",
    "from src.core.llm.": "from gaia.infra.llm.",
    "from src.core.storage.": "from gaia.infra.storage.",

    # Models
    "from src.core.models.": "from gaia.models.",
    "from src.core.character.models.": "from gaia.models.character.",

    # Mechanics
    "from src.core.combat.": "from gaia.mechanics.combat.",
    "from src.core.character.": "from gaia.mechanics.character.",
    "from src.core.campaign.": "from gaia.mechanics.campaign.",
    "from src.core.session.combat.": "from gaia.mechanics.combat.",

    # Engine
    "from src.engine.": "from gaia.engine.",

    # Config
    "from src.core.config.": "from gaia.config.",

    # Utils
    "from src.utils.": "from gaia.utils.",
    "from src.core.utils.": "from gaia.utils.",

    # Services
    "from src.services.": "from gaia.services.",

    # PRIVATE - Agents
    "from src.game.dnd_agents.": "from gaia_private.agents.",
    "from src.game.scene_agents.": "from gaia_private.agents.scene.",
    "from src.game.scene_analyzer_agents.": "from gaia_private.agents.scene_analyzer.",

    # PRIVATE - Orchestration
    "from src.core.agent_orchestration.": "from gaia_private.orchestration.",
    "from src.core.agents.": "from gaia_private.orchestration.agents.",

    # PRIVATE - Session
    "from src.core.session.": "from gaia_private.session.",

    # PRIVATE - Extraction
    "from src.core.character.extraction.": "from gaia_private.extraction.",

    # PRIVATE - Prompts
    "from src.core.prompts.": "from gaia_private.prompts.",
    "from src.prompts.": "from gaia_private.prompts.",
}
```

### 4.2 Run Import Update Script

```bash
# Create the script
cat > scripts/migration/update_imports.py << 'EOF'
#!/usr/bin/env python3
import os
import re
from pathlib import Path

IMPORT_MAPPINGS = {
    # [paste mappings from above]
}

def update_file(filepath: Path) -> bool:
    """Update imports in a single file. Returns True if modified."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    for old, new in IMPORT_MAPPINGS.items():
        content = content.replace(old, new)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    backend = Path('/home/user/Gaia/backend/src')
    modified = []

    for pyfile in backend.rglob('*.py'):
        if update_file(pyfile):
            modified.append(pyfile)
            print(f"Updated: {pyfile}")

    print(f"\nModified {len(modified)} files")

if __name__ == '__main__':
    main()
EOF

python3 scripts/migration/update_imports.py
```

### 4.3 Manual Import Fixes

Some imports will need manual attention:

1. **Relative imports** within moved packages
2. **Circular imports** that may arise
3. **Dynamic imports** using `importlib`

```bash
# Find remaining old imports
grep -r "from src\." backend/src/gaia backend/src/gaia_private --include="*.py"
grep -r "import src\." backend/src/gaia backend/src/gaia_private --include="*.py"
```

---

## Phase 5: Update Entry Points

### 5.1 Update main.py

```python
# backend/src/main.py
from gaia.api.app import create_app

app = create_app()
```

### 5.2 Update Docker/Scripts

Update any references in:
- `docker-compose.yml`
- `Dockerfile`
- `gaia_launcher.py`
- `scripts/*.py`

---

## Phase 6: Testing

### 6.1 Verify Structure

```bash
# Check directory structure
tree backend/src/gaia -d
tree backend/src/gaia_private -d

# Check no files left in old locations
ls backend/src/core/
ls backend/src/game/
ls backend/src/api/
```

### 6.2 Run Tests

```bash
# Run all tests
python3 gaia_launcher.py test

# If tests fail, check import errors
python3 -c "from gaia.api.app import create_app; print('API OK')"
python3 -c "from gaia_private.session.campaign_runner import CampaignRunner; print('Session OK')"
```

### 6.3 Start Services

```bash
docker compose --profile dev up -d
docker logs -f gaia-backend-dev
```

---

## Phase 7: Clean Up

### 7.1 Remove Empty Directories

```bash
find backend/src -type d -empty -delete
```

### 7.2 Remove Old src/ Contents

```bash
# Only after verifying everything works
rm -rf backend/src/api
rm -rf backend/src/connection
rm -rf backend/src/core
rm -rf backend/src/engine
rm -rf backend/src/game
rm -rf backend/src/prompts
rm -rf backend/src/services
rm -rf backend/src/utils
```

### 7.3 Update .gitignore

Add if needed:
```
backend/src_backup/
```

---

## Phase 8: Prepare for Subtree Extraction

### 8.1 Verify Private Package Independence

```bash
# Ensure gaia_private only imports from gaia (not vice versa for core functionality)
grep -r "from gaia_private" backend/src/gaia --include="*.py"
# Should be minimal - only in places where private code is integrated
```

### 8.2 Create Private Repo

```bash
# On GitHub, create: boundless-studios/gaia-private

# Extract subtree
cd /home/user/Gaia
git subtree split --prefix=backend/src/gaia_private -b gaia-private-extract

# Push to new repo
git remote add gaia-private git@github.com:boundless-studios/gaia-private.git
git push gaia-private gaia-private-extract:main
```

### 8.3 Re-add as Subtree

```bash
# Remove the directory
rm -rf backend/src/gaia_private

# Re-add as subtree
git subtree add --prefix=backend/src/gaia_private \
    git@github.com:boundless-studios/gaia-private.git main --squash
```

---

## Post-Migration Verification Checklist

- [ ] All tests pass
- [ ] Backend starts without errors
- [ ] Frontend can communicate with backend
- [ ] No import errors in logs
- [ ] Old directories removed
- [ ] Git history preserved for moved files
- [ ] CI/CD pipelines updated
- [ ] Documentation updated

---

## Rollback Plan

If migration fails:

```bash
# Restore from backup
rm -rf backend/src/gaia backend/src/gaia_private
cp -r backend/src_backup/* backend/src/

# Or reset git
git checkout -- backend/src
git clean -fd backend/src
```

---

## File Count Summary

| Package | Files | Purpose |
|---------|-------|---------|
| `gaia/api/` | ~20 | HTTP endpoints, schemas |
| `gaia/connection/` | ~12 | WebSocket, connections |
| `gaia/infra/audio/` | ~18 | TTS/STT infrastructure |
| `gaia/infra/image/` | ~10 | Image generation |
| `gaia/infra/llm/` | ~6 | LLM abstraction |
| `gaia/infra/storage/` | ~2 | Persistence |
| `gaia/models/` | ~35 | Data models |
| `gaia/mechanics/` | ~25 | Game rules (non-AI) |
| `gaia/engine/` | ~4 | Game configuration |
| `gaia/utils/` | ~10 | Utilities |
| **gaia/ Total** | **~142** | **PUBLIC** |
| `gaia_private/agents/` | ~45 | AI agents |
| `gaia_private/orchestration/` | ~7 | Agent coordination |
| `gaia_private/session/` | ~25 | Session management |
| `gaia_private/extraction/` | ~3 | AI extraction |
| `gaia_private/prompts/` | ~10 | Prompt management |
| **gaia_private/ Total** | **~90** | **PRIVATE** |

---

## Notes for Agent-Driven Refactoring

When using an AI agent to execute this plan:

1. **Execute phases sequentially** - Don't skip ahead
2. **Commit after each phase** - Easier to debug issues
3. **Run tests after each major move** - Catch import errors early
4. **Handle one directory at a time** - Less cognitive load
5. **Check for circular imports** - Common issue after reorganization
6. **Update __init__.py exports** - Maintain public API surface

The agent should be instructed to:
- Use `git mv` to preserve history
- Run `python3 -m py_compile <file>` after moves to catch syntax issues
- Keep a log of all changes made
- Stop and report if tests fail
