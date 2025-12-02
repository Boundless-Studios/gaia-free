# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General Approach
1. Explore the codebase
2. Make a plan
3. Execute your plan
4. Create or update tests based on changes
5. Test your changes by running the actual code

## Development Guidelines

### Data Modeling
- For data modeling always prefer typed dataobjects to raw dictionaries.
- When we convert Dict to a fixed data model representation don't maintain backwards compatibility for the type
- Minimize where in the code we have to be concerned with serialization/deserialization. Only persistence managers should deal with the serialized Dict representations while most code should use typed objects
- Create one file per data model

### Persistence Hooks
- Agent tools automatically trigger persistence via hooks in `src/game/dnd_agents/tools/persistence_hooks.py`
- All hooks work with typed data structures (CharacterInfo, NPCInfo, EnvironmentInfo, QuestInfo, SceneInfo)
- Tools return structured data matching model schemas
- Hooks deserialize to typed models before persisting
- See `src/core/session/CLAUDE.md` for detailed hook flow documentation


### Branching & PRs
- Create new branches off of main (ensure main is up to date)
- Avoid stacked branches where possible
- Create a PR once complete for every branch

### Testing & Validation
- Always test changes by running `gaia_launcher.py test` and checking for errors
- Ensure changes compile on both frontend and backend
- Check logs at `src/logs/gaia_all.log` for errors
- When adding dependencies, ensure they're installed by package managers in `gaia_launcher.py`

### File Organization
- Documentation goes in `docs/` folder
- Test scripts go in `scripts/claude_helpers/`
- Frontend code is in `src/frontend/`
- Backend code is in `src/backend` (`/home/gaia/src/backend` in docker)

## Python Execution
- ALways test inside the docker container
- ALWAYS use `python3` instead of `python` when running scripts
- Virtual environment locations:
  - `/tmp/gaia_venv` (WSL with Windows filesystem)
  - `./venv` (otherwise)
- Use `sys.executable` when calling Python from within Python scripts

## Quick Start Commands

```bash
# One-click setup
python3 gaia_launcher.py

# Backend server (Docker - recommended)
docker compose up -d gpu  # or 'dev' for CPU-only
# Check system health
curl http://localhost:8000/api/health
```

## Running Commands in Docker

When working with Docker containers, use the following patterns:

```bash
# Execute commands in the running GPU container
docker exec gaia-backend-gpu bash -c "cd /home/gaia && python3 scripts/your_script.py"

# Generate campaign summaries
docker exec gaia-backend-gpu bash -c "cd /home/gaia && CAMPAIGN_STORAGE_PATH='/home/gaia/campaigns' python3 scripts/generate_campaign_summary.py campaign_11"

# Run tests
docker exec gaia-backend-gpu bash -c "cd /home/gaia && python3 -m pytest tests/"

# Access Python shell
docker exec -it gaia-backend-gpu python3

# View logs
docker logs gaia-backend-gpu --tail 100 -f
```

### Important Docker Paths
- Working directory: `/home/gaia`
- Campaign storage: `/home/gaia/campaigns`
- Logs: `/home/gaia/logs`
- Source code: `/home/gaia/src`

### Docker Services
- `gpu`: Production-like environment with GPU support
- `dev`: Development environment (CPU only)
- `test`: Testing environment
- `prod`: Production build

## Architecture Overview

### Core Systems

**Orchestrator (`src/core/agent_orchestration/`)**
- Unified orchestrator with automatic agent handoffs
- Uses the `agents` library for seamless transitions
- No deferred initialization - all components ready on startup

**D&D Agents (`src/game/dnd_agents/`)**
- DungeonMaster: Main storyteller and coordinator
- EncounterRunner: Complex encounter management
- RuleEnforcer: D&D 5e rule interpretations
- TurnRunner: Combat initiative and turn order
- ScenarioAnalyzer: Analyzes player input
- OutputFormatter: Structures responses into JSON

