"""Tests for Auto-TTS integration with DM responses."""

import pytest
import logging
from unittest.mock import patch, AsyncMock, Mock
from pathlib import Path

from gaia.infra.audio.auto_tts_service import auto_tts_service, AutoTTSService
from gaia.infra.audio.tts_service import AudioSynthesisResult

# Setup logging for tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestAutoTTSIntegration:
    """Test the auto-TTS service with sample DM responses."""
    
    @pytest.fixture(autouse=True)
    def setup_auto_tts(self):
        """Setup auto-TTS service for each test."""
        # Reset service state
        auto_tts_service.enabled = True
        auto_tts_service.default_voice = "jon"
        auto_tts_service.speed = 1.0
        auto_tts_service.client_audio_enabled = False
        yield
        # Cleanup after each test
        auto_tts_service.cleanup()
    
    @pytest.mark.asyncio
    async def test_simple_narrative_response(self):
        """Test processing a simple narrative response."""
        text = "Welcome, brave adventurers, to the mystical realm of Eldoria! The ancient tower looms before you, its stone walls covered in mysterious glowing runes."
        
        with patch('gaia.infra.audio.auto_tts_service.tts_service') as mock_tts:
            mock_tts.synthesize_speech = AsyncMock(
                return_value=AudioSynthesisResult(audio_bytes=b'123', method='local')
            )
            
            result = await auto_tts_service.generate_audio(text, "test_session_1")
            
            assert result is True
            mock_tts.synthesize_speech.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_json_string_response_format(self):
        """Test processing JSON string response format."""
        text = "The dungeon door creaks open, revealing a dark corridor filled with the echo of distant footsteps. A cold wind carries the scent of ancient magic."
        
        with patch('gaia.infra.audio.auto_tts_service.tts_service') as mock_tts:
            mock_tts.synthesize_speech = AsyncMock(
                return_value=AudioSynthesisResult(audio_bytes=b'123', method='local')
            )
            
            result = await auto_tts_service.generate_audio(text, "test_session_2")
            
            assert result is True
            mock_tts.synthesize_speech.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_direct_response_text(self):
        """Test processing direct response text."""
        text = "The goblin chieftain raises his rusty blade and lets out a bone-chilling war cry! Roll for initiative!"
        
        with patch('gaia.infra.audio.auto_tts_service.tts_service') as mock_tts:
            mock_tts.synthesize_speech = AsyncMock(
                return_value=AudioSynthesisResult(audio_bytes=b'123', method='local')
            )
            
            result = await auto_tts_service.generate_audio(text, "test_session_3")
            
            assert result is True
            mock_tts.synthesize_speech.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_voice_and_speed_configuration(self):
        """Test voice and speed configuration changes."""
        # Set voice and speed (use 'priyanka' which exists in registry)
        auto_tts_service.set_voice("priyanka")
        auto_tts_service.set_speed(1.2)

        text = "With a faster pace and different voice, the story continues as you venture deeper into the mysterious caverns."

        with patch('gaia.infra.audio.auto_tts_service.tts_service') as mock_tts:
            mock_tts.synthesize_speech = AsyncMock(
                return_value=AudioSynthesisResult(audio_bytes=b'123', method='local')
            )

            result = await auto_tts_service.generate_audio(text, "test_session_4")

            assert result is True
            mock_tts.synthesize_speech.assert_called_once()

            # Verify that the service is using the configured voice and speed
            assert auto_tts_service.default_voice == "priyanka"
            assert auto_tts_service.speed == 1.2
    
    def test_toggle_functionality(self):
        """Test enable/disable toggle functionality."""
        # Test initial state
        assert auto_tts_service.enabled == True
        
        # Toggle off
        auto_tts_service.toggle_enabled()
        assert auto_tts_service.enabled == False
        
        # Toggle back on
        auto_tts_service.toggle_enabled()
        assert auto_tts_service.enabled == True
    
    @pytest.mark.asyncio
    async def test_disabled_auto_tts(self):
        """Test that audio is not generated when disabled."""
        auto_tts_service.enabled = False
        
        text = "This should not generate audio."
        
        result = await auto_tts_service.generate_audio(text, "test_session_disabled")
        
        # Should not have audio when disabled
        assert result is None
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test handling of empty or invalid responses."""
        # Test empty text
        result = await auto_tts_service.generate_audio("", "test_session_empty")
        assert result is None
        
        # Test whitespace-only text
        result = await auto_tts_service.generate_audio("   \n\t   ", "test_session_no_text")
        assert result is None
    
    def test_temp_directory_creation(self):
        """Test that temporary directory is created properly."""
        # The simplified AutoTTSService doesn't have temp_dir
        # This test is no longer applicable
        pass
    
    @pytest.mark.asyncio
    async def test_audio_generation_failure_handling(self):
        """Test handling of audio generation failures."""
        text = "This should handle TTS failure gracefully."
        
        with patch('gaia.infra.audio.auto_tts_service.tts_service') as mock_tts:
            mock_tts.synthesize_speech = AsyncMock(side_effect=Exception("TTS failed"))
            
            result = await auto_tts_service.generate_audio(text, "test_session_failure")
            
            # Should not crash, just return None
            assert result is None 

    @pytest.mark.asyncio
    async def test_returns_artifact_when_client_audio_enabled(self):
        """Auto-TTS should surface artifact payload when client audio is enabled."""
        auto_tts_service.client_audio_enabled = True

        text = "The narrator speaks." 
        fake_artifact = Mock()
        fake_artifact.to_payload.return_value = {
            "success": True,
            "id": "artifact-123",
            "session_id": "session_client",
            "url": "https://example.com/audio.mp3",
            "mime_type": "audio/mpeg",
            "duration_sec": 12.3,
            "size_bytes": 1024,
            "created_at": "2024-11-19T10:00:00Z",
        }

        with patch('gaia.infra.audio.auto_tts_service.tts_service') as mock_tts:
            mock_tts.synthesize_speech = AsyncMock(
                return_value=AudioSynthesisResult(
                    audio_bytes=b'123',
                    method='elevenlabs',
                    artifact=fake_artifact,
                )
            )

            result = await auto_tts_service.generate_audio(text, "session_client")

            assert isinstance(result, dict)
            assert result["success"] is True
            assert result["provider"] == "elevenlabs"
            assert result["session_id"] == "session_client"
            mock_tts.synthesize_speech.assert_awaited_once()
            _, kwargs = mock_tts.synthesize_speech.call_args
            assert kwargs["persist"] is True
            assert kwargs["session_id"] == "session_client"

        auto_tts_service.client_audio_enabled = False
