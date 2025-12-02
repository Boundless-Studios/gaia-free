"""
Central voice registry for all TTS voices used in Gaia.
This module consolidates all voice definitions to avoid duplication.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
from .f5_tts_config import get_speaker_names, get_speaker_config


class VoiceProvider(Enum):
    """Supported TTS providers."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    LOCAL = "local"


@dataclass
class Voice:
    """Voice configuration."""
    id: str  # Internal voice ID used in code
    name: str  # Display name for UI
    provider: VoiceProvider
    provider_voice_id: str  # Provider-specific voice ID
    description: str
    gender: Optional[str] = None
    style: Optional[str] = None
    character_role: Optional[str] = None  # Character role in the game (DM/Narrator, Noble NPC, etc.)


class VoiceRegistry:
    """Central registry for all available voices."""
    
    # ElevenLabs voice mappings
    ELEVENLABS_VOICES = {
        "priyanka": Voice(
            id="priyanka",
            name="Priyanka",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="BpjGufoPiobT79j2vtj4",
            description="Warm and expressive female voice",
            gender="female",
            style="friendly",
            character_role="Innkeeper"
        ),
        "caleb": Voice(
            id="caleb",
            name="Caleb",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="pNInz6obpgDQGcFmaJgB",
            description="Confident male voice",
            gender="male",
            style="confident",
            character_role="Warrior"
        ),
        "cornelius": Voice(
            id="cornelius",
            name="Cornelius",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="6sFKzaJr574YWVu4UuJF",
            description="Distinguished older male voice",
            gender="male",
            style="authoritative",
            character_role="Noble NPC"
        ),
        "alice": Voice(
            id="alice",
            name="Alice",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="Xb7hH8MSUJpSbSDYk0k2",
            description="Clear and articulate female voice",
            gender="female",
            style="professional",
            character_role="Merchant"
        ),
        "mr-attractive": Voice(
            id="mr-attractive",
            name="Mr. Attractive",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="Gwf9mOMZG8bkPbhsbOVc",
            description="Moderate Japanese",
            gender="male",
            style="professional",
            character_role="Wise Sage"
        ),
        "nathaniel": Voice(
            id="nathaniel",
            name="Nathaniel",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="AeRdCCKzvd23BpJoofzx",
            description="Calm English",
            gender="male",
            style="storyteller",
            character_role="DM/Narrator"
        ),
        "almee-whisper": Voice(
            id="almee-whisper",
            name="Almee Whisper",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="GL7nHO5mDrxcHlJPJK5T",
            description="Freaky Soft",
            gender="female",
            style="storyteller",
            character_role="Mysterious Figure"
        ),
        "jen-soft": Voice(
            id="jen-soft",
            name="Jen Soft",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="HzVnxqtdk9eqrcwfxD57",
            description="Gentle and Soft",
            gender="female",
            style="narrator",
            character_role="Young Adventurer"
        )
    }
    
    # OpenAI voice mappings (if needed in the future)
    OPENAI_VOICES = {
        "alloy": Voice(
            id="alloy",
            name="Alloy",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="alloy",
            description="OpenAI default voice",
            gender="neutral",
            style="neutral"
        )
    }
    
    # Local F5-TTS voice mappings based on Python configuration
    LOCAL_VOICES = {}
    
    @classmethod
    def _get_local_voice_mappings(cls) -> Dict[str, Voice]:
        """Get local F5-TTS voice mappings based on Python configuration."""
        mappings = {}
        
        for speaker_id, speaker in get_speaker_names().items():
            speaker_config = get_speaker_config(speaker_id)
            if speaker_config:
                # Map speaker roles to character roles
                character_role_map = {
                    "dm": "DM/Narrator",
                    "adventurer": "Young Adventurer", 
                    "innkeeper": "Innkeeper",
                    "merchant": "Merchant",
                    "sage": "Wise Sage",
                    "mysterious": "Mysterious Figure",
                    "warrior": "Warrior",
                    "noble": "Noble NPC"
                }
                
                mappings[speaker_id] = Voice(
                    id=speaker_id,
                    name=speaker,
                    provider=VoiceProvider.LOCAL,
                    provider_voice_id=speaker_id,
                    description=speaker_config.description,
                    gender=speaker_config.gender,
                    style=speaker_config.style,
                    character_role=character_role_map.get(speaker_id, speaker)
                )
        
        return mappings
    
    @classmethod
    def get_voice(cls, voice_id: str) -> Optional[Voice]:
        """Get a voice by ID."""
        # Check ElevenLabs voices first
        if voice_id in cls.ELEVENLABS_VOICES:
            return cls.ELEVENLABS_VOICES[voice_id]
        # Check OpenAI voices
        if voice_id in cls.OPENAI_VOICES:
            return cls.OPENAI_VOICES[voice_id]
        # Check Local voices (dynamic from config)
        local_voices = cls._get_local_voice_mappings()
        if voice_id in local_voices:
            return local_voices[voice_id]
        return None
    
    @classmethod
    def get_provider_voice_id(cls, voice_id: str, provider: VoiceProvider = VoiceProvider.LOCAL) -> str:
        """Get the provider-specific voice ID for a given voice."""
        voice = cls.get_voice(voice_id)
        if voice and voice.provider == provider:
            return voice.provider_voice_id
        
        # If voice not found or wrong provider, get default voice for the provider
        default_voice_id = cls.get_default_voice(provider)
        default_voice = cls.get_voice(default_voice_id)
        if default_voice and default_voice.provider == provider:
            return default_voice.provider_voice_id
        
        # Final fallback - return empty string if no valid voice found
        return ""
    
    @classmethod
    def list_voices(cls, provider: Optional[VoiceProvider] = None) -> List[Voice]:
        """List all available voices, optionally filtered by provider."""
        all_voices = []
        
        # Add ElevenLabs voices
        all_voices.extend(cls.ELEVENLABS_VOICES.values())
        
        # Add OpenAI voices
        all_voices.extend(cls.OPENAI_VOICES.values())
        
        # Add Local voices (dynamic from config)
        local_voices = cls._get_local_voice_mappings()
        all_voices.extend(local_voices.values())
        
        # Filter by provider if specified
        if provider:
            all_voices = [v for v in all_voices if v.provider == provider]
        
        return all_voices
    
    @classmethod
    def get_voice_mapping(cls, provider: VoiceProvider = VoiceProvider.LOCAL) -> Dict[str, str]:
        """Get a simple voice ID to provider ID mapping for backward compatibility."""
        mapping = {}
        for voice in cls.list_voices(provider):
            mapping[voice.id] = voice.provider_voice_id
        return mapping
    
    @classmethod
    def get_default_voice(cls, provider: VoiceProvider = VoiceProvider.LOCAL) -> Optional[str]:
        """Get the default voice ID for a provider based on DM/Narrator character role."""
        # Get all voices for the specified provider
        provider_voices = cls.list_voices(provider)
        
        # Find the first voice with "DM/Narrator" character role
        dm_narrator_voice = next(
            (voice for voice in provider_voices if voice.character_role == "DM/Narrator"),
            None
        )
        
        if dm_narrator_voice:
            return dm_narrator_voice.id
        
        # Fallback to first available voice if no DM/Narrator found
        if provider_voices:
            return provider_voices[0].id
        
        # No voices available for this provider
        return None


# Convenience exports
def get_voice(voice_id: str) -> Optional[Voice]:
    """Get a voice by ID."""
    return VoiceRegistry.get_voice(voice_id)


def get_provider_voice_id(voice_id: str, provider: VoiceProvider = VoiceProvider.LOCAL) -> str:
    """Get the provider-specific voice ID."""
    return VoiceRegistry.get_provider_voice_id(voice_id, provider)


def list_voices(provider: Optional[VoiceProvider] = None) -> List[Voice]:
    """List all available voices."""
    return VoiceRegistry.list_voices(provider)