**LLM Providers (`src/core/llm/`)**
- Ollama (local): llama3.x, deepseek-coder series (deprecated for production)
- Claude (API): claude-3-5-sonnet-20241022
- Parasail (API): kimi-k2-instruct, deepseek-r1-0528-qwen3-8b, qwen3-32b
- Environment: `USE_SMALLER_MODEL=true` for lighter models
- **Automatic Model Management**: Models are automatically pulled on container startup
  - Primary model: `$OLLAMA_MODEL` (default: llama3.2:1b)
  - Default fallback: `$DEFAULT_OLLAMA_MODEL` (default: llama3.1:8b)
  - Smaller fallback: `$SMALLER_OLLAMA_MODEL` (default: llama3.2:1b)
  - Models are pulled during Docker build AND at runtime if missing
- **Model Fallback Chain**: Production uses Parasail-only models to avoid API provider failures
  - Primary: kimi-k2-instruct
  - Fallback 1: deepseek-r1-0528-qwen3-8b
  - Fallback 2: qwen3-32b
  - All use PARASAIL_API_KEY for consistent availability

**Campaign System (`src/core/session/`)**
- Campaign persistence and state management
- Session tracking and statistics
- Chat history integration
- Scene transitions (only on explicit DM scene creation)
- Turn management with combat integration
- Automatic persistence hooks for character/NPC/environment/quest updates

**Audio System (`src/core/audio/`)**
- ElevenLabs STT for transcription
- Multi-provider TTS (Parler-TTS, OpenAI, local)
- Voice activity detection with frequency analysis
- WSL-to-Windows audio passthrough

## Key Features & Configuration

**Frontend Usage:**
1. Click "🎙️ Show Transcription" button
2. Click "🎤 Start Listening" to begin
3. Voice activity indicator shows green when speaking
4. Click "📤 Send Unsent Text" to send to chat

### Image Generation
```bash
# Providers (automatic fallback, in order of preference)
# 1. Gemini 2.0 Flash (preferred - fast cloud-based)
export GEMINI_API_KEY=your_key_here
# 2. Local SDXL (fallback - requires GPU)
```

## API Endpoints

### Core
- `GET /api/health` - System health check
- `POST /api/chat` - Send chat message
- `WebSocket /api/chat/stream` - Streaming chat

### Audio
- `WebSocket /ws/transcribe/continuous` - Continuous transcription
- `GET /api/voice-activity/{session_id}` - Voice activity status
- `POST /api/tts/synthesize` - Generate speech
- `GET /api/tts/auto/status` - Auto-TTS status

### Campaign
- `GET /api/campaigns` - List campaigns
- `POST /api/campaigns/new` - Create campaign
- `GET /api/campaigns/{id}/history` - Get history

### Images
- `POST /api/images/generate` - Generate image
- `GET /api/images/models` - Available models
- `GET /api/media/images/{session_id}/{filename}` - Serve character portraits and scene images from GCS/local storage

## Development Workflow

### Adding New Agents
1. Create agent class in `src/game/dnd_agents/`
2. Define instructions, tools, output format, and model
3. Implement handoff logic in existing agents
4. Add to orchestrator initialization

### Frontend Development
- Components expect structured API responses
- Use dark gaming theme conventions
- Test with different agent responses and handoffs

## Pre-Generated Content and Deployment

### Pre-Generation System

The system pre-generates campaigns and characters during Cloud Run container startup via `scripts/entrypoint_cloud_run.py`.

**Behavior:**
- Non-blocking by default - failures don't prevent deployment
- Checks GCS bucket first for existing content before generating
- Saves to both local filesystem (`/tmp/campaigns/pregenerated/`) and GCS
- Uses Parasail-only model fallback chain to avoid API provider failures

**Model Fallback Chain** (`scripts/pregenerate_content.py`):
1. `kimi-k2-instruct` - Primary Parasail model
2. `deepseek-r1-0528-qwen3-8b` - First fallback
3. `qwen3-32b` - Final fallback

