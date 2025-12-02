"""Debug endpoints for streaming and DM testing."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth.src.flexible_auth import optional_auth
from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
from gaia_private.session.session_manager import SessionNotFoundError, SessionManager
from gaia.infra.audio.auto_tts_service import auto_tts_service
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter
from gaia.infra.audio.voice_and_tts_config import STREAMING_DEBUG_TTS_ENABLED
from gaia_private.orchestration.orchestrator import Orchestrator
from gaia.engine.dm_context import DMContext


router = APIRouter(prefix="/api/debug", tags=["debug"])


class StreamingTestRequest(BaseModel):
    session_id: str = Field(..., description="Campaign/session identifier to target")
    narrative: Optional[str] = Field(
        None,
        description="Narrative text to stream. Defaults to a canned sample when omitted.",
    )
    player_response: Optional[str] = Field(
        None,
        description="Player response text to stream. Defaults to a canned sample when omitted.",
    )


class RunDmRequest(BaseModel):
    session_id: str = Field(..., description="Campaign/session identifier to target")
    prompt: Optional[str] = Field(
        None,
        description="Prompt to feed the Dungeon Master. A default debug prompt is used when omitted.",
    )


class RunStreamingDirectRequest(BaseModel):
    session_id: str = Field(..., description="Campaign/session identifier to target")
    prompt: Optional[str] = Field(
        None,
        description="Prompt to feed the streaming Dungeon Master. Uses a default debug prompt when omitted.",
    )
    analysis: Optional[Dict] = Field(
        None,
        description="Optional analysis payload to pass into the DM context (defaults to a simple narrative stub).",
    )
    include_scene_context: bool = Field(
        default=True,
        description="Include scene integration context when available.",
    )
    include_conversation_context: bool = Field(
        default=True,
        description="Include conversation context built from history manager.",
    )
    force_audio: bool = Field(
        default=False,
        description="Force client audio generation even if auto-TTS is disabled.",
    )
    next_character_name: Optional[str] = Field(
        None,
        description="Name of the next character in turn order (for testing turn prompts).",
    )


def _get_session_manager(request: Request) -> SessionManager:
    session_manager = getattr(request.app.state, "session_manager", None)
    if not session_manager:
        raise HTTPException(status_code=500, detail="Session manager not initialized")
    return session_manager


def _get_orchestrator(request: Request) -> Orchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    return orchestrator


@router.post("/streaming-test")
async def debug_streaming_test(
    payload: StreamingTestRequest,
    request: Request,
    current_user=Depends(optional_auth),
):
    """Manually emit streaming narrative/player response chunks to connected clients."""

    # Ensure caller has access to the session (reuses optional auth logic).
    narrative = payload.narrative or (
        "The debug sun dips beneath the horizon, casting long shadows across the test field. "
        "Wind whistles through the placeholder trees as lanterns flicker to life."
    )
    response = payload.player_response or (
        "You feel the simulation shift, inviting you to explore the mocked scene. "
        "What action will you take to verify the streaming pipeline?"
    )

    # Broadcast narrative in two chunks for realism.
    midpoint = len(narrative) // 2
    narrative_chunks = [narrative[:midpoint], narrative[midpoint:]]
    for chunk in narrative_chunks:
        await campaign_broadcaster.broadcast_narrative_chunk(
            payload.session_id,
            chunk,
            is_final=False,
        )
    # Final empty chunk to signal completion.
    await campaign_broadcaster.broadcast_narrative_chunk(
        payload.session_id,
        "",
        is_final=True,
    )

    # Optional: generate audio using progressive client audio flow
    audio_summary: Optional[Dict[str, Any]] = None
    first_chunk_payload: Optional[Dict[str, Any]] = None

    if STREAMING_DEBUG_TTS_ENABLED and auto_tts_service.client_audio_enabled:
        logger = logging.getLogger(__name__)
        logger.info(
            "[DEBUG][stream] Generating progressive audio for session %s", payload.session_id
        )

        writer = PlaybackRequestWriter(
            session_id=payload.session_id,
            broadcaster=campaign_broadcaster,
            playback_group="narrative",
        )

        async def on_chunk_ready(chunk_artifact: Dict[str, Any]) -> None:
            nonlocal first_chunk_payload
            if first_chunk_payload is None and chunk_artifact.get("url"):
                first_chunk_payload = dict(chunk_artifact)

        try:
            audio_summary = await auto_tts_service.generate_audio_progressive(
                narrative,
                payload.session_id,
                on_chunk_ready=on_chunk_ready,
                force=False,
                playback_writer=writer,
            )

            if first_chunk_payload:
                provider = audio_summary.get("method") if isinstance(audio_summary, dict) else None
                if provider:
                    first_chunk_payload.setdefault("provider", provider)

                await campaign_broadcaster.broadcast_campaign_update(
                    payload.session_id,
                    "audio_available",
                    {
                        "campaign_id": payload.session_id,
                        "audio": first_chunk_payload,
                    },
                )
        except Exception as exc:  # pragma: no cover - debug only
            logger.error(
                "[DEBUG][stream] Failed to generate debug audio for session %s: %s",
                payload.session_id,
                exc,
                exc_info=True,
            )

    # Broadcast player response in two chunks as well.
    midpoint_resp = len(response) // 2
    response_chunks = [response[:midpoint_resp], response[midpoint_resp:]]
    for chunk in response_chunks:
        await campaign_broadcaster.broadcast_player_response_chunk(
            payload.session_id,
            chunk,
            is_final=False,
        )
    await campaign_broadcaster.broadcast_player_response_chunk(
        payload.session_id,
        "",
        is_final=True,
    )

    return {
        "success": True,
        "message": "Streaming debug chunks dispatched.",
        "narrative": narrative,
        "player_response": response,
        "audio_summary": audio_summary,
    }


@router.post("/run-dm")
async def debug_run_dm(
    payload: RunDmRequest,
    request: Request,
    current_user=Depends(optional_auth),
):
    """Trigger a Dungeon Master turn with a fixed prompt for debugging."""

    session_manager = _get_session_manager(request)
    try:
        session_context = await session_manager.get_or_create(payload.session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{payload.session_id}' not found.",
        ) from exc

    prompt = payload.prompt or (
        "DEBUG RUN: Please provide a concise scene update for automated validation. "
        "Use two sentences and mention the party checking their gear."
    )

    # Execute within the session lock to avoid concurrency issues.
    async with session_context.lock:
        result = await session_context.orchestrator.run_campaign(
            user_input=prompt,
            campaign_id=session_context.campaign_id,
            broadcaster=campaign_broadcaster,
        )
        session_context.touch()

    structured_data_raw = dict(result.get("structured_data") or {})

    # Audio is already handled by run_campaign internally via scene agents and streaming DM

    if structured_data_raw:
        result["structured_data"] = structured_data_raw

    return {
        "success": True,
        "message": "Dungeon Master executed with debug prompt.",
        "result_preview": result.get("structured_data", {}),
        "audio_summary": audio_summary,
    }


class QueueAudioTestRequest(BaseModel):
    session_id: str = Field(..., description="Campaign/session identifier to target")
    num_items: int = Field(default=3, ge=1, le=10, description="Number of audio items to queue (1-10)")
    use_sample_mp3s: bool = Field(default=True, description="Use existing sample mp3 files instead of TTS")


@router.post("/queue-audio-test")
async def debug_queue_audio_test(
    payload: QueueAudioTestRequest,
):
    """Queue multiple audio items for testing frontend playback (no auth required).

    This endpoint creates fake audio chunks using existing mp3 files to test
    the audio queue and playback system without requiring TTS generation.
    Useful for Playwright tests and debugging the frontend playback logic.
    """
    import os
    import uuid
    from pathlib import Path
    from gaia.infra.audio.audio_artifact_store import audio_artifact_store
    from gaia.infra.audio.audio_playback_service import audio_playback_service

    logger = logging.getLogger(__name__)
    logger.info(
        "[DEBUG][audio] Queueing %d test audio items for session %s (use_sample_mp3s=%s)",
        payload.num_items,
        payload.session_id,
        payload.use_sample_mp3s,
    )

    # Find sample mp3 files
    sample_dir = Path(__file__).parent.parent.parent.parent / "audio_samples"
    sample_files = list(sample_dir.glob("*.mp3")) if sample_dir.exists() else []

    if payload.use_sample_mp3s and not sample_files:
        raise HTTPException(
            status_code=500,
            detail=f"No sample mp3 files found in {sample_dir}",
        )

    # Create ONE writer for all chunks (simulates a single audio request)
    writer = PlaybackRequestWriter(
        session_id=payload.session_id,
        broadcaster=campaign_broadcaster,
        playback_group="narrative",
    )

    results = []
    chunk_ids = []  # Collect chunk IDs for frontend tracking

    for i in range(payload.num_items):
        if payload.use_sample_mp3s:
            # Use existing mp3 file
            sample_file = sample_files[i % len(sample_files)]

            # Read the mp3 file
            with open(sample_file, "rb") as f:
                audio_bytes = f.read()

            # Store it in the artifact store
            artifact = audio_artifact_store.persist_audio(
                session_id=payload.session_id,
                audio_bytes=audio_bytes,
                mime_type="audio/mpeg",
            )

            # Add chunk to the writer with proper sequence number and capture chunk_id
            chunk_id = await writer.add_chunk(
                artifact=artifact,
                sequence_number=i,
                text_preview=f"Debug audio item {i+1}/{payload.num_items} from {sample_file.name}",
            )

            if chunk_id:
                chunk_ids.append(chunk_id)

            logger.info(
                "[DEBUG][audio] Queued item %d/%d | file=%s size=%d bytes chunk_id=%s",
                i + 1,
                payload.num_items,
                sample_file.name,
                len(audio_bytes),
                chunk_id,
            )

            results.append({
                "item": i + 1,
                "source": sample_file.name,
                "artifact_id": artifact.id,
                "chunk_id": chunk_id,
                "request_id": str(writer.request_id),
                "size_bytes": len(audio_bytes),
            })

    # Finalize the request after all chunks are added
    # Create descriptive text for the audio request
    test_text = f"Debug audio test with {payload.num_items} item{'s' if payload.num_items > 1 else ''}"
    await writer.finalize(text=test_text)

    # Build the stream URL
    stream_url = f"/api/audio/stream/{payload.session_id}?request_id={writer.request_id}"

    return {
        "success": True,
        "message": f"Queued {payload.num_items} audio items for testing",
        "session_id": payload.session_id,
        "stream_url": stream_url,
        "request_id": str(writer.request_id),
        "chunk_ids": chunk_ids,  # Return chunk IDs for frontend tracking
        "items": results,
    }


@router.post("/run-streaming-direct")
async def debug_run_streaming_direct(
    payload: RunStreamingDirectRequest,
    request: Request,
    current_user=Depends(optional_auth),
):
    """Trigger the streaming DM runner directly, bypassing the full campaign runner."""

    session_manager = _get_session_manager(request)
    try:
        session_context = await session_manager.get_or_create(payload.session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{payload.session_id}' not found.",
        ) from exc

    prompt = payload.prompt or (
        "DEBUG STREAMING RUN: Provide a short atmospheric update describing what the party senses "
        "and hint at the next obstacle. Keep it under four sentences."
    )

    async with session_context.lock:
        orchestrator = session_context.orchestrator
        campaign_runner = orchestrator.campaign_runner

        analysis_payload = payload.analysis or {
            "routing": {"primary_agent": "DungeonMaster"},
            "overall": {"confidence_score": 1.0},
            "complexity": {"score": 5},
            "scene": {"primary_type": "NARRATIVE"},
        }
        try:
            analysis_str = json.dumps(analysis_payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:  # pragma: no cover - invalid payload
            raise HTTPException(
                status_code=400,
                detail=f"analysis payload is not JSON serializable: {exc}",
            ) from exc

        campaign_state = {
            "session_id": session_context.session_id,
            "history": campaign_runner.history_manager.get_recent_history()
            if hasattr(campaign_runner, "history_manager")
            else [],
        }

        scene_context_str = ""
        if payload.include_scene_context and getattr(campaign_runner, "scene_integration", None):
            try:
                scene_context_str = campaign_runner.scene_integration.get_scene_context_for_agents(
                    session_context.session_id
                )
            except Exception as exc:  # pragma: no cover - debug resilience
                scene_context_str = ""
                logger = logging.getLogger(__name__)
                logger.warning(
                    "[DEBUG][stream] Failed to build scene context for %s: %s",
                    session_context.session_id,
                    exc,
                )

        conversation_context = ""
        if payload.include_conversation_context and getattr(campaign_runner, "context_manager", None):
            try:
                conversation_context = campaign_runner.context_manager.build_conversation_context()
            except Exception as exc:  # pragma: no cover - debug resilience
                conversation_context = ""
                logger = logging.getLogger(__name__)
                logger.warning(
                    "[DEBUG][stream] Failed to build conversation context for %s: %s",
                    session_context.session_id,
                    exc,
                )

        dm_context = DMContext(
            analysis_output=analysis_str,
            player_input=prompt,
            campaign_state=campaign_state,
            game_config=campaign_runner._select_game_config_from_analysis(analysis_payload),
            scene_context=scene_context_str,
            conversation_context=conversation_context,
        )

        result = await campaign_runner.streaming_dm_runner.run_streaming(
            user_input=prompt,
            dm_context=dm_context,
            session_id=session_context.session_id,
            broadcaster=campaign_broadcaster,
            force_audio=payload.force_audio,
            next_character_name=payload.next_character_name,
        )

        session_context.touch()

    return {
        "success": True,
        "message": "Streaming DM executed directly.",
        "result": result,
    }
