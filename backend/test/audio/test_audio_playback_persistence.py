"""Unit tests for audio playback persistence system."""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from gaia.infra.audio.audio_playback_service import audio_playback_service
from gaia.infra.audio.audio_models import AudioPlaybackRequest, AudioChunk, PlaybackStatus
from gaia.infra.audio.chunking_manager import UnifiedChunkingManager
from gaia.infra.audio.voice_registry import VoiceProvider
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter


class DummyBroadcaster:
    async def broadcast_playback_queue_update(self, *args, **kwargs):
        return None

    async def broadcast_campaign_update(self, *args, **kwargs):
        return None

    async def start_synchronized_stream(self, *args, **kwargs):
        return None

    def get_connected_user_ids(self, session_id: str):
        return []


class TestAudioPlaybackService:
    """Test suite for AudioPlaybackService."""

    def test_create_playback_request_success(self, audio_service, db_session, sample_campaign_id, sample_playback_group):
        """Test creating a playback request successfully."""
        # Execute
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group=sample_playback_group,
        )

        # Verify
        assert request_id is not None
        assert isinstance(request_id, uuid.UUID)

        # Verify the request was persisted in database
        from sqlalchemy import select
        stmt = select(AudioPlaybackRequest).where(AudioPlaybackRequest.request_id == request_id)
        result = db_session.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.campaign_id == sample_campaign_id
        assert result.playback_group == sample_playback_group
        assert result.status == PlaybackStatus.PENDING

    def test_create_playback_request_db_disabled(self):
        """Test creating playback request when database is disabled."""
        from gaia.infra.audio.audio_playback_service import AudioPlaybackService
        service = AudioPlaybackService()
        service._db_enabled = False

        result = service.create_playback_request(
            campaign_id="test-campaign",
            playback_group="narrative",
        )

        assert result is None

    def test_add_audio_chunk_success(self, audio_service, db_session, sample_campaign_id):
        """Test adding an audio chunk successfully."""
        # First create a playback request
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
        )
        assert request_id is not None

        artifact_id = "test-artifact-123"
        url = "/api/media/audio/test-campaign/test-artifact-123.mp3"

        # Execute
        chunk_id = audio_service.add_audio_chunk(
            request_id=request_id,
            campaign_id=sample_campaign_id,
            artifact_id=artifact_id,
            url=url,
            sequence_number=0,
            mime_type="audio/mpeg",
            size_bytes=12345,
            storage_path=f"{sample_campaign_id}/media/audio/test-artifact-123.mp3",
            duration_sec=3.5,
            bucket="test-bucket",
        )

        # Verify
        assert chunk_id is not None
        assert isinstance(chunk_id, uuid.UUID)

        # Verify the chunk was persisted in database
        from sqlalchemy import select
        stmt = select(AudioChunk).where(AudioChunk.chunk_id == chunk_id)
        result = db_session.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.request_id == request_id
        assert result.campaign_id == sample_campaign_id
        assert result.artifact_id == artifact_id
        assert result.url == url
        assert result.sequence_number == 0
        assert result.status == PlaybackStatus.PENDING

    def test_get_pending_chunks_ordered(self, audio_service, db_session, sample_campaign_id):
        """Test getting pending chunks in correct order."""
        # Create first request (older)
        request1_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
        )
        assert request1_id is not None

        # Create second request (newer)
        request2_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="response",
        )
        assert request2_id is not None

        # Add chunks to first request
        chunk1_id = audio_service.add_audio_chunk(
            request_id=request1_id,
            campaign_id=sample_campaign_id,
            artifact_id="artifact-1",
            url="/api/media/audio/campaign/artifact-1.mp3",
            sequence_number=0,
            mime_type="audio/mpeg",
            size_bytes=1000,
            storage_path="path1",
            duration_sec=2.0,
        )

        chunk2_id = audio_service.add_audio_chunk(
            request_id=request1_id,
            campaign_id=sample_campaign_id,
            artifact_id="artifact-2",
            url="/api/media/audio/campaign/artifact-2.mp3",
            sequence_number=1,
            mime_type="audio/mpeg",
            size_bytes=1500,
            storage_path="path2",
            duration_sec=3.0,
        )

        # Add chunk to second request
        chunk3_id = audio_service.add_audio_chunk(
            request_id=request2_id,
            campaign_id=sample_campaign_id,
            artifact_id="artifact-3",
            url="/api/media/audio/campaign/artifact-3.mp3",
            sequence_number=0,
            mime_type="audio/mpeg",
            size_bytes=2000,
            storage_path="path3",
            duration_sec=4.0,
        )

        # Execute
        chunks = audio_service.get_pending_chunks(sample_campaign_id)

        # Verify ordering: first by request time, then by sequence number
        assert len(chunks) == 3
        # First request chunks come first (ordered by sequence)
        assert chunks[0]["artifact_id"] == "artifact-1"
        assert chunks[0]["sequence_number"] == 0
        assert chunks[0]["playback_group"] == "narrative"
        assert chunks[1]["artifact_id"] == "artifact-2"
        assert chunks[1]["sequence_number"] == 1
        assert chunks[1]["playback_group"] == "narrative"
        # Second request chunk comes last
        assert chunks[2]["artifact_id"] == "artifact-3"
        assert chunks[2]["sequence_number"] == 0
        assert chunks[2]["playback_group"] == "response"

    def test_mark_chunk_played_success(self, audio_service, db_session, sample_campaign_id):
        """Test marking a chunk as played."""
        # Create request and chunk
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
        )
        chunk_id = audio_service.add_audio_chunk(
            request_id=request_id,
            campaign_id=sample_campaign_id,
            artifact_id="test-artifact",
            url="/api/media/audio/test.mp3",
            sequence_number=0,
            mime_type="audio/mpeg",
            size_bytes=1000,
            storage_path="test/path",
        )

        # Execute
        success = audio_service.mark_chunk_played(str(chunk_id))

        # Verify
        assert success is True

        # Verify status was updated in database
        from sqlalchemy import select
        stmt = select(AudioChunk).where(AudioChunk.chunk_id == chunk_id)
        result = db_session.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.status == PlaybackStatus.PLAYED
        assert result.played_at is not None

    def test_mark_chunk_played_not_found(self, audio_service):
        """Test marking non-existent chunk as played."""
        chunk_id = str(uuid.uuid4())

        # Execute
        success = audio_service.mark_chunk_played(chunk_id)

        # Verify
        assert success is False

    def test_mark_request_started_with_chunkless_request(self, audio_service, db_session, sample_campaign_id):
        """Regression test: mark_request_started() should not raise NameError on chunkless request.

        This tests the fix for the stale chunk_count reference bug where undefined
        chunk_count variable caused NameError when logging.
        """
        # Create a playback request without any chunks
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
            text="Test text for chunkless request",
        )
        assert request_id is not None

        # Mark request as started (should not raise NameError)
        success = audio_service.mark_request_started(request_id)

        # Verify
        assert success is True

        # Verify status was updated in database
        from sqlalchemy import select
        stmt = select(AudioPlaybackRequest).where(AudioPlaybackRequest.request_id == request_id)
        result = db_session.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.status == PlaybackStatus.GENERATING
        assert result.started_at is not None

    def test_cleanup_old_chunks(self, audio_service, db_session, sample_campaign_id):
        """Test cleaning up old played chunks."""
        # Create request and chunks
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
        )

        # Create two chunks and mark them as played
        chunk1_id = audio_service.add_audio_chunk(
            request_id=request_id,
            campaign_id=sample_campaign_id,
            artifact_id="old-artifact-1",
            url="/api/media/audio/old1.mp3",
            sequence_number=0,
            mime_type="audio/mpeg",
            size_bytes=1000,
            storage_path="path1",
        )
        chunk2_id = audio_service.add_audio_chunk(
            request_id=request_id,
            campaign_id=sample_campaign_id,
            artifact_id="old-artifact-2",
            url="/api/media/audio/old2.mp3",
            sequence_number=1,
            mime_type="audio/mpeg",
            size_bytes=1500,
            storage_path="path2",
        )

        # Mark both chunks as played
        audio_service.mark_chunk_played(str(chunk1_id))
        audio_service.mark_chunk_played(str(chunk2_id))

        # Manually set played_at to 10 days ago to make them eligible for cleanup
        from sqlalchemy import update
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=10)
        stmt = (
            update(AudioChunk)
            .where(AudioChunk.chunk_id.in_([chunk1_id, chunk2_id]))
            .values(played_at=old_timestamp)
        )
        db_session.execute(stmt)
        db_session.commit()

        # Execute cleanup (delete chunks older than 7 days)
        deleted_count = audio_service.cleanup_old_chunks(sample_campaign_id, days=7)

        # Verify
        assert deleted_count == 2

        # Verify chunks were deleted from database
        from sqlalchemy import select
        stmt = select(AudioChunk).where(AudioChunk.chunk_id.in_([chunk1_id, chunk2_id]))
        remaining = db_session.execute(stmt).scalars().all()
        assert len(remaining) == 0