All models use `PARASAIL_API_KEY` for consistent availability.

**Retry Logic:**
- Validation failures (incomplete output): Retry same model with stronger prompt (2 retries)
- Provider failures (API errors): Immediately try next model in chain
- This prevents wasting API credits on transient issues

**Environment Variables:**
- `AUTO_PREGEN_FAIL_ON_ERROR=true` - Make pre-gen failures blocking (dev/test only)
- `FORCE_PREGEN=true` - Force regeneration even if content exists
- `SKIP_AUTO_PREGEN=true` - Skip pre-generation entirely
- `AUTO_PREGEN_MIN_CAMPAIGNS=5` - Minimum campaigns before skip
- `AUTO_PREGEN_MIN_CHARACTERS=10` - Minimum characters before skip
- `AUTO_PREGEN_LOCK_TIMEOUT=600` - Lock acquisition timeout (seconds)

**GCS Persistence:**
Pre-generated content is saved to:
```
gs://gaia-campaigns-{env}/campaigns/{env}/pregenerated/campaigns.json
gs://gaia-campaigns-{env}/campaigns/{env}/pregenerated/characters.json
```

This ensures content persists across container restarts and deployments.

### Deployment Environment Variables

Deployment supports `DEPLOY_*` environment variables for dynamic configuration:

**Usage in deployment scripts:**
```bash
# Force pre-generation during deployment
./scripts/deploy_production.sh --force-pregen

# Passes to GitHub Actions workflow as force_pregen input
# Workflow sets DEPLOY_FORCE_PREGEN=true
# entrypoint_cloud_run.py reads and converts to FORCE_PREGEN
```

**Pattern:**
- Deployment script flags → GitHub Actions inputs → `DEPLOY_*` env vars → Runtime env vars
- Allows temporary configuration without changing base environment files

### Character Visual Fields

Character generation includes visual details for portrait generation:
- `gender` - Character's gender presentation (default: "non-binary")
- `facial_expression` - Default expression (default: "determined")
- `build` - Physical build (default: "average")

These fields ensure portrait generation always has required details. Defaults are applied in:
- `scripts/pregenerate_content.py` - Pre-generated characters
- `backend/src/api/campaign_service.py` - Runtime character generation

### Image Artifact Storage

Character portraits and scene images use `ImageArtifactStore` (`backend/src/core/image/image_artifact_store.py`):

**Features:**
- GCS-backed persistent storage
- Automatic file cleanup after upload (saves ephemeral storage)
- Returns URLs in format: `/api/media/images/{session_id}/{filename}`
- Mirrors `AudioArtifactStore` pattern for consistency
- Environment-aware path generation (production vs development)

**Storage Paths:**
- **Production**: `media/images/campaign_XX/portraits/image.png` (no hostname prefix)
- **Development**: `media/images/{hostname}/campaign_XX/portraits/image.png` (hostname prefix to avoid conflicts)
- **Local Cache**: `/tmp/gaia-images/{session_id}/{filename}`

**Environment Detection:**
The store checks three environment variables to determine production vs development:
1. `ENV` - Set to `prod`/`stg` for production/staging, `dev` for development
2. `ENVIRONMENT_NAME` - Alternative production/staging indicator
3. `ENVIRONMENT` - Legacy variable, set to `development` for dev mode

If none are set or don't match known values, defaults to **production behavior** (no hostname prefix) for safety.

**Required Environment Variables:**
- **Production/Staging**: Set at least one of: `ENV=prod`, `ENVIRONMENT_NAME=prod`, or `ENVIRONMENT=production`
- **Development**: Set `ENVIRONMENT=development` to enable hostname-prefixed paths
- Configured in: `config/cloudrun.prod.env`, `config/cloudrun.stg.env`, `backend/.settings.docker.env`

**Backward Compatibility:**
The store includes fallback logic for images stored with incorrect paths:
1. Primary: New path (`media/images/campaign_XX/portraits/image.png`)
2. Legacy: Old path (`campaign_XX/media/images/image.png`)
3. Hostname-prefixed: Migration fallback (`media/images/localhost/campaign_XX/portraits/image.png`)

