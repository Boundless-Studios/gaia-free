"""Centralized TTS provider management system."""

import os
import logging
from typing import Optional, List, Dict, Tuple
from enum import Enum

from gaia.infra.audio.voice_registry import VoiceRegistry, VoiceProvider

logger = logging.getLogger(__name__)

class TTSProviderManager:
    """Centralized manager for TTS provider availability and default selection."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # Provider priority order (highest to lowest)
        self.provider_priority = [
            VoiceProvider.ELEVENLABS,
            VoiceProvider.LOCAL, 
            VoiceProvider.OPENAI
        ]
        
        # Cache for availability status
        self._availability_cache = {}
        self._last_check = 0
        self._cache_duration = 30  # seconds
        
    def get_provider_priority_order(self) -> List[VoiceProvider]:
        """Get the priority order for TTS providers."""
        return self.provider_priority.copy()
    
    def check_provider_availability(self, provider: VoiceProvider) -> bool:
        """Check if a specific TTS provider is available."""
        try:
            from gaia.infra.audio.tts_service import tts_service
            
            if provider == VoiceProvider.LOCAL:
                return tts_service.local_tts_available
            elif provider == VoiceProvider.ELEVENLABS:
                return tts_service.elevenlabs_available
            elif provider == VoiceProvider.OPENAI:
                return tts_service.openai_client is not None
            else:
                return False
        except Exception as e:
            logger.warning(f"Error checking availability for {provider}: {e}")
            return False
    
    def get_available_providers(self) -> List[VoiceProvider]:
        """Get list of available TTS providers in priority order."""
        available = []
        for provider in self.provider_priority:
            if self.check_provider_availability(provider):
                available.append(provider)
        return available
    
    def get_default_provider(self) -> Optional[VoiceProvider]:
        """Get the default TTS provider based on availability and priority."""
        available_providers = self.get_available_providers()
        if available_providers:
            return available_providers[0]  # First available provider (highest priority)
        return None
    
    def get_default_voice(self) -> Optional[str]:
        """Get the default voice ID based on available providers and priority."""
        default_provider = self.get_default_provider()
        if default_provider:
            return VoiceRegistry.get_default_voice(default_provider)
        return None
    
    def get_default_voice_for_provider(self, provider: VoiceProvider) -> Optional[str]:
        """Get the default voice for a specific provider."""
        if self.check_provider_availability(provider):
            return VoiceRegistry.get_default_voice(provider)
        return None
    
    def get_provider_info(self) -> Dict[str, Dict]:
        """Get comprehensive provider information for frontend."""
        try:
            from gaia.infra.audio.tts_service import tts_service
            
            provider_info = {}
            
            # Local TTS
            local_available = tts_service.local_tts_available
            local_voices = VoiceRegistry.list_voices(VoiceProvider.LOCAL) if local_available else []
            provider_info['local'] = {
                'available': local_available,
                'voice_count': len(local_voices),
                'default_voice': VoiceRegistry.get_default_voice(VoiceProvider.LOCAL) if local_available else None
            }
            
            # ElevenLabs
            elevenlabs_available = tts_service.elevenlabs_available
            elevenlabs_voices = VoiceRegistry.list_voices(VoiceProvider.ELEVENLABS) if elevenlabs_available else []
            provider_info['elevenlabs'] = {
                'available': elevenlabs_available,
                'voice_count': len(elevenlabs_voices),
                'default_voice': VoiceRegistry.get_default_voice(VoiceProvider.ELEVENLABS) if elevenlabs_available else None
            }
            
            # OpenAI
            openai_available = tts_service.openai_client is not None
            openai_voices = VoiceRegistry.list_voices(VoiceProvider.OPENAI) if openai_available else []
            provider_info['openai'] = {
                'available': openai_available,
                'voice_count': len(openai_voices),
                'default_voice': VoiceRegistry.get_default_voice(VoiceProvider.OPENAI) if openai_available else None
            }
            
            return provider_info
            
        except Exception as e:
            logger.error(f"Error getting provider info: {e}")
            return {
                'local': {'available': False, 'voice_count': 0, 'default_voice': None},
                'elevenlabs': {'available': False, 'voice_count': 0, 'default_voice': None},
                'openai': {'available': False, 'voice_count': 0, 'default_voice': None}
            }
    
    def get_recommended_provider_for_frontend(self) -> Optional[str]:
        """Get the recommended provider ID for frontend selection."""
        default_provider = self.get_default_provider()
        if default_provider:
            return default_provider.value  # Convert enum to string
        return None

# Global instance
provider_manager = TTSProviderManager() 