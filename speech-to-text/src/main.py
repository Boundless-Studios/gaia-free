"""
Speech-to-Text Service Main Application
FastAPI application providing WebSocket and REST endpoints for audio transcription
"""

# Setup shared imports for auth and db submodules
from . import shared_imports

import logging
from fastapi import FastAPI, WebSocket, File, UploadFile, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import uvicorn
import os

from .config import get_settings
from .websocket_handlers import (
    handle_transcription_websocket,
    handle_simple_transcription_websocket,
    handle_scribe_v2_realtime_websocket
)
from .services.audio_recorder import get_audio_recorder

# Import authentication modules from gaia-auth
from auth.src.flexible_auth import (
    require_auth_if_available,
    optional_auth,
    is_auth_available,
    AUTH_AVAILABLE
)

# Import Auth0 JWT verifier
from .auth0_jwt_verifier import initialize_auth0_verifier, get_auth0_verifier

# Import WebSocket auth with Auth0 support
from .auth_websocket import websocket_auth

# Initialize settings
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Filter to suppress noisy health check and voice activity polling logs
class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        # Suppress GET /health logs from uvicorn access logger
        if '"GET /health' in message and '200' in message:
            return False
        # Suppress GET /stt/voice-activity logs (500ms polling)
        if '"GET /stt/voice-activity/' in message and '200' in message:
            return False
        # Suppress OPTIONS preflight requests (CORS)
        if '"OPTIONS /stt/voice-activity/' in message and '200' in message:
            return False
        return True


# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

# Create FastAPI app
app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description="Standalone Speech-to-Text service with voice activity detection"
)

# Add CORS middleware
def _build_cors_origins() -> list[str]:
    origins: list[str] = []
    # Local dev defaults
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    origins.extend(defaults)
    # Production/frontend domains
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)
    stt_public_url = os.getenv("STT_PUBLIC_URL")
    if stt_public_url:
        origins.append(stt_public_url)
    partyup_primary = os.getenv("PARTYUP_PRIMARY_ORIGIN", "https://your-domain.com")
    if partyup_primary:
        origins.append(partyup_primary)
    extra = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if extra:
        for item in extra.split(","):
            val = item.strip()
            if val:
                origins.append(val)
    # Dedup
    seen = set()
    unique = []
    for o in origins:
        if o not in seen:
            unique.append(o)
            seen.add(o)
    return unique

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "elevenlabs_configured": bool(settings.elevenlabs_api_key)
    }


@app.get("/stt/voice-activity/{session_id}")
async def get_voice_activity(session_id: str, current_user=require_auth_if_available()):
    """
    Get voice activity status for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        Voice activity status
    """
    from .websocket_handlers import get_voice_activity_status
    
    is_active = get_voice_activity_status(session_id)
    return {
        "session_id": session_id,
        "voice_active": is_active
    }


@app.post("/stt/transcribe/upload")
async def upload_and_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    current_user=require_auth_if_available()
):
    """Upload an audio file and transcribe it."""
    try:
        from .services.elevenlabs_stt import get_elevenlabs_stt_service
        
        # Read file content
        content = await file.read()
        
        # Get file extension
        file_ext = file.filename.split('.')[-1].lower()
        
        # Get ElevenLabs STT service
        stt_service = get_elevenlabs_stt_service()
        
        # Transcribe
        result = await stt_service.transcribe_audio(
            content,
            audio_format=file_ext
        )
        
        return {
            "filename": file.filename,
            "transcription": result["text"],
            "language": result.get("language", "en"),
            "duration": result.get("duration", 0)
        }
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stt/transcribe/session/{session_id}")
async def get_session_transcription(session_id: str, current_user=require_auth_if_available()):
    """Get transcription for a recording session."""
    audio_recorder = get_audio_recorder()
    
    status = audio_recorder.get_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    
    transcription = audio_recorder.get_transcription(session_id)
    
    return {
        "session_id": session_id,
        "status": status["status"],
        "transcription": transcription,
        "duration": status.get("duration", 0)
    }


