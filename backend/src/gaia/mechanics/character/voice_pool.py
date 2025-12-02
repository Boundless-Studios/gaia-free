"""Voice pool manager for character voice assignments."""

import random
import logging
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta

from gaia.models.character import CharacterProfile, CharacterType, VoiceArchetype
from gaia.infra.audio.voice_registry import VoiceRegistry, VoiceProvider


logger = logging.getLogger(__name__)


class VoicePool:
    """Manages available voices and assignments to ensure unique voices per character."""
    
    # Get available voices directly from registry
    @property
    def AVAILABLE_VOICES(self) -> Dict[str, Dict[str, str]]:
        """Get available voices from voice registry.
        
        Returns:
            Dict mapping voice IDs to their characteristics
        """
        voices = {}
        
        # Get all ElevenLabs voices from registry
        registry_voices = VoiceRegistry.list_voices(VoiceProvider.ELEVENLABS)
        
        for voice in registry_voices:
            # Convert Voice object to characteristics dict for compatibility
            voices[voice.id] = {
                "gender": voice.gender or "unknown",
                "age": "adult",  # Default since not in Voice model
                "tone": voice.style or "neutral",
                "accent": "american"  # Default since not in Voice model
            }
        
        return voices
    
    def __init__(self):
        """Initialize the voice pool."""
        self.assigned_voices: Dict[str, str] = {}  # character_id -> voice_id
        self.voice_last_used: Dict[str, datetime] = {}  # voice_id -> last used time
        self.voice_archetypes = self._define_archetypes()
        self.cooldown_period = timedelta(hours=2)  # Cooldown before reusing voice
    
    def _define_archetypes(self) -> Dict[VoiceArchetype, List[str]]:
        """Define voice archetypes for different character types.
        
        Returns:
            Mapping of archetypes to suitable voices
        """
        # Only use voices that exist in VoiceRegistry
        return {
            VoiceArchetype.HERO: ["caleb", "nathaniel", "priyanka"],
            VoiceArchetype.VILLAIN: ["cornelius", "caleb"],
            VoiceArchetype.MENTOR: ["cornelius", "priyanka", "nathaniel"],
            VoiceArchetype.MERCHANT: ["priyanka", "jen-soft", "nathaniel"],
            VoiceArchetype.NARRATOR: ["nathaniel", "cornelius", "jen-soft"],
            VoiceArchetype.CREATURE: ["cornelius", "caleb"],
            VoiceArchetype.CHILD: ["jen-soft", "priyanka"],
            VoiceArchetype.ELDER: ["cornelius", "nathaniel"]
        }
    
    def assign_voice(self, character: CharacterProfile, archetype: Optional[VoiceArchetype] = None) -> Tuple[str, VoiceArchetype]:
        """Assign appropriate voice based on character archetype.
        
        Args:
            character: CharacterProfile to assign voice to
            archetype: Optional voice archetype (defaults to NARRATOR for NPCs, HERO for players)
            
        Returns:
            Tuple of (voice_id, voice_archetype)
        """
        # Use provided archetype or default based on character type
        if archetype is None:
            archetype = VoiceArchetype.HERO if character.character_type == CharacterType.PLAYER else VoiceArchetype.NARRATOR
        
        # Get suitable voices for archetype
        suitable_voices = self.voice_archetypes.get(archetype, list(self.AVAILABLE_VOICES.keys()))
        
        # Filter out already assigned voices (for major characters)
        if character.character_type == CharacterType.PLAYER:
            # Players always get unique voices
            available_voices = [v for v in suitable_voices if v not in self.assigned_voices.values()]
        else:
            # NPCs can reuse voices after cooldown
            available_voices = self._get_available_voices_with_cooldown(suitable_voices)
        
        # If no voices available, expand search
        if not available_voices:
            available_voices = self._get_available_voices_with_cooldown(list(self.AVAILABLE_VOICES.keys()))
        
        # Select voice
        if available_voices:
            # Prefer voices that match character attributes
            voice_id = self._select_best_voice(character, available_voices)
        else:
            # Fallback: use least recently used voice
            voice_id = self._get_least_recently_used_voice()
        
        # Record assignment
        self.assigned_voices[character.character_id] = voice_id
        self.voice_last_used[voice_id] = datetime.now()
        
        logger.info(f"🎤 Assigned voice '{voice_id}' (archetype: {archetype.value}) to {character.name}")
        
        return voice_id, archetype
    
    def _get_available_voices_with_cooldown(self, voice_list: List[str]) -> List[str]:
        """Get voices that are available or past cooldown period.
        
        Args:
            voice_list: List of voices to check
            
        Returns:
            List of available voices
        """
        available = []
        current_time = datetime.now()
        
        for voice_id in voice_list:
            # Check if voice is assigned to active character
            if voice_id not in self.assigned_voices.values():
                available.append(voice_id)
            elif voice_id in self.voice_last_used:
                # Check cooldown
                last_used = self.voice_last_used[voice_id]
                if current_time - last_used >= self.cooldown_period:
                    available.append(voice_id)
        
        return available
    
    def _select_best_voice(self, character: CharacterProfile, available_voices: List[str]) -> str:
        """Select the best voice from available options.
        
        Args:
            character: CharacterProfile
            available_voices: List of available voice IDs
            
        Returns:
            Selected voice ID
        """
        # Score voices based on character attributes
        scores = {}
        
        for voice_id in available_voices:
            voice_attrs = self.AVAILABLE_VOICES[voice_id]
            score = 0
            
            # Gender matching (if specified in name)
            name_lower = character.name.lower()
            if voice_attrs["gender"] == "female" and any(word in name_lower for word in ["woman", "girl", "lady", "queen", "princess"]):
                score += 3
            elif voice_attrs["gender"] == "male" and any(word in name_lower for word in ["man", "boy", "lord", "king", "prince"]):
                score += 3
            
            # Age matching (based on name)
            if voice_attrs["age"] == "young" and any(word in name_lower for word in ["young", "youth", "child"]):
                score += 2
            elif voice_attrs["age"] == "elder" and any(word in name_lower for word in ["old", "elder", "aged"]):
                score += 2
            
            # Tone matching
            if voice_attrs["tone"] == "wise" and character.character_type == CharacterType.NPC:
                score += 1
            elif voice_attrs["tone"] == "confident" and character.character_type == CharacterType.PLAYER:
                score += 1
            
            scores[voice_id] = score
        
        # Sort by score and select best (with some randomization for ties)
        sorted_voices = sorted(available_voices, key=lambda v: scores.get(v, 0), reverse=True)
        top_score = scores.get(sorted_voices[0], 0)
        
        # Get all voices with top score
        top_voices = [v for v in sorted_voices if scores.get(v, 0) == top_score]
        
        # Randomly select from top voices
        return random.choice(top_voices)
    
    def _get_least_recently_used_voice(self) -> str:
        """Get the least recently used voice.
        
        Returns:
            Voice ID
        """
        if not self.voice_last_used:
            # No usage history, return random voice
            return random.choice(list(self.AVAILABLE_VOICES.keys()))
        
        # Sort by last used time
        sorted_voices = sorted(self.voice_last_used.items(), key=lambda x: x[1])
        return sorted_voices[0][0]
    
    def release_voice(self, character_id: str):
        """Release a voice assignment.
        
        Args:
            character_id: Character ID to release voice for
        """
        if character_id in self.assigned_voices:
            voice_id = self.assigned_voices[character_id]
            del self.assigned_voices[character_id]
            logger.info(f"🔊 Released voice '{voice_id}' from character {character_id}")
    
    def get_voice_archetype(self, voice_id: str) -> Optional[VoiceArchetype]:
        """Get the archetype for a specific voice.
        
        Args:
            voice_id: Voice ID
            
        Returns:
            VoiceArchetype or None
        """
        for archetype, voices in self.voice_archetypes.items():
            if voice_id in voices:
                return archetype
        return None
    
    def get_voice_info(self, voice_id: str) -> Dict[str, any]:
        """Get information about a voice.
        
        Args:
            voice_id: Voice ID
            
        Returns:
            Voice attributes dictionary
        """
        return self.AVAILABLE_VOICES.get(voice_id, {})
    
    def get_all_voices(self) -> Dict[str, Dict[str, any]]:
        """Get all available voices with their attributes.
        
        Returns:
            Dictionary of voice_id -> attributes
        """
        return self.AVAILABLE_VOICES.copy()
    
    def get_assigned_voices(self) -> Dict[str, str]:
        """Get current voice assignments.
        
        Returns:
            Dictionary of character_id -> voice_id
        """
        return self.assigned_voices.copy()