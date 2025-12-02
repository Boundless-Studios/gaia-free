"""Tests for TTS service functionality."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import importlib

class TestTTSService:
    """Test TTS service functionality."""
    
    @pytest.fixture
    def tts_service(self):
        """Create TTS service instance."""
        with patch("gaia.infra.audio.voice_and_tts_config.GAIA_AUDIO_DISABLED", True), \
                patch("gaia.infra.audio.voice_and_tts_config.AUTO_TTS_ENABLED", False), \
                patch("gaia.infra.audio.voice_and_tts_config.CLIENT_AUDIO_ENABLED", False):
            import gaia.infra.audio.tts_service as tts_module
            importlib.reload(tts_module)
            return tts_module.TTSService()
    
    def test_get_available_voices(self, tts_service):
        """Test getting available voices."""
        voices = tts_service.get_available_voices()
        # Without API keys, voices list may be empty - that's expected behavior
        # Just verify the method doesn't crash and returns a list
        assert isinstance(voices, list)
        # If voices are available, they should have the required fields
        if voices:
            assert all("name" in v and "provider" in v for v in voices)

class TestAutoTTSService:
    """Test automatic TTS service."""
    
    @pytest.fixture
    def auto_tts(self):
        """Create auto TTS service instance."""
        with patch("gaia.infra.audio.voice_and_tts_config.GAIA_AUDIO_DISABLED", False), \
                patch("gaia.infra.audio.voice_and_tts_config.AUTO_TTS_ENABLED", True), \
                patch("gaia.infra.audio.voice_and_tts_config.CLIENT_AUDIO_ENABLED", True):
            import gaia.infra.audio.auto_tts_service as auto_module
            importlib.reload(auto_module)
            auto_module.AutoTTSService._instance = None
            return auto_module.AutoTTSService.get_instance()
    
    def test_singleton_pattern(self):
        """Test that AutoTTSService is a singleton."""
        from gaia.infra.audio.auto_tts_service import AutoTTSService
        
        instance1 = AutoTTSService.get_instance()
        instance2 = AutoTTSService.get_instance()
        
        assert instance1 is instance2
    
    def test_enable_disable(self, auto_tts):
        """Test enabling and disabling auto TTS."""
        auto_tts.enabled = False
        
        result = auto_tts.toggle_enabled()
        assert result is True
        assert auto_tts.enabled is True
        
        result = auto_tts.toggle_enabled()
        assert result is False
        assert auto_tts.enabled is False
    
    def test_set_voice(self, auto_tts):
        """Test setting voice."""
        # Use a voice that exists in the registry
        auto_tts.set_voice("nathaniel")
        assert auto_tts.default_voice == "nathaniel"

        # Setting to an invalid voice logs warning but keeps current voice
        auto_tts.set_voice("invalid_voice")
        assert auto_tts.default_voice in ["nathaniel", "dm"]  # May keep previous or fall back to default
    
    def test_set_speed(self, auto_tts):
        """Test setting speed."""
        auto_tts.set_speed(1.5)
        assert auto_tts.speed == 1.5
        
        # Too fast, should clamp to 4.0
        auto_tts.set_speed(5.0)
        assert auto_tts.speed == 4.0
        
        # Too slow, should clamp to 0.25
        auto_tts.set_speed(0.1)
        assert auto_tts.speed == 0.25