class TestChunkingManagerIntegration:
    """Test chunking manager integration with audio persistence."""

    @pytest.mark.asyncio
    async def test_synthesize_with_chunking_creates_request(self, audio_service, db_session, sample_campaign_id):
        """Test that synthesize_with_chunking creates a playback request."""
        # Mock audio creator function (ElevenLabs)
        async def mock_audio_creator(text: str, voice: str, speed: float) -> bytes:
            return b"fake_audio_data"

        # Mock on_chunk_ready callback
        chunks_ready = []

        async def mock_on_chunk_ready(artifact: Dict[str, Any]) -> None:
            chunks_ready.append(artifact)

        # Mock audio artifact store (file I/O)
        mock_artifact = MagicMock()
        mock_artifact.id = "test-artifact-id"
        mock_artifact.url = "/api/media/audio/test/artifact.mp3"
        mock_artifact.mime_type = "audio/mpeg"
        mock_artifact.size_bytes = 1000
        mock_artifact.duration_sec = 2.5
        mock_artifact.storage_path = "test/path"
        mock_artifact.bucket = None
        mock_artifact.to_payload = Mock(return_value={
            "success": True,
            "id": "test-artifact-id",
            "url": "/api/media/audio/test/artifact.mp3",
            "mime_type": "audio/mpeg",
            "size_bytes": 1000,
            "duration_sec": 2.5,
            "storage_path": "test/path",
            "bucket": None,
        })

        mock_store = MagicMock()
        mock_store.enabled = True
        mock_store.uses_gcs = False
        mock_store.persist_audio = Mock(return_value=mock_artifact)

        # Use real audio service but mock artifact store
        with patch('gaia.infra.audio.audio_artifact_store.audio_artifact_store', mock_store):

            writer = PlaybackRequestWriter(
                session_id=sample_campaign_id,
                broadcaster=DummyBroadcaster(),
                playback_group="narrative",
            )

            # Execute
            await UnifiedChunkingManager.synthesize_with_chunking(
                text="This is a test sentence for audio synthesis.",
                provider=VoiceProvider.ELEVENLABS,
                voice="test-voice",
                speed=1.0,
                audio_creator_func=mock_audio_creator,
                play=False,
                chunked=True,
                session_id=sample_campaign_id,
                persist_progressive=True,
                on_chunk_ready=mock_on_chunk_ready,
                playback_group="narrative",
                playback_writer=writer,
            )
            await writer.finalize()

            # Verify playback request was created in database
            from sqlalchemy import select
            stmt = select(AudioPlaybackRequest).where(
                AudioPlaybackRequest.campaign_id == sample_campaign_id
            )
            requests = db_session.execute(stmt).scalars().all()
            assert len(requests) >= 1
            assert requests[0].playback_group == "narrative"

            # Verify chunks were ready
            assert len(chunks_ready) > 0

            # Verify artifact store was called
            assert mock_store.persist_audio.called