This ensures existing images remain accessible after the environment detection bug fix.

**Endpoint:** `/api/media/images/{session_id}/{filename}`
- Authentication via header token or query parameter
- Authorization checks against session ownership
- Serves from GCS if enabled, falls back to local storage

## Troubleshooting

### Common Issues
- **Ollama not running**: Automatically started by Docker entrypoint script
- **Port conflicts**: Check ports 8000 (backend) and 5173 (frontend)
- **Missing models**: Models are auto-pulled on startup; if issues persist:
  - Check logs: `docker logs gaia-backend-gpu 2>&1 | grep "Pulling"`
  - Manually pull: `docker exec gaia-backend-gpu ollama pull llama3.2:1b`
  - Verify models: `docker exec gaia-backend-gpu ollama list`
- **Audio issues**: Run `./setup_wsl_audio_improved.sh`
- **Pre-generation failures**: Check Cloud Run logs for model fallback chain
  - Verify `PARASAIL_API_KEY` is set in Secret Manager
  - Check if pre-generated content exists in GCS bucket
  - Use `--force-pregen` flag to regenerate content
- **Character portrait issues**: Ensure `ImageArtifactStore` has GCS enabled
  - Check `CAMPAIGN_STORAGE_BUCKET` and `CAMPAIGN_STORAGE_BACKEND` env vars
  - Verify service account has `storage.objects.create` permission
- **Image 404 errors in production**: Verify environment variables are set correctly
  - Production/Staging: Must have `ENV=prod`, `ENVIRONMENT_NAME=prod`, or `ENVIRONMENT=production`
  - Missing these causes images to use hostname prefix (`localhost/campaign_XX/...`)
  - Check `config/cloudrun.prod.env` and `config/cloudrun.stg.env` for proper values
  - See Image Artifact Storage section for full environment detection documentation

### Log Locations
- Backend: `src/logs/gaia_backend.log`
- Frontend: Browser console
- All logs: `src/logs/gaia_all.log`

## Audio System

### Overview
Gaia features a comprehensive audio system with multiple Text-to-Speech (TTS) providers, Speech-to-Text (STT) capabilities, and a centralized voice registry. The system supports local and cloud-based audio generation with automatic fallback and seamless WSL2 Windows audio passthrough.

### Audio Architecture

**Multi-Provider TTS System:**
1. **Local F5-TTS** (Preferred when available): High-quality local TTS server
   - Runs on localhost:7860 via Gradio interface
   - Multiple voice models (EN_V2, EN, ES)
   - No API keys required
   - Automatic server management
2. **ElevenLabs** (Primary cloud provider): Professional voice synthesis
   - 20+ character voices with distinct personalities
   - Real-time streaming support
   - Requires `ELEVENLABS_API_KEY`

**Speech-to-Text (STT) System:**
- **ElevenLabs STT**: Primary transcription service
- WebSocket-based continuous transcription
- Voice activity detection with frequency analysis
- 5-minute audio buffering
- Visual voice activity indicator in frontend

**Centralized Voice Registry:**
- Single source of truth for all voice definitions
- Prevents duplicate voice configurations
- Character role assignments (DM/Narrator, Noble NPC, Merchant, etc.)
- Voice attributes (gender, style, personality)

### API Endpoints

**TTS Generation:**
- `POST /api/tts/synthesize` - Generate speech from text
- `GET /api/tts/voices` - List available voices
- `GET /api/tts/availability` - Check TTS provider availability
- `GET /api/tts/providers` - Get available providers with recommendations

**Auto-TTS Control:**
- `GET /api/tts/auto/status` - Get auto-TTS configuration
- `POST /api/tts/auto/toggle` - Toggle auto-TTS on/off
- `POST /api/tts/auto/voice/{voice}` - Set voice
- `POST /api/tts/auto/speed/{speed}` - Set playback speed

