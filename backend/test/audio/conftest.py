"""Configuration for audio tests - mocks external dependencies and provides database fixtures."""

import sys
import pytest
from unittest.mock import Mock

# Mock elevenlabs module to avoid import errors
mock_elevenlabs = Mock()
mock_elevenlabs.client = Mock()
mock_elevenlabs.client.ElevenLabs = Mock()
sys.modules['elevenlabs'] = mock_elevenlabs
sys.modules['elevenlabs.client'] = mock_elevenlabs.client


@pytest.fixture(scope="function")
def db_session():
    """Provide a real database session with cleanup for test isolation."""
    from db.src.connection import db_manager
    from gaia.infra.audio.audio_models import AudioPlaybackRequest, AudioChunk
    from sqlalchemy import delete

    # Initialize database
    db_manager.initialize()
    engine = db_manager.sync_engine

    # Create tables if they don't exist
    with engine.begin() as connection:
        AudioPlaybackRequest.__table__.create(bind=connection, checkfirst=True)
        AudioChunk.__table__.create(bind=connection, checkfirst=True)

    # Create session
    session = db_manager.sync_session_factory()

    yield session

    # Clean up all test data (audio_service commits its own transactions)
    try:
        # Delete all chunks first (foreign key constraint)
        session.execute(delete(AudioChunk))
        # Then delete all requests
        session.execute(delete(AudioPlaybackRequest))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


@pytest.fixture(scope="function")
def audio_service():
    """Provide AudioPlaybackService with real database enabled."""
    from gaia.infra.audio.audio_playback_service import AudioPlaybackService
    from db.src.connection import db_manager

    # Ensure database is initialized
    db_manager.initialize()

    # Create fresh service instance
    service = AudioPlaybackService()
    if not service.db_enabled:
        # Force initialization if it failed
        service._init_db()

    return service


@pytest.fixture
def sample_campaign_id():
    """Sample campaign identifier."""
    return "test-campaign-audio-123"


@pytest.fixture
def sample_playback_group():
    """Sample playback group."""
    return "narrative" 