class TestAPIEndpoints:
    """Test API endpoint behavior."""


    @pytest.mark.asyncio
    async def test_mark_audio_played_endpoint_success(self, audio_service, db_session, sample_campaign_id):
        """Test POST /api/audio/played/{chunk_id} endpoint success."""
        from gaia.api.routes.chat import mark_audio_played

        # Create real chunk in database
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
        )
        chunk_id = audio_service.add_audio_chunk(
            request_id=request_id,
            campaign_id=sample_campaign_id,
            artifact_id="test-chunk",
            url="/api/media/audio/test.mp3",
            sequence_number=0,
            mime_type="audio/mpeg",
            size_bytes=1000,
            storage_path="test/chunk.mp3",
        )

        # Execute
        response = await mark_audio_played(
            chunk_id=str(chunk_id),
            current_user=None,
        )

        # Verify
        assert response["success"] is True
        assert response["chunk_id"] == str(chunk_id)

        # Verify chunk status was updated in database
        from sqlalchemy import select
        stmt = select(AudioChunk).where(AudioChunk.chunk_id == chunk_id)
        result = db_session.execute(stmt).scalar_one()
        assert result.status == PlaybackStatus.PLAYED

    @pytest.mark.asyncio
    async def test_mark_audio_played_endpoint_not_found(self):
        """Test POST /api/audio/played/{chunk_id} when chunk not found."""
        from gaia.api.routes.chat import mark_audio_played
        from fastapi import HTTPException

        chunk_id = str(uuid.uuid4())

        # Execute and verify exception
        with pytest.raises(HTTPException) as exc_info:
            await mark_audio_played(
                chunk_id=chunk_id,
                current_user=None,
            )

        assert exc_info.value.status_code == 404