**Audio Queue Management:**
- `GET /api/tts/queue/status` - Get audio queue status
- `POST /api/tts/queue/clear` - Clear pending audio
- `POST /api/tts/queue/stop` - Stop current playback

**Character Voices:**
- `GET /api/characters/voices` - Get voices formatted for character management

### Usage Examples

**Test Audio Generation:**
```bash
# Test TTS backend
cd src && python3 test_auto_tts_integration.py

# Test manual TTS generation
curl -X POST "http://localhost:8000/api/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text":"Welcome to your D&D adventure!","voice":"jon","speed":1.0}' \
  --output narration.wav
```

**Control Auto-TTS via API:**
```bash
# Check auto-TTS status
curl http://localhost:8000/api/tts/auto/status

# Change voice to Lea
curl -X POST http://localhost:8000/api/tts/auto/voice/lea

# Set faster speed
curl -X POST http://localhost:8000/api/tts/auto/speed/1.3
```

### Local F5-TTS Setup

**Installation:**
```bash
# Install F5-TTS (if not already installed)
pip install f5-tts

# Start the TTS server
python3 scripts/start_tts_server.py

# Or manually start with custom port
python3 -m f5_tts.gradio_app --port 7860
```

**Server Management:**
- Automatic server detection on startup
- Graceful shutdown handling
- Process management via `TTSServerManager`
- Health checks at `http://localhost:7860/`

### Troubleshooting

**Common Issues:**
- **No audio output**: Ensure `GAIA_AUDIO_DISABLED` is unset and, if screen-sharing, force `AUTO_TTS_OUTPUT=windows`
- **Permission errors**: WSL audio requires Windows interop features
- **Missing voices**: Install TTS dependencies with `pip install -r requirements.txt`
- **Slow generation**: Use local F5-TTS for faster processing
- **F5-TTS not available**: Ensure server is running on port 7860
- **ElevenLabs quota**: Check API usage limits

**Audio File Locations:**
- Generated audio: `/tmp/gaia_auto_tts/`
- Test audio: `/tmp/gaia_test_audio.wav`
- Windows temp: `C:\Windows\Temp\gaia_narration.wav`

**Debugging:**
- Check logs: Backend shows TTS generation details
- Audio file sizes: 60KB-100KB per response indicates successful generation
- Test Windows audio: `powershell.exe -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('Test')"`

### Features

**Automatic Narration:**
- DM responses automatically generate immersive audio
- Extracts narrative content from JSON and text responses
- Plays through Windows audio system for best experience
- Caches audio for repeated phrases
- **Seamless playback mode**: Concatenates all audio chunks before playing for smoother narration

**Voice Registry System:**
The centralized voice registry (`src/core/audio/voice_registry.py`) manages all available voices:

**ElevenLabs Character Voices:**
- **nathaniel**: Calm English narrator (DM/Narrator role)
- **cornelius**: Distinguished older male (Noble NPC)
- **priyanka**: Warm expressive female (Innkeeper)
- **caleb**: Confident male (Warrior)
- **alice**: Clear articulate female (Merchant)
- **mr-attractive**: Moderate Japanese accent (Wise Sage)
- **almee-whisper**: ASMR-style female (Mysterious Character)

**Local F5-TTS Voices:**
- **EN_V2**: Enhanced English voice model
- **EN**: Standard English voice
- **ES**: Spanish voice model

**Provider Manager:**
- Automatic provider selection based on availability
- Fallback chain: Local F5-TTS → ElevenLabs → OpenAI → Local Basic
- Dynamic voice availability checking
- Seamless switching between providers

### Speech-to-Text (STT) System

**ElevenLabs STT Integration:**
- WebSocket-based continuous transcription
- Real-time audio streaming with chunk processing
- Automatic language detection
- Session-based transcription management

**Voice Activity Detection:**
- Frequency-based voice detection algorithm
- Visual indicator in frontend (green when speaking)
- 5-minute audio buffer for context
- Configurable sensitivity thresholds

