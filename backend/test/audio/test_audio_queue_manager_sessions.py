import asyncio

import pytest


@pytest.mark.asyncio
async def test_audio_queue_manager_is_session_isolated(monkeypatch):
    """Ensure audio playback state is isolated per session."""
    from gaia.infra.audio.audio_queue_manager import audio_queue_manager

    # Force mute output to avoid launching real playback processes during the test.
    monkeypatch.setattr(
        "gaia.infra.audio.voice_and_tts_config.get_tts_config",
        lambda: {"output": "mute", "windows_routing": "windows_utils"},
    )
    monkeypatch.setattr(
        "gaia.infra.audio.voice_and_tts_config.get_playback_config",
        lambda: {"chunk_delay": 0.0, "paragraph_delay": 0.0, "seamless": False},
    )

    session_a = "queue-session-a"
    session_b = "queue-session-b"

    # Queue simple paragraph breaks for both sessions
    await audio_queue_manager.add_paragraph_break(session_id=session_a)
    await audio_queue_manager.add_paragraph_break(session_id=session_b)

    # Wait for the worker threads to process the items
    for _ in range(20):
        status_a = audio_queue_manager.get_queue_status(session_id=session_a)
        status_b = audio_queue_manager.get_queue_status(session_id=session_b)
        if status_a["history_count"] > 0 and status_b["history_count"] > 0:
            break
        await asyncio.sleep(0.05)
    else:
        pytest.fail("Audio queue items were not processed in time")

    assert status_a["session_id"] == session_a
    assert status_b["session_id"] == session_b
    assert status_a["last_played"]["session_id"] == session_a
    assert status_b["last_played"]["session_id"] == session_b

    # Cleanup after test
    await audio_queue_manager.stop_current(session_id=session_a)
    await audio_queue_manager.stop_current(session_id=session_b)
    final_a = audio_queue_manager.get_queue_status(session_id=session_a)
    final_b = audio_queue_manager.get_queue_status(session_id=session_b)
    assert not final_a.get("pending_playback_ids")
    assert not final_b.get("pending_playback_ids")


@pytest.mark.asyncio
async def test_audio_queue_preserves_playback_group_order(monkeypatch, tmp_path):
    """Ensure playback runs through an entire request before switching groups."""
    from gaia.infra.audio.audio_queue_manager import audio_queue_manager

    # Force mute output and zero delays for reproducibility
    monkeypatch.setattr(
        "gaia.infra.audio.voice_and_tts_config.get_tts_config",
        lambda: {"output": "mute", "windows_routing": "windows_utils"},
    )
    monkeypatch.setattr(
        "gaia.infra.audio.voice_and_tts_config.get_playback_config",
        lambda: {"chunk_delay": 0.0, "paragraph_delay": 0.0, "seamless": False},
    )

    session_id = "playback-order-session"
    first_token = "group-one"
    second_token = "group-two"

    audio_path = tmp_path / "silence.wav"
    audio_path.write_bytes(b"\x00\x00")

    # Queue first logical group (two chunks)
    await audio_queue_manager.add_to_queue(
        file_path=str(audio_path),
        voice="test",
        text="chunk-1",
        session_id=session_id,
        playback_id=first_token,
        metadata={"chunk_number": 1},
    )
    await audio_queue_manager.add_to_queue(
        file_path=str(audio_path),
        voice="test",
        text="chunk-2",
        session_id=session_id,
        playback_id=first_token,
        metadata={"chunk_number": 2},
    )

    # Queue second logical group while first is still pending
    await audio_queue_manager.add_to_queue(
        file_path=str(audio_path),
        voice="test",
        text="chunk-a",
        session_id=session_id,
        playback_id=second_token,
        metadata={"chunk_number": 1},
    )

    # Allow worker to process
    for _ in range(40):
        status = audio_queue_manager.get_queue_status(session_id=session_id)
        if not status["is_playing"] and status["queue_size"] == 0:
            break
        await asyncio.sleep(0.05)
    else:
        pytest.fail("Audio queue did not drain in expected time")

    state = audio_queue_manager._get_session(session_id, create=False)
    assert state is not None
    history = list(state.playback_history)
    # Ensure we processed at least three items (two chunks + one chunk)
    assert len(history) >= 3
    # First two history entries should belong to the first playback group
    assert history[-3]["playback_id"] == first_token
    assert history[-2]["playback_id"] == first_token
    # Final entry should correspond to the second playback group
    assert history[-1]["playback_id"] == second_token

    await audio_queue_manager.stop_current(session_id=session_id)