class TestEndToEndFlow:
    """Test end-to-end audio playback persistence flow."""

    @pytest.mark.asyncio
    async def test_full_audio_persistence_flow(self, audio_service, db_session, sample_campaign_id):
        """Test complete flow from generation to playback to marking played."""
        # Step 1: Create playback request
        request_id = audio_service.create_playback_request(
            campaign_id=sample_campaign_id,
            playback_group="narrative",
        )
        assert request_id is not None

        # Step 2: Add chunks
        chunk_ids = []
        for i in range(3):
            chunk_id = audio_service.add_audio_chunk(
                request_id=request_id,
                campaign_id=sample_campaign_id,
                artifact_id=f"artifact-{i}",
                url=f"/api/media/audio/test/chunk-{i}.mp3",
                sequence_number=i,
                mime_type="audio/mpeg",
                size_bytes=1000,
                storage_path=f"path-{i}",
            )
            assert chunk_id is not None
            chunk_ids.append(chunk_id)

        # Step 3: Query pending chunks
        chunks = audio_service.get_pending_chunks(sample_campaign_id)
        assert len(chunks) == 3
        assert all(c["playback_group"] == "narrative" for c in chunks)
        assert chunks[0]["sequence_number"] == 0
        assert chunks[1]["sequence_number"] == 1
        assert chunks[2]["sequence_number"] == 2

        # Step 4: Mark first chunk as played
        success = audio_service.mark_chunk_played(str(chunk_ids[0]))
        assert success is True

        # Verify chunk was marked played in database
        from sqlalchemy import select
        stmt = select(AudioChunk).where(AudioChunk.chunk_id == chunk_ids[0])
        result = db_session.execute(stmt).scalar_one()
        assert result.status == PlaybackStatus.PLAYED
        assert result.played_at is not None

        # Step 5: Query pending chunks again (should only have 2 now)
        remaining_chunks = audio_service.get_pending_chunks(sample_campaign_id)
        assert len(remaining_chunks) == 2
        assert remaining_chunks[0]["chunk_id"] == str(chunk_ids[1])
        assert remaining_chunks[1]["chunk_id"] == str(chunk_ids[2])