**Frontend Integration:**
1. Click "🎙️ Show Transcription" to reveal controls
2. Click "🎤 Start Listening" to begin transcription
3. Voice activity indicator shows real-time speech detection
4. Transcribed text appears in the input field
5. Click "📤 Send Unsent Text" to send to chat

**WebSocket Endpoints:**
- `/ws/transcribe`: Basic audio transcription
- `/ws/transcribe/continuous`: Continuous transcription with voice activity

## Parasail API Integration

### Overview
Gaia now supports the Parasail API for accessing the Kimi K2 model, a powerful language model that can be used alongside Ollama and Claude.

### Configuration
```bash
# Parasail API key (required)
export PARASAIL_API_KEY=your_key_here
```

### Usage
To use the Kimi K2 model in your agents, specify the model key:
- `kimi-k2-instruct` or `parasail-kimi-k2-instruct`

Example in agent configuration:
```python
agent = Agent(
    model="kimi-k2-instruct",
    # ... other configuration
)
```

### Testing
```bash
# Test Parasail text generation
python3 scripts/claude_helpers/test_parasail_kimi.py

# Test Parasail batch image generation
python3 scripts/claude_helpers/test_parasail_batch_image.py
```

## Image Generation

### Overview
Gaia supports multiple image generation providers with automatic fallback:
1. **Stable Diffusion XL (Local)** - Default provider for GPU-accelerated local generation
2. **Gemini 2.0 Flash** - Secondary cloud provider for fast generation
3. **Parasail (OmniGen)** - Tertiary cloud provider using batch API

### Configuration

#### Local Stable Diffusion XL Setup
```bash
# Install dependencies
pip install torch torchvision diffusers transformers accelerate safetensors

# Optional: Install xformers for memory efficiency
pip install xformers

# Optional: Set custom model path (defaults to SDXL)
export FLUX_MODEL_PATH=stabilityai/stable-diffusion-xl-base-1.0

# Check dependencies
python3 test_flux_dependencies.py
```

**Note**: SDXL will download ~6.9GB of model files on first run. Make sure you have:
- Sufficient disk space
- Good internet connection
- GPU with at least 8GB VRAM (recommended)

#### Cloud Providers
```bash
# Gemini API key (Google's image generation)
export GEMINI_API_KEY=your_key_here

# Parasail API key (OmniGen batch generation)
export PARASAIL_API_KEY=your_key_here

# HuggingFace API key (for gated models and Lightning checkpoints)
export HUGGING_FACE_KEY=your_huggingface_token_here
```

### Features
- **Automatic Fallback**: Local SDXL (default) → Gemini → Parasail
- **GPU Acceleration**: Flux uses CUDA if available
- **Memory Optimization**: Supports xformers and attention slicing
- **D&D Optimized**: Prompts are automatically enhanced for D&D fantasy art
- **Multiple Types**: Supports scenes, characters, items, maps, and creatures
- **Flexible Sizes**: Supports various aspect ratios and resolutions

### API Endpoints
- `POST /api/images/generate` - Generate an image
- `GET /api/images/models` - List available models
- `GET /api/images/sizes/{model}` - Get supported sizes for a model

### Testing
```bash
# Test Flux local generation
python3 scripts/claude_helpers/test_flux_local.py

# Test Gemini generation
python3 scripts/claude_helpers/test_gemini_image_generation.py

# Test full integration
python3 test_gaia_audio.sh
```

### Performance Tips
1. **GPU Usage**: SDXL requires a GPU with 6GB+ VRAM for optimal performance
2. **CPU Fallback**: Works on CPU but is significantly slower (5-10 minutes per image)
3. **Memory**: Use `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512` if you encounter OOM errors
4. **Batch Size**: Generate one image at a time to avoid memory issues

## Testing Infrastructure

### Test Suite Status
- **386 tests passing** consistently
- **1 test skipped** intentionally (manual-only full combat integration test)
- **1 remaining warning** (internal to Pydantic library)