@app.delete("/stt/transcribe/session/{session_id}")
async def delete_session(session_id: str, current_user=require_auth_if_available()):
    """Delete a recording session and its data."""
    audio_recorder = get_audio_recorder()
    
    if session_id not in audio_recorder.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Clean up session
    await audio_recorder.stop_session(session_id)
    
    return {"message": "Session deleted", "session_id": session_id}


@app.get("/stt/sessions")
async def list_sessions(current_user=require_auth_if_available()):
    """
    List all active recording sessions
    
    Returns:
        List of active sessions
    """
    audio_recorder = get_audio_recorder()
    sessions = audio_recorder.list_sessions()
    
    return {
        "count": len(sessions),
        "sessions": sessions
    }


@app.get("/stt/sessions/{session_id}")
async def get_session_info(session_id: str, current_user=require_auth_if_available()):
    """
    Get information about a specific session
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session information or 404 if not found
    """
    audio_recorder = get_audio_recorder()
    session_info = audio_recorder.get_session_info(session_id)
    
    if not session_info:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found"}
        )
    
    return session_info


@app.post("/stt/sessions/{session_id}/clear")
async def clear_session_buffer(session_id: str, current_user=require_auth_if_available()):
    """
    Clear the audio buffer for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        Success status
    """
    audio_recorder = get_audio_recorder()
    audio_recorder.clear_audio_buffer(session_id)
    
    return {
        "status": "success",
        "message": f"Audio buffer cleared for session {session_id}"
    }


@app.websocket("/stt/transcribe")
async def websocket_transcribe(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None)
):
    """
    WebSocket endpoint for simple audio transcription
    Send complete audio and receive transcription
    """
    # Authenticate WebSocket with Auth0 support
    user_info = await websocket_auth(websocket, token, authorization, cookie)
    if not user_info:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    await handle_simple_transcription_websocket(websocket, user_info)


@app.websocket("/stt/transcribe/continuous")
async def websocket_transcribe_continuous(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None)
):
    """
    WebSocket endpoint for continuous audio transcription
    Stream audio chunks and receive transcriptions in real-time
    Requires authentication via HttpOnly cookie or subprotocol header
    """
    # Authenticate WebSocket with Auth0 support
    user_info = await websocket_auth(websocket, token, authorization, cookie)
    if not user_info:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    await handle_transcription_websocket(websocket, user_info)


@app.websocket("/stt/transcribe/realtime")
async def websocket_transcribe_realtime_v2(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None)
):
    """
    WebSocket endpoint for real-time transcription using ElevenLabs Scribe V2
    Stream audio chunks and receive transcriptions with built-in VAD
    Requires authentication via HttpOnly cookie or subprotocol header
    """
    # Authenticate WebSocket with Auth0 support
    user_info = await websocket_auth(websocket, token, authorization, cookie)
    if not user_info:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    await handle_scribe_v2_realtime_websocket(websocket, user_info)


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"Starting {settings.service_name} v{settings.service_version}")
    logger.info(f"Listening on {settings.service_host}:{settings.service_port}")
    
    # Initialize Auth0 if configured
    auth0_initialized = initialize_auth0_verifier()
    if auth0_initialized:
        logger.debug("Auth0 authentication ENABLED for speech-to-text service")
    else:
        # Log legacy authentication status
        if AUTH_AVAILABLE:
            logger.info("Legacy authentication ENABLED for speech-to-text service")
        else:
            logger.info("Authentication DISABLED for speech-to-text service (DISABLE_AUTH=true)")
    
    if settings.elevenlabs_api_key:
        logger.info("ElevenLabs STT service configured and ready")
    else:
        logger.warning("ElevenLabs API key not configured - functionality limited")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info(f"Shutting down {settings.service_name}")


def main():
    """Run the application"""
    uvicorn.run(
        "src.main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=True,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
