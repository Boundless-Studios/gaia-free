# Voice Registry Architecture

## Overview

The Voice Registry provides a centralized location for all TTS voice definitions, eliminating duplication and making it easier to manage voices across the application.

## Location

`src/core/audio/voice_registry.py`

## Key Components

### VoiceProvider Enum
```python
class VoiceProvider(Enum):
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    LOCAL = "local"
```

### Voice Dataclass
```python
@dataclass
class Voice:
    id: str                  # Internal voice ID used in code
    name: str                # Display name for UI
    provider: VoiceProvider  # TTS provider
    provider_voice_id: str   # Provider-specific voice ID
    description: str         # Voice description
    gender: Optional[str]    # Voice gender
    style: Optional[str]     # Voice style/personality
```

### VoiceRegistry Class
The main registry that contains all voice definitions and provides utility methods:

- `get_voice(voice_id)`: Get a voice by ID
- `get_provider_voice_id(voice_id, provider)`: Get provider-specific ID
- `list_voices(provider)`: List all voices, optionally filtered by provider
- `get_voice_mapping(provider)`: Get backward-compatible voice mapping
- `get_default_voice(provider)`: Get default voice for a provider

## Available Voices

### ElevenLabs Voices
- **priyanka**: Warm and expressive female voice
- **caleb**: Confident male voice
- **cornelius**: Distinguished older male voice
- **alice**: Clear and articulate female voice
- **jon**: Deep and authoritative (perfect for serious NPCs)
- **lea**: Warm and friendly (great for helpful characters)
- **gary**: Confident and clear (excellent for narration)
- **mike**: Calm and steady (ideal for descriptions)
- **laura**: Bright and engaging (perfect for lively characters)
- **jenna**: Expressive and animated (great for dramatic moments)

### OpenAI Voices
- **alloy**: OpenAI default voice

## Usage Examples

### In TTS Service
```python
from src.core.audio.voice_registry import VoiceRegistry, VoiceProvider

# Get voice ID for ElevenLabs
voice_id = VoiceRegistry.get_provider_voice_id("priyanka", VoiceProvider.ELEVENLABS)
```

### In API Endpoints
```python
# List available voices
voices = VoiceRegistry.list_voices()
for voice in voices:
    print(f"{voice.id}: {voice.description}")

# Validate voice exists
if not VoiceRegistry.get_voice(voice_id):
    raise ValueError(f"Voice '{voice_id}' not found")
```

## Benefits

1. **Single Source of Truth**: All voice definitions in one place
2. **Type Safety**: Using dataclasses provides type hints and validation
3. **Provider Abstraction**: Easy to add new TTS providers
4. **Backward Compatibility**: Maintains existing voice ID mappings
5. **Extensibility**: Easy to add new voices or voice metadata
6. **Validation**: Built-in voice validation for API endpoints

## Migration Notes

The registry was created to consolidate voice definitions that were previously scattered across:
- `tts_service.py`: Had hardcoded voice_mapping dictionary
- `auto_tts_service.py`: Referenced voices without validation
- Documentation: Listed voices that weren't implemented in code

Now all voice definitions are centralized in the voice registry, making the system more maintainable and consistent.