### Recent Test Modernization (Oct 2025)
- **Pydantic v2 Migration**: Updated all Pydantic models from v1 to v2 syntax
  - `src/api/schemas/chat.py` - API request/response models
  - `src/game/dnd_agents/character_generator.py:37-63` - Character generation output
  - `src/game/dnd_agents/campaign_generator.py:24-57` - Campaign generation output
  - Changed `class Config` to `model_config = ConfigDict()`
  - Changed `min_items`/`max_items` to `min_length`/`max_length` for lists

- **SQLAlchemy Modernization**: Updated to current import paths
  - Changed `sqlalchemy.orm.declarative_base` to `sqlalchemy.orm.declarative_base` (new location)

- **Test Helper Cleanup**: Renamed test classes to avoid pytest collection warnings
  - Test helper classes now use `Helper` prefix instead of `Test` prefix
  - Prevents pytest from attempting to collect helper classes as tests

- **Integration Test Re-enablement**: Re-enabled 7 previously skipped integration tests
  - `test/core/character/test_character_campaign_integration.py` - 5 tests
  - `test/test_character_scene_integration.py` - 2 tests
  - All tests now passing with proper fixture isolation

- **Manual Integration Test Documentation**: Enhanced documentation for full combat integration test
  - `test/combat/integration/test_combat_full_integration.py` - Remains skipped for CI/CD
  - Comprehensive usage instructions for manual validation
  - Requires full LLM environment setup

### Running Tests
```bash
# Run all tests in Docker
python3 gaia_launcher.py test

# Run specific test file
python3 gaia_launcher.py test backend/test/api/test_main.py

# Run with verbose output
python3 gaia_launcher.py test -v
```

### Test Categories
- **Unit Tests**: Fast, isolated component tests
- **Integration Tests**: Multi-component interaction tests with proper fixtures
- **Manual Tests**: Complex end-to-end tests requiring full environment (1 test, documented)

See `backend/test/README.md` for complete testing documentation.

## Recent Updates

- **Image Storage Hostname Fix** (Oct 2025): Fixed production image storage environment detection bug
  - Production images now stored without hostname prefix (`media/images/campaign_XX/...` not `localhost/campaign_XX/...`)
  - Enhanced environment detection to check ENV, ENVIRONMENT_NAME, and ENVIRONMENT variables
  - Added backward compatibility fallback for existing hostname-prefixed images
  - Comprehensive test suite for environment detection and path generation
- **Test Infrastructure Modernization**: Fixed 16 Python warnings, re-enabled 7 integration tests, migrated to Pydantic v2
- **Persistence Hooks Type Safety**: All persistence hooks now use typed data structures (CharacterInfo, NPCInfo, EnvironmentInfo, QuestInfo, SceneInfo) instead of raw dictionaries
- **Scene Transition Improvements**: Scene transitions now only occur on explicit DM scene creation via `scene_creator` tool or `requires_new_scene` flag; all other turns update the current scene
- **Combat Scene Transitions**: Fixed combat scene transition logic to properly handle scene changes during combat
- **Voice detection** with frequency analysis and 5-minute buffering
- **Visual voice activity indicator** shows when user is speaking
- **Pause/resume fixes** for transcription reliability
- **Seamless audio playback mode** for smoother TTS narration
- **Parasail API integration** for Kimi K2 model
- **Structured Data Parsing**: Fixed backend to parse JSON responses from LLM correctly
- **Frontend Layout**: Separated chat from game dashboard for better UX
- **Individual Components**: Each D&D section (Narrative, Turn, Characters, Status) now displays separately
- **WSL Audio Integration**: Complete TTS system with automatic DM narration and Windows audio passthrough
- **Voice Registry**: Created centralized voice registry to eliminate duplicate voice definitions
- **Transcription Service**: Migrated from WhisperX to ElevenLabs STT - WhisperX code retained but not initialized
- **Cleaned up redundant test scripts** for better project organization
