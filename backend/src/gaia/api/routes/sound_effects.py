"""Sound effects API endpoints using ElevenLabs."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.src.flexible_auth import optional_auth
from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
from gaia.infra.audio.audio_artifact_store import audio_artifact_store
from gaia.infra.audio.sfx_service import sfx_service


router = APIRouter(prefix="/api/sfx", tags=["sound-effects"])
logger = logging.getLogger(__name__)


class SFXRequest(BaseModel):
    """Request model for sound effect generation."""

    text: str = Field(..., description="Description of the sound effect to generate")
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration in seconds (0.5-22). If None, API determines optimal duration.",
    )
    prompt_influence: float = Field(
        default=0.3,
        description="How closely to follow the prompt (0-1). Higher = more literal.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Campaign/session ID for broadcasting the audio",
    )


@router.post("/generate")
async def generate_sound_effect(
    request: SFXRequest,
    current_user=Depends(optional_auth),
):
    """Generate a sound effect from a text description using ElevenLabs.

    This endpoint generates sound effects that play simultaneously with narration
    at 50% volume. Sound effects are broadcast to all clients in the session.
    """
    logger.info(
        "🔊 SFX request: text='%s...' duration=%s",
        request.text[:50],
        request.duration_seconds,
    )

    try:
        if not sfx_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="Sound effects service not available. Please configure ELEVENLABS_API_KEY.",
            )

        # Generate the sound effect
        result = await sfx_service.generate_sound_effect(
            text=request.text,
            duration_seconds=request.duration_seconds,
            prompt_influence=request.prompt_influence,
        )

        audio_bytes = result.audio_bytes
        session_id = request.session_id or "default"

        # Persist the audio artifact
        artifact = audio_artifact_store.persist_audio(
            session_id=session_id,
            audio_bytes=audio_bytes,
            mime_type="audio/mpeg",
        )

        audio_payload = {
            "id": artifact.id,
            "session_id": session_id,
            "url": artifact.url,
            "mime_type": artifact.mime_type,
            "size_bytes": artifact.size_bytes,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            "duration_sec": result.duration_seconds,
            "provider": "elevenlabs_sfx",
            "playback_group": "sound_effects",
        }

        # Broadcast to all clients in the session
        if request.session_id:
            try:
                await campaign_broadcaster.broadcast_campaign_update(
                    request.session_id,
                    "sfx_available",
                    {
                        "campaign_id": request.session_id,
                        "audio": audio_payload,
                    },
                )
                logger.info("🔊 SFX broadcast to session %s", request.session_id)
            except Exception as exc:
                logger.warning(
                    "Failed to broadcast SFX for %s: %s",
                    request.session_id,
                    exc,
                )

        logger.info("🔊 ✅ SFX generated: %d bytes", len(audio_bytes))

        return {
            "status": "success",
            "message": "Sound effect generated successfully",
            "text": request.text,
            "audio": audio_payload,
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("🔊 ❌ SFX runtime error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("🔊 ❌ SFX generation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Sound effect generation failed: {str(e)}",
        )


@router.get("/availability")
async def get_sfx_availability(
    current_user=Depends(optional_auth),
):
    """Check if sound effects service is available."""
    try:
        return {
            "available": sfx_service.is_available(),
            "provider": "elevenlabs" if sfx_service.is_available() else None,
        }
    except Exception as e:
        logger.error("Failed to check SFX availability: %s", e)
        return {"available": False, "provider": None, "error": str(e)}
