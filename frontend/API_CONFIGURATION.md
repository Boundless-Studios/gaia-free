# Gaia API Configuration Guide

## Overview
Gaia is currently configured to use external AI models that require API keys. This guide will help you configure all the necessary API keys to run Gaia successfully.

## Current Model Configuration

Based on the logs, Gaia is trying to use these models:
- **Scenario Analyzer**: `deepseek-r1-0528-qwen3-8b` (Parasail API)
- **Dungeon Master**: `kimi-k2-instruct` (Parasail API)

## Required API Keys

### 1. Parasail API (Required for current setup)
**Purpose**: Provides access to Kimi K2 and DeepSeek models
**Get API Key**: https://parasail.io/
**Environment Variable**: `PARASAIL_API_KEY`

### 2. Claude API (Alternative to Parasail)
**Purpose**: High-quality AI responses
**Get API Key**: https://console.anthropic.com/
**Environment Variable**: `CLAUDE_API_KEY`

### 3. ElevenLabs API (Optional - for Speech-to-Text)
**Purpose**: Audio transcription
**Get API Key**: https://elevenlabs.io/
**Environment Variable**: `ELEVENLABS_SPEECH_TO_TEXT_API_KEY`

### 4. OpenAI API (Optional - for TTS)
**Purpose**: Text-to-speech generation
**Get API Key**: https://platform.openai.com/
**Environment Variable**: `OPENAI_API_KEY`

### 5. Gemini API (Optional - for image generation)
**Purpose**: Image generation
**Get API Key**: https://makersuite.google.com/app/apikey
**Environment Variable**: `GEMINI_API_KEY`

## Quick Setup

### Option 1: Use Parasail (Recommended)
```bash
# Set your Parasail API key
export PARASAIL_API_KEY="your_parasail_api_key_here"

# Start Gaia
python start_gaia_launcher.py
```

### Option 2: Use Claude
```bash
# Set your Claude API key
export CLAUDE_API_KEY="your_claude_api_key_here"

# Start Gaia
python start_gaia_launcher.py
```

### Option 3: Use Ollama Only (Local - No API keys needed)
```bash
# Modify agent configurations to use Ollama models
# Edit these files to change models to Ollama models:
# - src/game/dnd_agents/scenario_analyzer.py (change to "llama3.2:3b")
# - src/game/dnd_agents/dungeon_master.py (change to "llama3.2:3b")

python start_gaia_launcher.py
```

## Environment Variables Reference

```bash
# Required for current setup
export PARASAIL_API_KEY="your_parasail_api_key"

# Alternative to Parasail
export CLAUDE_API_KEY="your_claude_api_key"
export CLAUDE_MODEL="claude-3-5-sonnet-20241022"
export CLAUDE_BASE_URL="https://api.anthropic.com/v1"

# Optional - Audio features
export ELEVENLABS_SPEECH_TO_TEXT_API_KEY="your_elevenlabs_key"
export OPENAI_API_KEY="your_openai_key"
export GEMINI_API_KEY="your_gemini_key"

# Audio runtime overrides
export GAIA_AUDIO_DISABLED="true"  # disable auto-TTS + client audio (optional)
export AUTO_TTS_OUTPUT="windows"   # override output detection when necessary
```

## Model Configuration Files

### Current Agent Models (src/game/dnd_agents/)

**Scenario Analyzer** (`src/game/dnd_agents/scenario_analyzer.py`):
```python
SCENARIO_ANALYZER_CONFIG = AgentConfig(
    name="Scenario Analyzer",
    description="Analyzes player input to determine complexity, relevant mechanics, and optimal approach",
    model="deepseek-r1-0528-qwen3-8b",  # Parasail model
    temperature=0.3
)
```

**Dungeon Master** (`src/game/dnd_agents/dungeon_master.py`):
```python
DUNGEON_MASTER_CONFIG = AgentConfig(
    name="Dungeon Master",
    description="Central coordinator for D&D campaigns, manages overall story and player interactions",
    model="kimi-k2-instruct",  # Parasail model
    temperature=0.7
)
```

## How to Change Models

### To Use Ollama Models (Local - No API keys needed):

1. **Edit Scenario Analyzer** (`src/game/dnd_agents/scenario_analyzer.py`):
```python
SCENARIO_ANALYZER_CONFIG = AgentConfig(
    name="Scenario Analyzer",
    description="Analyzes player input to determine complexity, relevant mechanics, and optimal approach",
    model="llama3.2:3b",  # Changed to Ollama model
    temperature=0.3
)
```

2. **Edit Dungeon Master** (`src/game/dnd_agents/dungeon_master.py`):
```python
DUNGEON_MASTER_CONFIG = AgentConfig(
    name="Dungeon Master",
    description="Central coordinator for D&D campaigns, manages overall story and player interactions",
    model="llama3.2:3b",  # Changed to Ollama model
    temperature=0.7
)
```

### To Use Claude Models:

1. **Edit Scenario Analyzer** (`src/game/dnd_agents/scenario_analyzer.py`):
```python
SCENARIO_ANALYZER_CONFIG = AgentConfig(
    name="Scenario Analyzer",
    description="Analyzes player input to determine complexity, relevant mechanics, and optimal approach",
    model="claude-3-5-sonnet-20241022",  # Changed to Claude model
    temperature=0.3
)
```

2. **Edit Dungeon Master** (`src/game/dnd_agents/dungeon_master.py`):
```python
DUNGEON_MASTER_CONFIG = AgentConfig(
    name="Dungeon Master",
    description="Central coordinator for D&D campaigns, manages overall story and player interactions",
    model="claude-3-5-sonnet-20241022",  # Changed to Claude model
    temperature=0.7
)
```

## Testing Your Configuration

### Test Parasail API:
```bash
python scripts/claude_helpers/test_parasail_kimi.py
```

### Test Claude API:
```bash
python scripts/claude_helpers/test_claude_integration.py
```

### Test Ollama Models:
```bash
ollama list
ollama run llama3.2:3b "Hello, how are you?"
```

## Troubleshooting

### Common Issues:

1. **"API key not found" errors**:
   - Check that environment variables are set correctly
   - Restart your terminal after setting environment variables
   - Use `echo $PARASAIL_API_KEY` to verify the key is set

2. **"Model not available" errors**:
   - For Ollama: Run `ollama pull llama3.2:3b`
   - For Parasail: Check your API key and account status
   - For Claude: Verify your API key and billing status

3. **"Connection refused" errors**:
   - Check if the API service is available
   - Verify your internet connection
   - Check if the API endpoint is correct

### Debug Mode:
```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"
python start_gaia_launcher.py
```

## Recommended Setup

For the best experience, we recommend:

1. **Get a Parasail API key** (free tier available)
2. **Set the environment variable**: `export PARASAIL_API_KEY="your_key"`
3. **Start Gaia**: `python start_gaia_launcher.py`

This will give you access to high-quality AI models without requiring local GPU resources.

## Alternative: Local-Only Setup

If you prefer to run everything locally without API keys:

1. **Install Ollama models**: `ollama pull llama3.2:3b`
2. **Edit agent configurations** to use Ollama models (see above)
3. **Start Gaia**: `python start_gaia_launcher.py`

This setup will work completely offline but may have lower quality responses. 
