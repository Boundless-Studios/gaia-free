# Setup shared imports for auth and db submodules
from src import shared_imports

from fastapi import FastAPI, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional, Set, List
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from pathlib import Path
import os
import re
import json
import time
import uuid
import base64
from datetime import datetime, timezone
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Setup logging first before any other imports that might use logger
from gaia_private.session.logging_config import setup_logging
logger = setup_logging()

# Initialize secrets cache (optional, one-time fetch from GCP)
from gaia.config.secrets import init_secrets_cache_from_gcp_if_configured

# Import Gaia modules
from gaia_private.orchestration.orchestrator import Orchestrator
from gaia.infra.llm.providers.ollama import ollama_manager
from gaia_private.session.session_manager import SessionManager, SessionNotFoundError
from gaia_private.session.session_registry import SessionRegistry
from gaia.api.schemas.session import (
    SessionShareRequest,
    SessionShareResponse,
    SessionJoinRequest,
    SessionJoinResponse,
)
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager

# Import authentication modules using flexible auth
from gaia.api.routes.auth import router as auth0_router
from gaia.api.routes.registration import router as registration_router
from auth.src.middleware import CurrentUser, ActiveUser, AdminUser, OptionalUser
from auth.src.flexible_auth import (
    require_auth_if_available,
    optional_auth,
    AUTH_AVAILABLE
)

if AUTH_AVAILABLE:
    logger.info("Authentication ENABLED")
else:
    logger.info("Authentication DISABLED (DISABLE_AUTH=true)")

# Import new modular components
from gaia.infra.audio.auto_tts_service import auto_tts_service
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter
# TTS server manager no longer needed - using external TTS service
from gaia.api.routes.campaigns import (
    CampaignService, CreateCampaignRequest, UpdateCampaignRequest,
    AutoFillCampaignRequest, AutoFillCharacterRequest,
    CampaignInitializeRequest, CharacterSlotRequest,
    CampaignGenerateRequest, CampaignQuickStartRequest, ArenaQuickStartRequest
)
from gaia.api.schemas.campaign import (
    ActiveCampaignResponse,
    PlayerCampaignResponse
)
from gaia.infra.audio.voice_registry import VoiceRegistry, VoiceProvider
from gaia.infra.audio.provider_manager import provider_manager
from gaia.api.routes.internal import router as internal_router
from gaia.api.routes.combat import router as combat_router
from gaia.api.routes.admin import router as admin_router
from gaia.api.routes.scene_admin import router as scene_admin_router
from gaia.api.routes.prompts import router as prompts_router

from gaia.api.routes.chat import router as chat_router
from gaia.api.routes.debug import router as debug_router
from gaia.api.routes.room import router as room_router
from gaia.api.routes.sound_effects import router as sfx_router
from gaia.connection.ws_helpers import (
    send_error_and_close,
    authenticate_ws_user,
    ws_message_loop,
)
from gaia.connection.websocket.audio_websocket_handler import AudioWebSocketHandler

def extract_narrative_for_tts(result: dict) -> Optional[str]:
    """Extract narrative text from API result for TTS."""
    if "structured_data" in result and "narrative" in result["structured_data"]:
        return result["structured_data"]["narrative"]
    return None

async def process_auto_tts(result: dict, session_id: str) -> dict:
    """Process auto-TTS for a result and add audio info if generated."""
    narrative_text = extract_narrative_for_tts(result)
    
    if narrative_text and auto_tts_service.enabled:
        logger.info("Processing auto-TTS")
        if auto_tts_service.client_audio_enabled:
            audio_info = await auto_tts_service.generate_audio(
                narrative_text,
                session_id,
                return_artifact=True
            )
            if isinstance(audio_info, dict) and audio_info.get("success", True):
                structured = dict(result.get("structured_data", {}) or {})
                structured["audio"] = audio_info
                result["structured_data"] = structured
        else:
            await auto_tts_service.generate_audio(narrative_text, session_id, return_artifact=False)
    
    return result

# Environment-driven WebSocket security configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("GAIA_ENV", "development")).lower()
IS_PROD = ENVIRONMENT in {"prod", "production"}

# In production, disallow token in query string by default
WS_ALLOW_QUERY_TOKEN = os.getenv(
    "WS_ALLOW_QUERY_TOKEN",
    "false" if IS_PROD else "true",
).lower() == "true"

# Enforce Origin allowlist checks on WS handshakes in production by default
WS_ENFORCE_ORIGIN = os.getenv(
    "WS_ENFORCE_ORIGIN",
    "true" if IS_PROD else "false",
).lower() == "true"

def _parse_allowed_origins() -> list[str]:
    # Priority: WS_ALLOWED_ORIGINS > CORS_ALLOWED_ORIGINS > ALLOWED_ORIGINS > built-in defaults
    raw = (
        os.getenv("WS_ALLOWED_ORIGINS")
        or os.getenv("CORS_ALLOWED_ORIGINS")
        or os.getenv("ALLOWED_ORIGINS")
    )
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    # Fallback to localhost-only for development (production origins should be set via env vars)
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

WS_ALLOWED_ORIGINS = _parse_allowed_origins()
logger.info(
    "[WS] Security config: ENV=%s ENFORCE_ORIGIN=%s ALLOW_QUERY_TOKEN=%s ALLOWED_ORIGINS=%s",
    ENVIRONMENT,
    WS_ENFORCE_ORIGIN,
    WS_ALLOW_QUERY_TOKEN,
    ",".join(WS_ALLOWED_ORIGINS[:6]) + ("…" if len(WS_ALLOWED_ORIGINS) > 6 else ""),
)

def _split_cors_allowlist(origins: list[str]) -> tuple[list[str], Optional[str]]:
    """Split allowlist into exact origins and a combined regex for wildcard entries."""
    exacts: list[str] = []
    regexes: list[str] = []
    for pattern in origins:
        p = pattern.strip()
        if not p:
            continue
        if "*" not in p:
            exacts.append(p)
            continue
        # Handle common wildcard forms like https://*.example.com
        try:
            if p.startswith("http://") or p.startswith("https://"):
                scheme, rest = p.split("://", 1)
                host_port = rest.split("/", 1)[0]
                if host_port.startswith("*."):
                    base = host_port[2:]
                    base_escaped = re.escape(base)
                    # Require at least one subdomain segment
                    regexes.append(fr"^{scheme}://([a-z0-9-]+\.)+{base_escaped}(?::\d+)?$")
                    continue
        except Exception:
            pass
        # Fallback: translate * to .*
        safe = re.escape(p).replace(r"\*", ".*")
        regexes.append(fr"^{safe}$")

    combined = "|".join(regexes) if regexes else None
    return exacts, combined

def _is_origin_allowed(origin_val: str | None) -> bool:
    if not origin_val:
        # No Origin: allow in non-prod (dev tools, local scripts), deny in prod
        return not WS_ENFORCE_ORIGIN
    try:
        from urllib.parse import urlparse
        o = urlparse(origin_val)
        if not o.scheme or not o.hostname:
            return False
        origin_scheme = o.scheme
        origin_host = o.hostname
        origin_port = f":{o.port}" if o.port else ""
        normalized = f"{origin_scheme}://{origin_host}{origin_port}"
    except Exception:
        return False

    for pattern in WS_ALLOWED_ORIGINS:
        p = pattern.strip()
        if not p:
            continue
        # Exact match first
        if normalized == p:
            return True
        # Wildcard subdomain support like https://*.example.com
        if "*" in p:
            try:
                po = urlparse(p.replace("*.", ""))
                if not po.scheme or not po.hostname:
                    continue
                if po.scheme != origin_scheme:
                    continue
                suffix = po.hostname
                # Accept apex or any subdomain
                if origin_host == suffix or origin_host.endswith("." + suffix):
                    return True
            except Exception:
                continue
    return False

# Global singleton instances
orchestrator: Optional[Orchestrator] = None
campaign_service: Optional[CampaignService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, campaign_service
    
    # Startup
    init_secrets_cache_from_gcp_if_configured()
    # Initialize database connection (optional in serverless staging)
    require_db = os.getenv("REQUIRE_DATABASE_ON_STARTUP", "true").strip().lower() not in {"0", "false", "no"}
    try:
        from db.src.connection import db_manager
        db_manager.initialize()
        if not await db_manager.test_connection():
            if require_db:
                logger.error("[CRITICAL] Database connection failed - cannot start without authentication")
                raise RuntimeError("Database connection required for authentication")
            logger.warning("[WARN] Database connection failed; continuing with limited features")
    except Exception as e:
        if require_db:
            logger.error(f"[CRITICAL] Could not initialize database: {e}")
            logger.error("[CRITICAL] Cannot start without authentication. Please configure database.")
            raise RuntimeError(f"Database initialization failed: {e}")
        logger.warning("Database initialization error ignored (REQUIRE_DATABASE_ON_STARTUP=false): %s", e)
    
    # Auth0 configuration is validated at runtime when tokens are verified
    # No pre-flight checks needed as Auth0 handles all authentication

    # Check for users with pending admin notifications and retry sending emails
    try:
        import sys
        from pathlib import Path
        # Add scripts directory to path for import
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from scripts.startup.check_pending_registrations import check_and_notify_pending_registrations
        await check_and_notify_pending_registrations()
    except Exception as e:
        logger.warning(f"Failed to check pending registrations: {e}", exc_info=True)
        # Don't fail startup if this check fails

    # Remote AI providers (Claude/Parasail) configured via environment variables

    # F5-TTS DISABLED - No longer logging audio paths or checking local TTS
    # from gaia.infra.audio.f5_tts_config import log_audio_paths
    # log_audio_paths()

    # F5-TTS DISABLED - No longer checking local TTS availability
    # from gaia.infra.audio.tts_service import tts_service
    # tts_service._check_local_tts()
    # logger.info(f"[OK] TTS service updated - Local TTS available: {tts_service.local_tts_available}")
    
    # Initialize the unified orchestrator
    orchestrator = Orchestrator()

    # Initialize WebSocket broadcasting system (will be configured with campaign_service later)
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
    orchestrator.campaign_broadcaster = campaign_broadcaster

    # Store orchestrator in app state for access in endpoints
    app.state.orchestrator = orchestrator
    session_registry = SessionRegistry()
    app.state.session_registry = session_registry
    app.state.session_manager = SessionManager(campaign_broadcaster=campaign_broadcaster)

    # Initialize room seats for campaigns seeded from filesystem
    # This runs after SessionRegistry._seed_db_from_memory() has populated campaign_sessions
    try:
        from scripts.startup.initialize_campaign_rooms import initialize_campaign_rooms
        room_init_stats = await initialize_campaign_rooms()
        if room_init_stats.get("campaigns_initialized", 0) > 0:
            logger.info(
                f"✅ Initialized rooms for {room_init_stats['campaigns_initialized']} campaigns "
                f"({room_init_stats['seats_created']} seats created)"
            )
    except Exception as e:
        logger.warning(f"Failed to initialize campaign rooms: {e}", exc_info=True)
        # Don't fail startup if room initialization fails

    # Background: prune idle sessions periodically
    # TTL and interval are environment-configurable; defaults keep memory tidy without being aggressive.
    prune_ttl_minutes = int(os.getenv("SESSION_PRUNE_TTL_MINUTES", "45"))
    prune_interval_seconds = int(os.getenv("SESSION_PRUNE_INTERVAL_SECONDS", "300"))

    async def _session_pruner(stop_event: asyncio.Event) -> None:
        logger.debug(
            "Session pruner started (ttl=%sm, interval=%ss)",
            prune_ttl_minutes,
            prune_interval_seconds,
        )
        while not stop_event.is_set():
            try:
                removed = await app.state.session_manager.prune_idle(prune_ttl_minutes)
                if removed:
                    logger.info("Pruned %d idle session(s)", removed)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Session pruner error: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=prune_interval_seconds)
            except asyncio.TimeoutError:
                continue

    app.state._session_pruner_stop = asyncio.Event()
    app.state._session_pruner_task = asyncio.create_task(_session_pruner(app.state._session_pruner_stop))
    
    # Initialize campaign service (singleton)
    campaign_service = CampaignService(orchestrator)

    # Inject campaign service into campaign broadcaster to avoid HTTP self-calls
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
    campaign_broadcaster._campaign_service = campaign_service

    # Start connection and audio cleanup background tasks
    from gaia.connection.cleanup import cleanup_task, audio_cleanup_task
    await cleanup_task.start()
    await audio_cleanup_task.start()

    yield
    
    # Shutdown
    logger.info("Shutting down Gaia API server...")

    # Stop connection and audio cleanup tasks
    try:
        from gaia.connection.cleanup import cleanup_task, audio_cleanup_task
        await cleanup_task.stop()
        await audio_cleanup_task.stop()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Error stopping cleanup tasks: %s", exc)

    # Stop session pruner
    try:
        stop_event = getattr(app.state, "_session_pruner_stop", None)
        task = getattr(app.state, "_session_pruner_task", None)
        if stop_event and task:
            stop_event.set()
            try:
                await asyncio.wait_for(task, timeout=5)
            except asyncio.TimeoutError:
                task.cancel()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Error stopping pruner: %s", exc)
    auto_tts_service.cleanup()
    # TTS server cleanup handled by external service
    logger.info("[OK] API server shutdown complete")

app = FastAPI(title="Gaia Web API", version="1.0.0", lifespan=lifespan)

# Include Auth0 endpoints
app.include_router(auth0_router)  # Auth0 authentication endpoints
logger.debug("Auth0 authentication endpoints registered")

# Include registration endpoints
app.include_router(registration_router)  # User registration flow endpoints
logger.info("Registration endpoints registered")

app.include_router(internal_router)  # Internal/debug endpoints
app.include_router(debug_router)  # Ad-hoc debugging utilities
app.include_router(chat_router)
app.include_router(room_router)  # Game room management endpoints
app.include_router(combat_router)  # Combat management endpoints
app.include_router(admin_router)  # Admin endpoints (email-restricted)
app.include_router(scene_admin_router)  # Scene inspection admin endpoints
app.include_router(prompts_router)  # Prompt management endpoints (admin-only)
app.include_router(sfx_router)  # Sound effects endpoints

# Add CORS middleware (wired to WS_ALLOWED_ORIGINS for consistency)
_cors_exacts, _cors_regex = _split_cors_allowlist(WS_ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_exacts,
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper function for session registration
def _register_campaign_session(campaign_id: str, result: dict, current_user) -> None:
    """Register a campaign session so the user can access campaign media (portraits, etc.)."""
    session_registry = getattr(app.state, "session_registry", None)
    if session_registry and current_user:
        owner_user_id = getattr(current_user, "user_id", None)
        owner_email = getattr(current_user, "email", None)

        # Try to get title from various possible locations in result
        title = (
            result.get("title") or
            result.get("name") or
            result.get("campaign_info", {}).get("title") or
            f"Campaign {campaign_id}"
        )

        session_registry.register_session(
            campaign_id,
            owner_user_id,
            title=title,
            owner_email=owner_email,
        )

# API endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint - no auth required for monitoring."""
    return {"status": "healthy", "service": "Gaia Web API"}

@app.get("/api/health/runware")
async def runware_health_check():
    """Health check for Runware service"""
    from gaia.infra.image.providers.runware import get_runware_image_service
    
    runware_service = get_runware_image_service()
    
    if not runware_service:
        return {
            "status": "unavailable",
            "reason": "service_not_configured",
            "configured": False,
            "connected": False,
            "available_models": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    try:
        # Test connection
        await runware_service.connect()
        await runware_service.disconnect()
        
        return {
            "status": "healthy",
            "configured": True,
            "connected": True,
            "available_models": len(runware_service.get_available_models()),
            "sdk_available": runware_service.get_model_info().get("sdk_available", False),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "reason": str(e),
            "configured": True,
            "connected": False,
            "available_models": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/api/images/models")
async def get_available_models():
    """Get list of available image generation models from all services"""
    from gaia.infra.image.image_service_manager import get_image_service_manager

    manager = get_image_service_manager()
    if not manager:
        return {"models": []}

    return manager.get_available_models()

@app.get("/api/combat/actions")
async def get_combat_actions(
    current_user = optional_auth()
):
    """Get all available combat action definitions.

    Frontend can cache these definitions and reference them by name
    in combat session data.
    """
    from core.models.combat.mechanics.action_definitions import (
        STANDARD_ACTIONS,
        ActionName,
        ActionType,
    )

    # Convert to dict format for API response
    actions = {}
    for action in STANDARD_ACTIONS:
        action_name = action.name.value if isinstance(action.name, ActionName) else action.name
        action_type = (
            action.action_type.value
            if isinstance(action.action_type, ActionType)
            else action.action_type
        )

        actions[action_name] = {
            "cost": action.cost,
            "description": action.description,
            "action_type": action_type,
            "prerequisites": action.prerequisites,
            "attack_bonus": action.attack_bonus,
            "damage_dice": action.damage_dice,
            "save_dc": action.save_dc,
            "requires_target": action.requires_target,
            "grants_effect": action.grants_effect
        }

    return {
        "actions": actions,
        "version": "1.0",
        "cache_hint": "static"  # Hint to frontend that these can be cached indefinitely
    }

@app.post("/api/test")
async def test_endpoint(
    request: Request,
    current_user = optional_auth()
):
    """Test endpoint to verify connectivity."""
    logger.info("🔍 Test endpoint called")
    logger.info(f"🔍 Request method: {request.method}")
    logger.info(f"🔍 Request URL: {request.url}")
    logger.info(f"🔍 Request headers: {dict(request.headers)}")
    
    body = await request.body()
    logger.info(f"🔍 Request body length: {len(body)} bytes")
    logger.info(f"🔍 Request body: {body}")
    
    return {"status": "test_successful", "message": "Test endpoint reached successfully"}

# Auto-TTS control endpoints
@app.get("/api/tts/auto/status")
async def get_auto_tts_status(
    current_user = optional_auth()
):
    """Get auto-TTS configuration status."""
    return {
        "enabled": auto_tts_service.enabled,
        "voice": auto_tts_service.default_voice,
        "speed": auto_tts_service.speed,
        "output_method": auto_tts_service.output_method
    }

@app.post("/api/tts/auto/toggle")
async def toggle_auto_tts(
    current_user = require_auth_if_available()
):
    """Toggle auto-TTS on/off - requires authentication if available."""
    enabled = auto_tts_service.toggle_enabled()
    return {"enabled": enabled, "message": f"Auto-TTS {'enabled' if enabled else 'disabled'}"}

@app.post("/api/tts/auto/voice/{voice}")
async def set_auto_tts_voice(
    voice: str,
    current_user = require_auth_if_available()
):
    """Set the auto-TTS voice - requires authentication if available."""
    
    # Validate voice exists
    if not VoiceRegistry.get_voice(voice):
        available_voices = [v.id for v in VoiceRegistry.list_voices()]
        raise HTTPException(
            status_code=400, 
            detail=f"Voice '{voice}' not found. Available voices: {available_voices}"
        )
    
    auto_tts_service.set_voice(voice)
    return {"voice": voice, "message": f"Auto-TTS voice set to {voice}"}

@app.post("/api/tts/auto/speed/{speed}")
async def set_auto_tts_speed(
    speed: float,
    current_user = require_auth_if_available()
):
    """Set the auto-TTS speed - requires authentication if available."""
    auto_tts_service.set_speed(speed)
    return {"speed": auto_tts_service.speed, "message": f"Auto-TTS speed set to {auto_tts_service.speed}"}

def get_default_voice_based_on_availability():
    """Get the default voice based on available TTS providers using centralized provider manager."""
    return provider_manager.get_default_voice()

# ElevenLabs TTS endpoints
class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = Field(default_factory=get_default_voice_based_on_availability)  # Dynamic default based on availability
    speed: float = 1.0
    session_id: Optional[str] = None


class TTSQueueRequest(BaseModel):
    session_id: Optional[str] = None

@app.post("/api/tts/synthesize")
async def synthesize_tts(
    request: TTSRequest,
    current_user = Depends(optional_auth)
):
    """Synthesize speech using TTS service with progressive delivery - optional authentication."""
    logger.info(f"🎵 TTS request: voice={request.voice} text_len={len(request.text)}")

    # Validate that a voice is provided
    if not request.voice:
        raise HTTPException(
            status_code=400,
            detail="No voice specified and no default voice available. Please check your TTS configuration."
        )

    try:
        from gaia.infra.audio.tts_service import tts_service
        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

        # Use progressive delivery if session_id provided
        if request.session_id:
            # Use PlaybackRequestWriter for chunk persistence and broadcasting
            writer = PlaybackRequestWriter(
                session_id=request.session_id,
                broadcaster=campaign_broadcaster,
                playback_group="narrative",
            )

            # Generate progressively
            summary = await tts_service.synthesize_speech_progressive(
                text=request.text,
                voice=request.voice,
                speed=request.speed,
                session_id=request.session_id,
                playback_writer=writer,
            )

            logger.info(
                "[AUDIO][TTS] Progressive synthesis complete session=%s provider=%s chunks=%s request_id=%s",
                request.session_id,
                summary.get("method") if isinstance(summary, dict) else None,
                summary.get("total_chunks") if isinstance(summary, dict) else None,
                writer.request_id,
            )

            # Build stream URL for frontend playback
            stream_url = f"/api/audio/stream/{request.session_id}?request_id={writer.request_id}"

            return {
                "status": "success",
                "message": f"Audio generated progressively using {summary.get('method')} TTS",
                "voice": request.voice,
                "text_length": len(request.text),
                "tts_method": summary.get("method"),
                "total_chunks": summary.get("total_chunks", 0),
                "progressive": True,
                "request_id": str(writer.request_id),
                "stream_url": stream_url,
                "session_id": request.session_id,
            }

        # Fallback to old non-progressive path if no session_id
        persist_artifact = False
        tts_result = await tts_service.synthesize_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            session_id=None,
            persist=persist_artifact,
            play=True,
        )
        audio_data = tts_result.audio_bytes
        tts_method = tts_result.method
        audio_payload = None
        if tts_result.artifact:
            payload = tts_result.artifact.to_payload()
            payload["provider"] = tts_method
            audio_payload = payload
        elif audio_data:
            inline_id = f"inline-{uuid.uuid4().hex}"
            mime_type = "audio/mpeg"
            b64_audio = base64.b64encode(audio_data).decode("ascii")
            data_url = f"data:{mime_type};base64,{b64_audio}"
            audio_payload = {
                "id": inline_id,
                "session_id": request.session_id or "default",
                "url": data_url,
                "mime_type": mime_type,
                "size_bytes": len(audio_data),
                "created_at": datetime.utcnow().isoformat(),
                "duration_sec": None,
                "provider": tts_method,
            }
        
        if audio_data:
            # Save to temporary file
            import tempfile
            from pathlib import Path
            
            # Use appropriate storage path and filename based on TTS method
            if tts_method == "local":
                audio_storage = os.getenv('AUDIO_STORAGE_PATH', os.path.join(tempfile.gettempdir(), 'gaia_local_tts'))
                temp_dir = Path(audio_storage) / "local_tts"
                filename = f"local_{hash(request.text)}.mp3"
            elif tts_method == "elevenlabs":
                audio_storage = os.getenv('AUDIO_STORAGE_PATH', os.path.join(tempfile.gettempdir(), 'gaia_elevenlabs_tts'))
                temp_dir = Path(audio_storage) / "elevenlabs_tts"
                filename = f"elevenlabs_{hash(request.text)}.mp3"
            elif tts_method == "openai":
                audio_storage = os.getenv('AUDIO_STORAGE_PATH', os.path.join(tempfile.gettempdir(), 'gaia_openai_tts'))
                temp_dir = Path(audio_storage) / "openai_tts"
                filename = f"openai_{hash(request.text)}.mp3"
            else:
                # Fallback for unknown method
                audio_storage = os.getenv('AUDIO_STORAGE_PATH', os.path.join(tempfile.gettempdir(), 'gaia_tts'))
                temp_dir = Path(audio_storage) / "tts"
                filename = f"tts_{hash(request.text)}.mp3"
            
            temp_dir.mkdir(parents=True, exist_ok=True)
            file_path = temp_dir / filename
            
            with open(file_path, "wb") as f:
                f.write(audio_data)
            
            # Note: The TTS service already handles queueing of individual chunks
            # We don't need to queue the combined audio file
            queue_status = {"status": "skipped", "message": "Queueing handled by TTS service"}
            
            # Log successful completion
            logger.info(f"🎵 ✅ TTS completed: method={tts_method} size={len(audio_data)}b")

            # Return immediately to avoid frontend timeout
            response_payload = {
                "status": "success",
                "message": f"Audio generated using {tts_method} TTS and queued for playback",
                "file_path": str(file_path),
                "file_size": len(audio_data),
                "voice": request.voice,
                "text_length": len(request.text),
                "tts_method": tts_method,
                "queue_status": queue_status
            }
            if audio_payload:
                response_payload["audio"] = audio_payload
                if request.session_id:
                    try:
                        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
                        await campaign_broadcaster.broadcast_campaign_update(
                            request.session_id,
                            "audio_available",
                            {
                                "campaign_id": request.session_id,
                                "audio": audio_payload,
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to broadcast synthesized audio for %s: %s", request.session_id, exc)
            return response_payload
        elif audio_payload:
            response_payload = {
                "status": "success",
                "message": f"Audio generated using {tts_method} TTS",
                "voice": request.voice,
                "text_length": len(request.text),
                "tts_method": tts_method,
                "queue_status": {"status": "queued", "message": "Artifact persisted for session playback"},
                "audio": audio_payload,
            }
            if request.session_id:
                try:
                    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
                    await campaign_broadcaster.broadcast_campaign_update(
                        request.session_id,
                        "audio_available",
                        {
                            "campaign_id": request.session_id,
                            "audio": audio_payload,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to broadcast synthesized audio for %s: %s", request.session_id, exc)
            return response_payload
        else:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
            
    except Exception as e:
        logger.error(f"🎵 ❌ TTS failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@app.get("/api/tts/queue/status")
async def get_audio_queue_status(
    session_id: Optional[str] = Query(default=None),
    current_user = optional_auth()
):
    """Get current audio queue status."""
    from gaia.infra.audio.audio_queue_manager import audio_queue_manager
    return audio_queue_manager.get_queue_status(session_id=session_id)

@app.post("/api/tts/queue/clear")
async def clear_audio_queue(
    request: TTSQueueRequest = Body(default=TTSQueueRequest()),
    current_user = require_auth_if_available()
):
    """Clear all pending audio from the queue - requires authentication if available."""
    from gaia.infra.audio.audio_queue_manager import audio_queue_manager
    return await audio_queue_manager.clear_queue(session_id=request.session_id)

@app.post("/api/tts/queue/stop")
async def stop_audio_playback(
    request: TTSQueueRequest = Body(default=TTSQueueRequest()),
    current_user = require_auth_if_available()
):
    """Stop current audio playback and clear the queue - requires authentication if available."""
    from gaia.infra.audio.audio_queue_manager import audio_queue_manager
    return await audio_queue_manager.stop_current(session_id=request.session_id)

@app.get("/api/tts/voices")
async def get_available_voices(
    current_user = optional_auth()
):
    """Get list of available TTS voices."""
    try:
        from gaia.infra.audio.tts_service import tts_service
        voices = tts_service.get_available_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Failed to get voices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get voices: {str(e)}")

@app.get("/api/characters/voices")
async def get_character_voices(
    current_user = optional_auth()
):
    """Get list of available character voices formatted for character management."""
    try:
        voices = []
        
        # Get all ElevenLabs voices from registry
        for voice in VoiceRegistry.list_voices(VoiceProvider.ELEVENLABS):
            voices.append({
                "voice_id": voice.id,
                "display_name": voice.name,
                "attributes": {
                    "gender": voice.gender or "neutral",
                    "age": "adult",  # Default age since not in Voice model
                    "tone": voice.style or "neutral"
                },
                "description": voice.description
            })
        
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Failed to get character voices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get character voices: {str(e)}")

@app.get("/api/tts/availability")
async def get_tts_availability(
    current_user = optional_auth()
):
    """Get current TTS availability status and recheck local TTS server."""
    try:
        from gaia.infra.audio.tts_service import tts_service
        
        # Recheck all TTS availability (this may have changed since startup)
        availability_status = tts_service.recheck_availability()
        
        # Check if ElevenLabs API key is configured
        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        
        availability = {
            "elevenlabs": {
                "available": availability_status["elevenlabs"],
                "api_key_configured": bool(elevenlabs_api_key)
            },
            "openai": {
                "available": availability_status["openai"],
                "client_configured": bool(tts_service.openai_client)
            },
            "timestamp": time.time()
        }
        
        return availability
    except Exception as e:
        logger.error(f"Failed to get TTS availability: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get TTS availability: {str(e)}")

@app.get("/api/tts/providers")
async def get_available_providers(
    current_user = optional_auth()
):
    """Get list of available TTS providers with recommended default."""
    try:
        provider_info = provider_manager.get_provider_info()
        recommended_provider = provider_manager.get_recommended_provider_for_frontend()
        
        # Convert to frontend format
        providers = []
        for provider_id, info in provider_info.items():
            if info['available']:
                provider_map = {
                    'local': {'name': 'Local', 'icon': '🏠', 'description': 'Local F5-TTS server'},
                    'elevenlabs': {'name': 'ElevenLabs', 'icon': '🎤', 'description': 'ElevenLabs cloud TTS'},
                    'openai': {'name': 'OpenAI', 'icon': '🤖', 'description': 'OpenAI TTS'}
                }
                
                display_info = provider_map.get(provider_id, {
                    'name': provider_id.title(), 
                    'icon': '🎵', 
                    'description': f'{provider_id.title()} TTS'
                })
                
                providers.append({
                    "id": provider_id,
                    "name": display_info['name'],
                    "icon": display_info['icon'],
                    "description": display_info['description'],
                    "available": True,
                    "voice_count": info['voice_count'],
                    "default_voice": info['default_voice']
                })
        
        return {
            "providers": providers,
            "recommended_provider": recommended_provider
        }
        
    except Exception as e:
        logger.error(f"Failed to get providers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get providers: {str(e)}")


# Image generation endpoint
class GenerateImageRequest(BaseModel):
    prompt: str
    campaign_id: Optional[str] = None
    image_type: str = "scene"
    model: Optional[str] = None  # Add optional model parameter

@app.post("/api/generate-image")
async def generate_image_old(
    request: GenerateImageRequest,
    http_request: Request,
    current_user = require_auth_if_available()
):
    """Generate an image based on the provided prompt - requires authentication if available."""
    global orchestrator
    
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    logger.info(f"🎨 Image generation request: {request.image_type} for campaign {request.campaign_id}")
    
    # Verify model if specified (but don't switch/reload)
    if request.model:
        from gaia.infra.image.image_config import get_image_config
        
        config = get_image_config()
        if request.model in config.get_all_models():
            # Just verify the model is valid and log which one we're using
            # Don't switch/reload the model since it should already be loaded from dropdown selection
            logger.info(f"Using model: {request.model} for image generation")
        else:
            logger.warning(f"Unknown model specified: {request.model}, using current model")
    
    try:
        # Use the unified entry point - routing logic is handled inside ImageGenerator
        image_result = await orchestrator.image_generator.generate(
            prompt=request.prompt,
            image_type=request.image_type,
            style="fantasy art",
            session_id=request.campaign_id,
        )
        
        # Handle success/failure
        if not image_result.get('success'):
            return {"success": False, "error": image_result.get('error', 'Failed to generate image')}

        # Save metadata and add API URL
        from gaia.infra.image.image_metadata import get_metadata_manager

        metadata_manager = get_metadata_manager()
        storage_filename = image_result.get("storage_filename") or os.path.basename(image_result.get("local_path", "") or "")
        metadata_payload = {
            "prompt": request.prompt,
            "type": image_result.get("type", request.image_type),
            "service": image_result.get('service', 'Unknown'),
            "style": image_result.get("style", "fantasy art"),
            "original_prompt": image_result.get("original_prompt", request.prompt),
            "proxy_url": image_result.get("proxy_url") or image_result.get("image_url"),
            "storage_path": image_result.get("storage_path"),
            "storage_bucket": image_result.get("storage_bucket"),
            "local_path": image_result.get("local_path"),
            "gcs_uploaded": image_result.get("gcs_uploaded"),
            "mime_type": image_result.get("mime_type"),
        }
        metadata_manager.save_metadata(
            storage_filename or f"image_{datetime.utcnow().timestamp():.0f}.png",
            metadata_payload,
            campaign_id=request.campaign_id or "default",
        )
        
        return {"success": True, "image": image_result}
        
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Removed duplicate endpoint - using the one with path parameter instead

@app.get("/api/images")
async def list_recent_images(
    limit: int = 10,
    campaign_id: Optional[str] = None,
    current_user = optional_auth()
):
    """List recent images for a specific campaign."""
    from gaia.infra.image.image_metadata import get_metadata_manager
    from gaia.infra.image.image_artifact_store import image_artifact_store
    
    metadata_manager = get_metadata_manager()
    image_files = []

    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id is required")

    # Get images from specific campaign
    campaign_images = metadata_manager.list_campaign_images(campaign_id)
    for img_metadata in campaign_images[:limit]:
        proxy_url = img_metadata.get('proxy_url') or img_metadata.get('image_url')
        storage_path = img_metadata.get('storage_path')
        if not proxy_url and storage_path:
            try:
                rel = Path(storage_path)
                base = Path(image_artifact_store.base_path) if getattr(image_artifact_store, 'base_path', None) else None
                rel = rel.relative_to(base) if base else rel
                proxy_url = f"/api/images/{rel.as_posix()}"
            except Exception:
                proxy_url = None
        proxy_url = proxy_url or f"/api/images/{img_metadata.get('filename', '')}"
        image_data = {
            "filename": img_metadata.get('filename', ''),
            "path": proxy_url,
            "proxy_url": proxy_url,
            "modified": datetime.fromisoformat(img_metadata.get('timestamp', '')).timestamp() if img_metadata.get('timestamp') else 0,
            "size": img_metadata.get('size', 0),
            "timestamp": img_metadata.get('timestamp', ''),
            "prompt": img_metadata.get('prompt', ''),
            "type": img_metadata.get('type', 'scene'),
            "model": img_metadata.get('model', ''),
            "campaign_id": img_metadata.get('campaign_id', campaign_id),
            "storage_path": img_metadata.get('storage_path'),
            "storage_bucket": img_metadata.get('storage_bucket'),
        }
        image_files.append(image_data)
    
    return {"images": image_files}

# Campaign management endpoints
@app.get("/api/campaigns")
async def list_campaigns(
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "last_played",
    ascending: bool = False,
    current_user = optional_auth()
):
    """List all available campaigns."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign service not initialized")
    
    return await campaign_service.list_campaigns(limit, offset, sort_by, ascending)

@app.post("/api/campaigns")
async def create_campaign(
    request: CreateCampaignRequest,
    current_user = require_auth_if_available()
):
    """Create a new campaign - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")

    # Create the campaign
    owner_user_id = getattr(current_user, "user_id", None) if current_user else None
    owner_email = getattr(current_user, "email", None) if current_user else None
    result = await campaign_service.create_campaign(
        request,
        owner_user_id=owner_user_id,
        owner_email=owner_email,
    )

    # Register the session for media access
    campaign_id = result.get("campaign_id") or result.get("id")
    if campaign_id:
        _register_campaign_session(campaign_id, result, current_user)

    return result

@app.get("/api/campaigns/{campaign_id}")
async def load_campaign(
    campaign_id: str,
    request: Request,
    current_user = optional_auth()
):
    """Load a specific campaign."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")

    result = await campaign_service.load_campaign(campaign_id)

    # Register pre-generated campaigns when first loaded
    session_registry = getattr(request.app.state, "session_registry", None)
    if session_registry and current_user:
        owner_user_id = getattr(current_user, "user_id", None)
        owner_email = getattr(current_user, "email", None)

        # Register if not already registered (important for pre-generated campaigns)
        if not session_registry.get_metadata(campaign_id):
            title = result.get("title") or result.get("name") or f"Campaign {campaign_id}"
            session_registry.register_session(
                campaign_id,
                owner_user_id,
                title=title,
                owner_email=owner_email,
            )

    return result

@app.post("/api/campaigns/{campaign_id}/save")
async def save_campaign(
    campaign_id: str,
    auto_save: bool = False,
    current_user = require_auth_if_available()
):
    """Save current campaign state - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.save_campaign(campaign_id, auto_save)

@app.post("/api/campaigns/{campaign_id}/audio/cancel")
async def cancel_audio_playback(
    campaign_id: str,
    request_id: Optional[str] = None,
    current_user = require_auth_if_available()
):
    """Cancel audio playback request(s) for a campaign.

    Allows frontend to explicitly stop playback instead of relying on timeouts.
    Useful for "skip" or "stop" buttons.

    Args:
        campaign_id: Campaign/session identifier
        request_id: Optional specific request ID to cancel. If not provided, cancels all pending/streaming requests.
        current_user: Authentication required if available

    Returns:
        Status and count of cancelled requests
    """
    from gaia.infra.audio.audio_playback_service import audio_playback_service
    from sqlalchemy import select, and_
    from gaia.infra.audio.audio_models import AudioPlaybackRequest

    # Verify session access if user is authenticated
    session_registry = getattr(app.state, "session_registry", None)
    if session_registry and current_user:
        user_id = getattr(current_user, "user_id", None)
        if user_id and not session_registry.has_access(campaign_id, user_id):
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this campaign"
            )

    if not audio_playback_service.db_enabled:
        raise HTTPException(status_code=503, detail="Audio playback database not available")

    if request_id:
        # Cancel specific request
        try:
            request_uuid = uuid.UUID(request_id)

            # Verify request belongs to this campaign before canceling
            session = audio_playback_service._get_session()
            if session:
                stmt = select(AudioPlaybackRequest).where(
                    AudioPlaybackRequest.request_id == request_uuid
                )
                request_obj = session.execute(stmt).scalar_one_or_none()
                session.close()

                if not request_obj:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Request {request_id} not found"
                    )

                if request_obj.campaign_id != campaign_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request {request_id} does not belong to campaign {campaign_id}"
                    )
            success = audio_playback_service.cancel_request(request_uuid)

            if success:
                # Broadcast cancellation to all connections
                from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
                await campaign_broadcaster.broadcast_campaign_update(
                    campaign_id,
                    "audio_playback_cancelled",
                    {
                        "request_id": request_id,
                        "campaign_id": campaign_id,
                    }
                )
                return {
                    "status": "success",
                    "message": f"Cancelled audio request {request_id}",
                    "cancelled_count": 1,
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"Request {request_id} not found or already completed",
                    "cancelled_count": 0,
                }
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid request_id format: {request_id}")
    else:
        # Cancel all pending/streaming requests for this campaign
        queue = audio_playback_service.get_playback_queue(campaign_id)
        cancelled_count = 0

        for req in queue:
            if req["status"] in ["pending", "generating", "playing"]:
                req_id = uuid.UUID(req["request_id"])
                if audio_playback_service.cancel_request(req_id):
                    cancelled_count += 1

        if cancelled_count > 0:
            # Broadcast cancellation to all connections
            from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
            await campaign_broadcaster.broadcast_campaign_update(
                campaign_id,
                "audio_playback_cancelled",
                {
                    "campaign_id": campaign_id,
                    "all_requests": True,
                }
            )

        return {
            "status": "success",
            "message": f"Cancelled {cancelled_count} audio request(s)",
            "cancelled_count": cancelled_count,
        }

@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current_user = require_auth_if_available()
):
    """Delete a campaign - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.delete_campaign(campaign_id)

@app.patch("/api/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    request: UpdateCampaignRequest,
    current_user = require_auth_if_available()
):
    """Update campaign metadata - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.update_campaign(campaign_id, request)

@app.post("/api/campaigns/import")
async def import_legacy_campaigns(
    current_user = require_auth_if_available()
):
    """Import legacy chat history files - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.import_legacy_campaigns()

@app.get("/api/campaigns/{campaign_id}/structured-data")
async def get_structured_data(
    campaign_id: str,
    limit: int = 10,
    current_user = optional_auth()
):
    """Get structured data for a campaign."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.get_structured_data(campaign_id, limit)

@app.get("/api/campaigns/{campaign_id}/structured-data/summary")
async def get_structured_data_summary(
    campaign_id: str,
    current_user = optional_auth()
):
    """Get a summary of structured data for a campaign."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.get_structured_data_summary(campaign_id)

@app.get("/api/campaigns/{campaign_id}/files")
async def get_campaign_file_info(
    campaign_id: str,
    current_user = optional_auth()
):
    """Get information about files associated with a campaign."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.get_campaign_file_info(campaign_id)

# Character endpoints
@app.get("/api/characters/pregenerated")
async def list_pregenerated_characters(
    current_user = optional_auth()
):
    """Get all pre-generated characters."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.list_pregenerated_characters()

@app.post("/api/characters/generate")
async def auto_fill_character(
    request: AutoFillCharacterRequest,
    current_user = require_auth_if_available()
):
    """Auto-fill a character slot with pre-generated data - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.auto_fill_character(request)

# Portrait generation endpoints
class PortraitGenerateRequest(BaseModel):
    """Request model for portrait generation."""
    character_id: str
    campaign_id: str
    regenerate: bool = False
    custom_prompt_additions: Optional[str] = None
    character_data: Optional[dict] = None  # For generating portraits during character creation

class VisualUpdateRequest(BaseModel):
    """Request model for updating character visuals."""
    gender: Optional[str] = None
    age_category: Optional[str] = None
    build: Optional[str] = None
    height_description: Optional[str] = None
    facial_expression: Optional[str] = None
    facial_features: Optional[str] = None
    attire: Optional[str] = None
    primary_weapon: Optional[str] = None
    distinguishing_feature: Optional[str] = None
    background_setting: Optional[str] = None
    pose: Optional[str] = None

@app.post("/api/characters/{character_id}/portrait/generate")
async def generate_character_portrait(
    character_id: str,
    portrait_request: PortraitGenerateRequest,
    request: Request,
    current_user = optional_auth()
):
    """Generate a portrait for a character."""
    try:
        # Try to get character manager from active session first
        session_manager = getattr(request.app.state, "session_manager", None)
        character_manager = None

        if session_manager:
            try:
                session_context = await session_manager.get_or_create(portrait_request.campaign_id)
                if session_context and hasattr(session_context, 'orchestrator'):
                    orchestrator = session_context.orchestrator
                    if hasattr(orchestrator, 'character_manager'):
                        character_manager = orchestrator.character_manager
            except Exception:
                pass  # Fall back to creating a new CharacterManager

        # If no active session or no character manager, get singleton for this campaign
        if not character_manager:
            manager = SimpleCampaignManager()
            character_manager = manager.get_character_manager(portrait_request.campaign_id)

        # Ensure the current user is registered as a participant for media access
        session_registry = getattr(request.app.state, "session_registry", None)
        if session_registry and portrait_request.campaign_id:
            user_id = getattr(current_user, "user_id", None) if current_user else None
            user_email = getattr(current_user, "email", None) if current_user else None
            if user_id or user_email:
                try:
                    session_registry.touch_session(
                        portrait_request.campaign_id,
                        user_id,
                        user_email=user_email,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Failed to touch session for portrait access (campaign=%s): %s",
                        portrait_request.campaign_id,
                        exc,
                    )

        # Generate portrait
        result = await character_manager.generate_character_portrait(
            character_id=character_id,
            custom_additions=portrait_request.custom_prompt_additions,
            character_data=portrait_request.character_data
        )

        return result
    except Exception as e:
        logger.error(f"Failed to generate portrait: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate portrait: {str(e)}")

@app.get("/api/characters/{character_id}/portrait")
async def get_character_portrait(
    character_id: str,
    request: Request,
    campaign_id: str = Query(..., description="Campaign ID"),
    current_user = optional_auth()
):
    """Get portrait information for a character."""
    try:
        # Try to get character manager from active session first
        session_manager = getattr(request.app.state, "session_manager", None)
        character_manager = None

        if session_manager:
            try:
                session_context = await session_manager.get_or_create(campaign_id)
                if session_context and hasattr(session_context, 'orchestrator'):
                    orchestrator = session_context.orchestrator
                    if hasattr(orchestrator, 'character_manager'):
                        character_manager = orchestrator.character_manager
            except Exception:
                pass  # Fall back to creating a new CharacterManager

        # If no active session or no character manager, get singleton for this campaign
        if not character_manager:
            manager = SimpleCampaignManager()
            character_manager = manager.get_character_manager(campaign_id)

        # Get portrait info
        result = character_manager.get_character_portrait(character_id)

        return result
    except Exception as e:
        logger.error(f"Failed to get portrait: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get portrait: {str(e)}")

@app.patch("/api/characters/{character_id}")
async def update_character_visuals(
    character_id: str,
    visual_request: VisualUpdateRequest,
    http_request: Request,
    campaign_id: str = Query(..., description="Campaign ID"),
    current_user = optional_auth()
):
    """Update character visual metadata."""
    try:
        # Try to get character manager from active session first
        session_manager = getattr(http_request.app.state, "session_manager", None)
        character_manager = None

        if session_manager:
            try:
                session_context = await session_manager.get_or_create(campaign_id)
                if session_context and hasattr(session_context, 'orchestrator'):
                    orchestrator = session_context.orchestrator
                    if hasattr(orchestrator, 'character_manager'):
                        character_manager = orchestrator.character_manager
            except Exception:
                pass  # Fall back to creating a new CharacterManager

        # If no active session or no character manager, get singleton for this campaign
        if not character_manager:
            manager = SimpleCampaignManager()
            character_manager = manager.get_character_manager(campaign_id)

        # Update visuals
        visual_data = visual_request.model_dump(exclude_none=True)
        result = character_manager.update_character_visuals(character_id, visual_data)

        return result
    except Exception as e:
        logger.error(f"Failed to update character visuals: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update character visuals: {str(e)}")

@app.get("/api/campaigns/{campaign_id}/characters")
async def get_campaign_characters(
    campaign_id: str,
    http_request: Request,
    current_user = optional_auth()
):
    """Get all characters in a campaign with enriched data (profiles + campaign state)."""
    try:
        # Try to get character manager from active session first
        session_manager = getattr(http_request.app.state, "session_manager", None)
        character_manager = None

        if session_manager:
            try:
                session_context = await session_manager.get_or_create(campaign_id)
                if session_context and hasattr(session_context, 'orchestrator'):
                    orchestrator = session_context.orchestrator
                    if hasattr(orchestrator, 'character_manager'):
                        character_manager = orchestrator.character_manager
            except Exception:
                pass  # Fall back to creating a new CharacterManager

        # If no active session or no character manager, get singleton for this campaign
        if not character_manager:
            manager = SimpleCampaignManager()
            character_manager = manager.get_character_manager(campaign_id)

        # Get all player characters
        player_characters = character_manager.get_player_characters()

        # Enrich each character with profile data
        enriched_characters = []
        for character_info in player_characters:
            try:
                enriched = character_manager.get_enriched_character(character_info.character_id)
                enriched_characters.append(enriched.to_dict())
            except Exception as e:
                logger.error(f"Failed to enrich character {character_info.character_id}: {e}")
                continue

        return {
            "success": True,
            "campaign_id": campaign_id,
            "characters": enriched_characters
        }
    except Exception as e:
        logger.error(f"Failed to get campaign characters: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get campaign characters: {str(e)}")

@app.post("/api/campaigns/generate")
async def auto_fill_campaign(
    request: AutoFillCampaignRequest,
    current_user = require_auth_if_available()
):
    """Auto-fill campaign with pre-generated data - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.auto_fill_campaign(request)

@app.post("/api/campaigns/initialize")
async def initialize_campaign(
    request: CampaignInitializeRequest,
    current_user = require_auth_if_available()
):
    """Initialize a campaign with full context and send the opening prompt - requires authentication if available."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")

    # Initialize the campaign
    result = await campaign_service.initialize_campaign(request)

    # Register the session for media access
    _register_campaign_session(request.campaign_id, result, current_user)

    return result

@app.post("/api/arena/quick-start")
async def arena_quick_start(
    request: ArenaQuickStartRequest,
    current_user = require_auth_if_available()
):
    """Quick-start an arena combat session with 2 players vs 2 NPCs (requires authentication if available)."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    # Check if user is authenticated when auth is enabled
    if AUTH_AVAILABLE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required for arena combat")
    user_id = getattr(current_user, "user_id", "anonymous")
    return await campaign_service.arena_quick_start(request, user_id)

@app.get("/api/images/{filename:path}")
async def serve_image(
    filename: str,
    current_user = optional_auth()
):
    """Serve images from GCS or local storage using metadata paths."""
    from pathlib import Path
    from fastapi.responses import Response, FileResponse
    from gaia.infra.image.image_artifact_store import image_artifact_store

    actual_filename = os.path.basename(filename)
    image_path = None

    # Try metadata lookup first - it has the exact storage_path and bucket
    try:
        from gaia.infra.image.image_metadata import get_metadata_manager
        meta = get_metadata_manager().get_metadata(actual_filename)

        if meta:
            # If image is in GCS, fetch it directly using the metadata's storage_path
            storage_bucket = meta.get('storage_bucket')
            storage_path = meta.get('storage_path')
            gcs_uploaded = meta.get('gcs_uploaded', False)

            if gcs_uploaded and storage_bucket and storage_path and image_artifact_store.uses_gcs:
                try:
                    blob = image_artifact_store._bucket.blob(storage_path)  # type: ignore[union-attr]
                    if blob.exists():
                        image_bytes = blob.download_as_bytes()
                        ext = Path(actual_filename).suffix.lower().lstrip('.')
                        mime_type = meta.get('mime_type') or f"image/{ext}" if ext else "image/png"
                        return Response(
                            content=image_bytes,
                            media_type=mime_type,
                            headers={"Cache-Control": "public, max-age=31536000, immutable"}
                        )
                except Exception as exc:
                    logger.error(f"Failed to fetch from GCS {storage_bucket}/{storage_path}: {exc}")

            # Try local paths from metadata
            raw_path = (
                meta.get('local_path')
                or meta.get('session_media_path')
                or meta.get('absolute_path')
                or meta.get('path')
            )
            if raw_path:
                candidate = Path(os.path.expanduser(raw_path))
                if candidate.exists() and candidate.is_file():
                    image_path = candidate
    except Exception as exc:
        logger.warning(f"Metadata lookup failed for {actual_filename}: {exc}")

    if image_path is None:
        # Parse session id from common storage path formats and fall back to image store
        session_id = None
        parts = Path(filename).parts
        for part in parts:
            if re.match(r"(campaign_\d+)", part):
                session_id = part
                break

        if session_id:
            storage_filename = os.path.basename(filename)
            try:
                image_bytes = image_artifact_store.read_artifact_bytes(session_id, storage_filename)
                ext = Path(storage_filename).suffix.lower().lstrip(".") or "png"
                mime_type = f"image/{ext}"
                logger.debug(
                    "Serving image via artifact store fallback session=%s filename=%s path=%s",
                    session_id,
                    storage_filename,
                    filename,
                )
                return Response(
                    content=image_bytes,
                    media_type=mime_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
            except FileNotFoundError:
                logger.debug(
                    "Artifact store fallback miss session=%s filename=%s path=%s",
                    session_id,
                    storage_filename,
                    filename,
                )
            except Exception as exc:
                logger.warning(
                    "Artifact store fallback failed session=%s filename=%s path=%s err=%s",
                    session_id,
                    storage_filename,
                    filename,
                    exc,
                )

    if image_path is None:
        # Handle different path formats and legacy global location
        if filename.startswith('home/') or filename.startswith('/home/'):
            # Handle absolute paths that were stripped of leading slash
            image_path = Path('/' + filename.lstrip('/'))
        elif filename.startswith('/'):
            # Already absolute path
            image_path = Path(filename)
        elif filename.startswith('tmp/gaia_images/'):
            # Handle legacy paths that are missing the leading slash
            image_path = Path('/' + filename)
        else:
            # Otherwise check image storage directory for just filename
            image_path = Path(os.path.expanduser(os.getenv('IMAGE_STORAGE_PATH', '/tmp/gaia_images'))) / filename

    # Verify the path exists and is an image
    if image_path and image_path.exists() and image_path.is_file():
        if image_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            # Strong caching for generated images (filenames are content-addressed/unique per generation)
            return FileResponse(
                path=str(image_path),
                media_type=f"image/{image_path.suffix[1:]}",
                headers={
                    "Cache-Control": "public, max-age=31536000, immutable"
                },
            )

    # Log for debugging
    logger.error(f"Image not found: {filename} (actual_filename={actual_filename})")
    raise HTTPException(status_code=404, detail=f"Image not found: {filename}")

@app.get("/api/structured-campaigns/{campaign_id}")
async def load_structured_campaign(
    campaign_id: str,
    current_user = optional_auth()
):
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    return await campaign_service.load_structured_campaign(campaign_id)

@app.get("/api/simple-campaigns/{campaign_id}")
async def load_simple_campaign(
    campaign_id: str,
    request: Request,
    current_user = optional_auth()
):
    """Load a campaign using the session-based architecture.

    This endpoint uses the SessionManager to ensure proper session isolation
    and activates the campaign in a dedicated orchestrator instance.
    """
    session_manager = getattr(request.app.state, "session_manager", None)
    if not session_manager:
        raise HTTPException(status_code=500, detail="Session manager not initialized")

    session_registry = getattr(request.app.state, "session_registry", None)

    # Normalize campaign ID to extract bare campaign_<number> from directory names
    def _normalize_id(raw_id: str) -> str:
        if not raw_id:
            return raw_id
        match = re.match(r"(campaign_\d+)", raw_id.strip())
        return match.group(1) if match else raw_id.strip()

    normalized_campaign_id = _normalize_id(campaign_id)

    # Check if campaign exists before allowing access
    # This prevents creating empty campaigns when accessing non-existent URLs
    manager = SimpleCampaignManager()
    campaign_dir = manager.storage.resolve_session_dir(normalized_campaign_id, create=False)

    if campaign_dir is None:
        logger.warning(f"Campaign not found: {normalized_campaign_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Campaign not found: {normalized_campaign_id}",
        )

    _enforce_session_access(session_registry, normalized_campaign_id, current_user)

    try:
        # Get or create a session context for this campaign (use normalized ID)
        session_context = await session_manager.get_or_create(normalized_campaign_id)

        async with session_context.lock:
            orchestrator = session_context.orchestrator
            already_active = (
                getattr(orchestrator, "active_campaign_id", None) == normalized_campaign_id
            )
            if already_active:
                activated = True
            else:
                activated = await orchestrator.activate_campaign(normalized_campaign_id)
            session_context.touch()

            # Register and update session registry (use normalized ID)
            if session_registry and current_user:
                owner_user_id = getattr(current_user, "user_id", None)
                owner_email = getattr(current_user, "email", None)

                # Register the session if it's not already registered
                # This is important for pre-generated campaigns
                if not session_registry.get_metadata(normalized_campaign_id):
                    session_registry.register_session(
                        normalized_campaign_id,
                        owner_user_id,
                        title=f"Campaign {normalized_campaign_id}",
                        owner_email=owner_email,
                    )
                else:
                    session_registry.touch_session(
                        normalized_campaign_id,
                        owner_user_id,
                        user_email=owner_email,
                    )

        if not activated:
            raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

        # Use the session-scoped orchestrator without mutating the global service
        global campaign_service
        if not campaign_service:
            raise HTTPException(status_code=500, detail="Campaign service not initialized")

        result = await campaign_service.load_simple_campaign(
            normalized_campaign_id,
            orchestrator=session_context.orchestrator,
        )
        if session_registry:
            meta = session_registry.get_metadata(normalized_campaign_id)
            if meta:
                display_name = meta.get("name") or meta.get("title")
                if display_name:
                    result["name"] = display_name
        return result

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    except Exception as e:
        logger.error(f"Error loading simple campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load campaign: {str(e)}")

@app.get("/api/simple-campaigns/{campaign_id}/read", response_model=PlayerCampaignResponse)
async def read_simple_campaign(
    campaign_id: str,
    request: Request,
    current_user = optional_auth()
):
    """Read campaign data without activating it (for player view)."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")

    # Check if campaign exists before allowing access
    # Use resolve_session_dir with create=False for O(1) filesystem check instead of loading all campaigns
    manager = SimpleCampaignManager()
    campaign_dir = manager.storage.resolve_session_dir(campaign_id, create=False)

    if campaign_dir is None:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign not found: {campaign_id}",
        )

    session_registry = getattr(request.app.state, "session_registry", None)
    _enforce_session_access(session_registry, campaign_id, current_user)

    resp = await campaign_service.read_campaign_structured(campaign_id)

    # Enrich with session display name if present in registry
    try:
        session_registry: Optional[SessionRegistry] = getattr(request.app.state, "session_registry", None)
    except Exception:
        session_registry = None
    if session_registry:
        meta = session_registry.get_metadata(campaign_id)
        if meta:
            display_name = meta.get("name") or meta.get("title")
            if display_name:
                try:
                    resp.name = display_name
                except Exception:
                    pass
    return resp

@app.get("/api/active-campaign", response_model=ActiveCampaignResponse)
async def get_active_campaign(
    current_user = optional_auth()
):
    """Get the currently active campaign ID from the orchestrator."""
    global campaign_service
    if not campaign_service:
        raise HTTPException(status_code=500, detail="Campaign endpoints not initialized")
    
    base = await campaign_service.get_active_campaign_structured()
    # Enrich with display name if available
    name: Optional[str] = None
    if base.active_campaign_id:
        try:
            session_registry: Optional[SessionRegistry] = getattr(app.state, "session_registry", None)  # type: ignore[name-defined]
        except Exception:
            session_registry = None
        if session_registry:
            meta = session_registry.get_metadata(base.active_campaign_id)
            if meta:
                name = meta.get("name") or meta.get("title")
    return ActiveCampaignResponse(active_campaign_id=base.active_campaign_id, name=name)

def _collect_simple_campaigns(
    request: Request,
    current_user,
    role: Optional[str] = None,
) -> list[dict]:
    """Gather campaign metadata from storage, optionally filtered by role."""
    campaign_storage = os.getenv("CAMPAIGN_STORAGE_PATH")
    if not campaign_storage:
        raise ValueError(
            "CAMPAIGN_STORAGE_PATH environment variable is not set. "
            "Please set it to your campaign storage directory."
        )

    session_registry: Optional[SessionRegistry] = getattr(request.app.state, "session_registry", None)

    def _normalize_email(value: object) -> Optional[str]:
        if isinstance(value, str):
            return value.strip().lower()
        return None

    def _parse_ts(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except Exception:  # noqa: BLE001
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed

    def _max_iso(*values: Optional[str]) -> Optional[str]:
        parsed = [_parse_ts(v) for v in values]
        parsed = [p for p in parsed if p is not None]
        if not parsed:
            return None
        return max(parsed).isoformat()

    current_user_id = getattr(current_user, "user_id", None) if current_user else None
    current_user_email = getattr(current_user, "email", None) if current_user else None

    normalized_user_email = _normalize_email(current_user_email)
    session_memberships: Set[str] = set()
    raw_session_memberships: Set[str] = set()
    if session_registry and (current_user_id or current_user_email):
        session_memberships = session_registry.get_sessions_for_user(
            user_id=current_user_id,
            user_email=current_user_email,
        )
        raw_session_memberships = set(session_memberships)
        if session_memberships:
            normalized_memberships: Set[str] = set()
            for membership_id in session_memberships:
                if not isinstance(membership_id, str):
                    continue
                candidate = membership_id.strip()
                if not candidate:
                    continue
                normalized_memberships.add(candidate)
                match = re.match(r"(campaign_\d+)", candidate)
                if match:
                    normalized_memberships.add(match.group(1))
            session_memberships = normalized_memberships

    campaigns: list[dict] = []
    seen_campaign_ids: Set[str] = set()
    manager = SimpleCampaignManager()
    base_listing = manager.list_campaigns(limit=5000).get("campaigns", [])

    for entry in base_listing:
        campaign_id = entry.get("id") or entry.get("session_id")
        if not campaign_id:
            continue

        directory_name = entry.get("directory") or entry.get("name") or campaign_id
        display_name = entry.get("name") or campaign_id
        entry_last_played = entry.get("last_played")
        entry_last_loaded = entry.get("last_loaded_at")
        entry_last_messaged = entry.get("last_messaged_at")
        last_played = entry_last_played

        item = {
            "id": campaign_id,
            "session_id": campaign_id,
            "name": display_name,
            "directory": directory_name,
            "last_played": last_played,
            "last_loaded_at": entry_last_loaded,
            "last_messaged_at": entry_last_messaged,
            "message_count": entry.get("message_count", 0),
        }
        seen_campaign_ids.add(campaign_id)

        if session_registry:
            metadata = session_registry.get_metadata(campaign_id)
            if metadata:
                owner_user_id = metadata.get("owner_user_id")
                owner_email = metadata.get("owner_email")
                normalized_owner_email = _normalize_email(owner_email)

                if owner_user_id:
                    item["owner_user_id"] = owner_user_id
                if owner_email:
                    item["owner_email"] = owner_email
                members = metadata.get("member_emails") or metadata.get("member_user_ids", [])
                item["members"] = members
                item["created_at"] = metadata.get("created_at")
                registry_last_accessed = metadata.get("last_accessed_at")
                item["last_accessed_at"] = registry_last_accessed
                # Use 'name' only for display
                meta_name = metadata.get("name")
                if meta_name:
                    item["name"] = meta_name

                is_owner = (
                    (owner_user_id and owner_user_id == current_user_id)
                    or (
                        normalized_owner_email
                        and normalized_user_email
                        and normalized_owner_email == normalized_user_email
                    )
                )
                item["is_owner"] = is_owner

                is_member = False
                if members and isinstance(members, list):
                    normalized_members = [_normalize_email(m) if isinstance(m, str) else None for m in members]
                    is_member = (
                        (current_user_id and current_user_id in members)
                        or (normalized_user_email and normalized_user_email in normalized_members)
                    )

                # New filtering logic based on role
                if role == 'dm':
                    if not is_owner:
                        continue  # For DMs, only show owned campaigns
                elif role == 'player':
                    if not is_owner and not is_member:
                        continue  # For Players, show campaigns they own or are a member of

                # Update last played/loaded fields with registry data if newer
                latest_loaded = _max_iso(entry_last_loaded, registry_last_accessed)
                if latest_loaded:
                    item["last_loaded_at"] = latest_loaded
                latest_played = _max_iso(entry_last_played, entry_last_messaged, item.get("last_messaged_at"), latest_loaded)
                if latest_played:
                    item["last_played"] = latest_played
            else:
                # No metadata in registry - skip if a role filter is active
                if role:
                    continue
                latest_played = _max_iso(entry_last_played, entry_last_messaged, entry_last_loaded)
                if latest_played:
                    item["last_played"] = latest_played
        else:
            # No session_registry - skip if a role filter is active
            if role:
                continue
            latest_played = _max_iso(entry_last_played, entry_last_messaged, entry_last_loaded)
            if latest_played:
                item["last_played"] = latest_played

        campaigns.append(item)

    if session_registry and raw_session_memberships:
        for raw_id in raw_session_memberships:
            if not isinstance(raw_id, str):
                continue
            candidate = raw_id.strip()
            if not candidate:
                continue
            base_match = re.match(r"(campaign_\d+)", candidate)
            canonical_id = base_match.group(1) if base_match else candidate
            if canonical_id in seen_campaign_ids:
                continue
            metadata = session_registry.get_metadata(candidate)
            if not metadata and canonical_id != candidate:
                metadata = session_registry.get_metadata(canonical_id)
            if not metadata:
                continue
            display_name = (
                metadata.get("name")
                or metadata.get("title")
                or canonical_id
            )
            last_loaded = metadata.get("last_loaded_at")
            last_accessed = metadata.get("last_accessed_at")
            last_played = _max_iso(
                metadata.get("last_played"),
                metadata.get("last_messaged_at"),
                last_loaded,
                last_accessed,
            )
            if not last_played:
                last_played = metadata.get("created_at")
            item = {
                "id": canonical_id,
                "session_id": canonical_id,
                "name": display_name,
                "directory": metadata.get("legacy_directory") or candidate,
                "last_played": last_played,
                "last_loaded_at": last_loaded or last_accessed,
                "last_messaged_at": metadata.get("last_messaged_at"),
                "message_count": metadata.get("message_count", 0),
            }
            owner_user_id = metadata.get("owner_user_id")
            owner_email = metadata.get("owner_email")
            if owner_user_id:
                item["owner_user_id"] = owner_user_id
            if owner_email:
                item["owner_email"] = owner_email
            members = metadata.get("member_emails") or metadata.get("member_user_ids", [])
            if members:
                item["members"] = members
            item["created_at"] = metadata.get("created_at")
            item["last_accessed_at"] = last_accessed

            normalized_owner_email = _normalize_email(owner_email)
            is_owner = (
                normalized_owner_email
                and normalized_user_email
                and normalized_owner_email == normalized_user_email
            )
            item["is_owner"] = is_owner

            is_member = canonical_id in session_memberships

            # New filtering logic based on role
            if role == 'dm':
                if not is_owner:
                    continue
            elif role == 'player':
                if not is_owner and not is_member:
                    continue

            seen_campaign_ids.add(canonical_id)
            campaigns.append(item)

    # Sort campaigns by last_played timestamp (newest first)
    # Campaigns without last_played go to the end
    def _sort_key(campaign: dict) -> tuple:
        last_played_str = campaign.get("last_played")
        if not last_played_str:
            # No timestamp - sort to the end (use minimum datetime)
            return (datetime.min.replace(tzinfo=timezone.utc),)
        parsed = _parse_ts(last_played_str)
        if parsed is None:
            # Invalid timestamp - sort to the end
            return (datetime.min.replace(tzinfo=timezone.utc),)
        return (parsed,)

    campaigns.sort(key=_sort_key, reverse=True)

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📋 Returning {len(campaigns)} campaigns (role={role})")

    return campaigns


def _enforce_session_access(
    session_registry: Optional[SessionRegistry],
    session_id: str,
    current_user,
) -> None:
    """Ensure the caller is authorized to access the session if claims exist.

    Notes:
    - Treat a "dummy" user object with no identifiers (no user_id and no email)
      as unauthenticated. Tests inject such an object, and the expected behavior
      is a 401 for unauthenticated callers (not 403).
    """
    if not session_registry or not session_id:
        return

    metadata = session_registry.get_metadata(session_id)
    if not metadata:
        return

    user_id = getattr(current_user, "user_id", None) if current_user else None
    user_email = getattr(current_user, "email", None) if current_user else None

    # Consider the request authenticated only if at least one identifier is present
    is_authenticated = bool(user_id or user_email)

    if session_registry.is_authorized(
        session_id,
        user_id=user_id,
        user_email=user_email,
    ):
        return

    if is_authenticated:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this session",
        )

    raise HTTPException(
        status_code=401,
        detail="Authentication required to access this session",
    )


@app.get("/api/media/{session_id}/{media_type}/{filename:path}")
async def serve_session_media(
    session_id: str,
    media_type: str,
    filename: str,
    request: Request,
    token: Optional[str] = Query(default=None),
    current_user = optional_auth(),
):
    """Serve media files associated to a session using metadata resolution.

    We do NOT store binaries under campaign/session directories to avoid repo bloat.
    This endpoint validates ACLs, then resolves the file path via metadata and serves it.
    """
    # For audio files, skip ACL enforcement (audio files are scoped to sessions already)
    # Note: Audio files use GCS signed URLs (900s TTL) when available - see audio_artifact_store.py
    if media_type != "audio":
        # Enforce access for non-audio media
        session_registry = getattr(request.app.state, "session_registry", None)
        _enforce_session_access(session_registry, session_id, current_user)

    # For audio files, try audio artifact store first
    if media_type == "audio":
        try:
            from gaia.infra.audio.audio_artifact_store import audio_artifact_store
            audio_path = audio_artifact_store.resolve_local_path(session_id, filename)
            if audio_path.exists() and audio_path.is_file():
                media_suffix = audio_path.suffix.lower().lstrip('.')
                media_map = {'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'ogg': 'audio/ogg'}
                media_type_header = media_map.get(media_suffix, 'audio/mpeg')
                return FileResponse(path=str(audio_path), media_type=media_type_header)
        except Exception as exc:
            logger.debug("Audio artifact resolution failed: %s", exc)

    # Resolve via metadata (campaign-specific) for other media types
    try:
        from gaia.infra.image.image_metadata import get_metadata_manager
        meta = get_metadata_manager().get_metadata(os.path.basename(filename), campaign_id=session_id)
        if meta:
            path = (
                meta.get('local_path')
                or meta.get('session_media_path')
                or meta.get('absolute_path')
                or meta.get('path')
            )
            if path:
                candidate = Path(os.path.expanduser(path))
                if candidate.exists() and candidate.is_file():
                    media_suffix = candidate.suffix.lower().lstrip('.')
                    media_map = {
                        'png': 'image/png',
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'gif': 'image/gif',
                        'webp': 'image/webp',
                        'mp3': 'audio/mpeg',
                        'wav': 'audio/wav',
                        'ogg': 'audio/ogg',
                    }
                    media_type_header = media_map.get(media_suffix, 'application/octet-stream')
                    return FileResponse(path=str(candidate), media_type=media_type_header)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Session media resolution failed: %s", exc)

    raise HTTPException(status_code=404, detail="Media file not found for session")


@app.post("/api/sessions/share", response_model=SessionShareResponse)
async def share_session(
    payload: SessionShareRequest,
    request: Request,
    current_user: ActiveUser,
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    session_registry: Optional[SessionRegistry] = getattr(
        request.app.state, "session_registry", None
    )
    if not session_registry:
        raise HTTPException(
            status_code=500, detail="Session registry not initialized on server"
        )

    # Normalize session ID to extract bare campaign_<number> from directory names
    def _normalize_id(raw_id: str) -> str:
        if not raw_id:
            return raw_id
        match = re.match(r"(campaign_\d+)", raw_id.strip())
        return match.group(1) if match else raw_id.strip()

    normalized_session_id = _normalize_id(payload.session_id)

    metadata = session_registry.get_metadata(normalized_session_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Session not found")

    owner_id = metadata.get("owner_user_id")
    owner_email = metadata.get("owner_email")
    user_id = getattr(current_user, "user_id", None)
    user_email = getattr(current_user, "email", None)
    user_email_norm = (
        user_email.strip().lower() if isinstance(user_email, str) else None
    )

    owner_email_norm = (
        owner_email.strip().lower() if isinstance(owner_email, str) else None
    )

    # Only check email for ownership - user_id is deprecated
    is_owner = False
    if owner_email_norm and user_email_norm and owner_email_norm == user_email_norm:
        is_owner = True

    if owner_email and not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Only the session owner can create invite links",
        )

    # Claim ownership if none recorded yet
    if not (owner_id or owner_email) and (user_id or user_email):
        session_registry.register_session(
            normalized_session_id,
            owner_user_id=user_id,
            title=metadata.get("name") or metadata.get("title"),
            owner_email=user_email,
        )

    if payload.regenerate:
        session_registry.invalidate_invites(normalized_session_id)

    try:
        result = session_registry.create_invite_token(
            normalized_session_id,
            created_by=user_id,
            created_by_email=user_email,
            expires_in_minutes=payload.expires_in_minutes,
            multi_use=payload.multi_use,
            max_uses=payload.max_uses,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SessionShareResponse(
        session_id=payload.session_id,
        invite_token=result["token"],
        expires_at=result.get("expires_at"),
    )


@app.post("/api/sessions/join", response_model=SessionJoinResponse)
async def join_session(
    payload: SessionJoinRequest,
    request: Request,
    current_user: ActiveUser,
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    session_registry: Optional[SessionRegistry] = getattr(
        request.app.state, "session_registry", None
    )
    if not session_registry:
        raise HTTPException(
            status_code=500, detail="Session registry not initialized on server"
        )

    result = session_registry.consume_invite_token(
        payload.invite_token,
        user_id=getattr(current_user, "user_id", None),
        user_email=getattr(current_user, "email", None),
    )

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Invite token is invalid, already used, or expired"
        )

    # Normalize session ID to ensure consistency
    def _normalize_id(raw_id: str) -> str:
        if not raw_id:
            return raw_id
        match = re.match(r"(campaign_\d+)", raw_id.strip())
        return match.group(1) if match else raw_id.strip()

    session_id = _normalize_id(result["session_id"])
    # Touch session to update last accessed timestamp
    session_registry.touch_session(
        session_id,
        getattr(current_user, "user_id", None),
        user_email=getattr(current_user, "email", None),
    )

    return SessionJoinResponse(session_id=session_id)


@app.get("/api/simple-campaigns")
async def list_simple_campaigns(
    request: Request,
    current_user = optional_auth(),
    role: Optional[str] = Query(default=None),
):
    campaigns = _collect_simple_campaigns(request, current_user, role)
    return {"campaigns": campaigns, "count": len(campaigns)}


@app.get("/api/sessions/mine")
async def list_user_sessions(
    request: Request,
    current_user = optional_auth(),
):
    if not current_user:
        return {"sessions": [], "count": 0}

    # This endpoint is for the DM view, so we use role='dm'
    sessions = _collect_simple_campaigns(request, current_user, role='dm')
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/campaigns/{campaign_id}/connected-players")
async def get_connected_players(
    campaign_id: str,
    current_user = optional_auth(),
):
    """Get list of players currently connected to a campaign session."""
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

    # TODO: Add permission check - only DM or players in session should see this
    connected = campaign_broadcaster.get_connected_players(campaign_id)
    return {
        "success": True,
        "campaign_id": campaign_id,
        "connected_players": connected,
        "count": len(connected)
    }

# Image generation endpoints
class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str = "black-forest-labs-flux-pro"
    size: str = "1024x1024"
    style: str = "fantasy art"
    image_type: str = "scene"
    campaign_id: Optional[str] = None

@app.post("/api/images/generate")
async def generate_image(
    request: ImageGenerationRequest,
    current_user = require_auth_if_available()
):
    """Generate an image using ImageServiceManager - requires authentication if available."""
    logger.info(f"Received image generation request: model={request.model}, type={request.image_type}")

    try:
        from gaia.infra.image.image_service_manager import get_image_service_manager

        # Get the image service manager
        manager = get_image_service_manager()
        if not manager:
            raise HTTPException(status_code=503, detail="Image service manager not available")

        # Enhance prompt with style
        enhanced_prompt = f"{request.prompt}, {request.style} style"

        # Parse size
        width, height = map(int, request.size.split('x'))

        # Generate image through manager (it routes to the appropriate provider)
        result = await manager.generate_image(
            prompt=enhanced_prompt,
            width=width,
            height=height,
            response_format="url",
            model=request.model
        )

        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error")
            raise HTTPException(status_code=500, detail=error_msg)

        images = result.get("images", [])
        if images:
            image_data = images[0]

            # Get the saved path directly from the result
            saved_path = image_data.get("path") or image_data.get("local_path")

            # Save metadata for the image
            if saved_path:
                from gaia.infra.image.image_metadata import get_metadata_manager
                metadata_manager = get_metadata_manager()
                filename = os.path.basename(saved_path)
                metadata_manager.save_metadata(
                    filename,
                    {
                        "prompt": request.prompt,  # Original prompt without enhancement
                        "enhanced_prompt": enhanced_prompt,
                        "type": request.image_type,
                        "model": request.model,
                        "size": request.size,
                        "service": result.get("provider", "unknown"),
                        "style": request.style
                    },
                    campaign_id=request.campaign_id or "default"
                )

                # Broadcast image generation event via WebSocket for instant UI updates
                if request.campaign_id:
                    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
                    await campaign_broadcaster.broadcast_campaign_update(
                        request.campaign_id,
                        "image_generated",
                        {
                            "campaign_id": request.campaign_id,
                            "filename": filename,
                            "path": saved_path,
                            "image_type": request.image_type,
                            "prompt": request.prompt,
                        }
                    )
                    logger.info(f"📸 Broadcasted image_generated event for {filename} to campaign {request.campaign_id}")

            return {
                "status": "success",
                "image_url": image_data.get("url"),
                "local_path": saved_path,
                "prompt": enhanced_prompt,
                "model": result.get("model", request.model),
                "size": request.size,
                "service": result.get("provider", "unknown")
            }
        else:
            raise HTTPException(status_code=500, detail="No images generated")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@app.get("/api/image-models")
async def get_image_models(
    current_user = optional_auth()
):
    """
    Get available image generation models.

    Returns both provider-grouped data and flat list for backward compatibility.
    """
    from gaia.infra.image.image_config import get_image_config
    from gaia.infra.image.image_service_manager import get_image_service_manager

    config = get_image_config()
    manager = get_image_service_manager()

    # Build provider status and flat models list
    providers_status = {}
    models_list = []  # Flat list for dropdown (backward compatibility)

    for provider_name, provider_config in config.providers.items():
        # Check if provider is registered and available
        is_available = (
            provider_name in manager.providers and
            manager.providers[provider_name].is_available()
        )

        providers_status[provider_name] = {
            "name": provider_name,
            "display_name": provider_config.display_name,
            "description": provider_config.description,
            "available": is_available,
            "default_model": provider_config.default_model,
            "priority": provider_config.priority,
            "models": []
        }

        # Add models if provider is available
        if is_available:
            for model_key, model_config in provider_config.models.items():
                # Add to provider-specific list
                providers_status[provider_name]["models"].append({
                    "key": model_key,
                    "name": model_config.name,
                    "is_default": model_key == provider_config.default_model
                })

                # Add to flat list for backward compatibility
                models_list.append({
                    "key": model_key,
                    "name": f"{model_config.name} ({provider_config.display_name})",
                    "provider": provider_name,
                    "steps": getattr(model_config, 'steps', 20),
                    "guidance_scale": getattr(model_config, 'guidance_scale', 7.5),
                    "supports_negative_prompt": getattr(model_config, 'supports_negative_prompt', True)
                })

    # Get the actually currently selected model (not the default fallback)
    current_model_key = config.current_model
    current_provider_name = config.get_provider_for_model(current_model_key)

    return {
        "models": models_list,  # Flat list for dropdown
        "current_model": current_model_key,
        "providers": providers_status,  # Provider-grouped data
        "current_provider": current_provider_name
    }

class SwitchImageModelRequest(BaseModel):
    model_key: str

@app.post("/api/image-models/switch")
async def switch_image_model(
    request: SwitchImageModelRequest,
    current_user = require_auth_if_available()
):
    """Switch to a different image generation model - requires authentication if available."""
    from gaia.infra.image.image_service_manager import get_image_service_manager

    manager = get_image_service_manager()
    if not manager:
        raise HTTPException(status_code=503, detail="Image service manager not available")

    # Delegate to the manager (it handles all provider-specific logic)
    result = manager.switch_model(request.model_key)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to switch model"))

    return result


# WebSocket endpoints for real-time campaign synchronization
@app.websocket("/ws/campaign/player")
async def campaign_player_websocket(websocket: WebSocket):
    """WebSocket endpoint for players to receive real-time campaign updates."""
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

    connection = None
    try:
        logger.debug("[WS][player] Connection attempt from origin=%s ua=%s", websocket.headers.get("origin"), websocket.headers.get("user-agent"))

        # Validate session_id
        session_id = websocket.query_params.get("session_id")
        if not session_id:
            await send_error_and_close(websocket, 4404, "session_id query parameter required")
            return

        # Check if campaign exists before allowing WebSocket connection
        # This prevents creating empty campaigns when connecting to non-existent URLs
        manager = SimpleCampaignManager()
        campaign_dir = manager.storage.resolve_session_dir(session_id, create=False)

        if campaign_dir is None:
            logger.warning(f"Campaign not found, rejecting player WebSocket: {session_id}")
            await send_error_and_close(websocket, 4404, f"Campaign not found: {session_id}")
            return

        # Enforce Origin allowlist (in prod by default)
        origin = websocket.headers.get("origin")
        if WS_ENFORCE_ORIGIN:
            allowed = _is_origin_allowed(origin)
            logger.info(
                "[WS][player] Origin check: origin=%s allowed=%s enforce=%s",
                origin,
                allowed,
                WS_ENFORCE_ORIGIN,
            )
        if WS_ENFORCE_ORIGIN and not _is_origin_allowed(origin):
            await send_error_and_close(websocket, 4403, "Forbidden origin")
            return

        # Try to authenticate user from initial connection (headers/cookies)
        # If auth fails but is required, we'll accept the connection and wait for auth message
        session_registry: Optional[SessionRegistry] = getattr(app.state, "session_registry", None)  # type: ignore[name-defined]
        user_obj = None
        auth_required = False

        try:
            user_obj = await authenticate_ws_user(
                websocket, session_registry, session_id, WS_ALLOW_QUERY_TOKEN
            )

            # Check if ACL is required for this session
            if session_registry:
                meta = session_registry.get_metadata(session_id)
                if meta and (
                    meta.get("owner_user_id")
                    or meta.get("owner_email")
                    or (meta.get("member_user_ids") or [])
                    or (meta.get("member_emails") or [])
                ):
                    auth_required = True
            logger.info(
                "[WS][player] ACL required=%s token_provided=%s via_header=%s via_query=%s via_cookie=%s",
                auth_required,
                bool(websocket.headers.get("authorization")) or bool(websocket.query_params.get("token")) or bool(websocket.cookies),
                bool(websocket.headers.get("authorization")),
                bool(websocket.query_params.get("token")),
                bool(websocket.cookies),
            )

            # Enforce membership/ownership if authentication was provided
            if user_obj and auth_required:
                _enforce_session_access(session_registry, session_id, user_obj)
                logger.debug("[WS][player] Initial auth OK: user_id=%s email=%s", getattr(user_obj, "user_id", None), getattr(user_obj, "email", None))

        except HTTPException as exc:
            # If auth failed but is required, accept connection and wait for auth message
            # The auth message handler will validate the token
            if exc.status_code == 401:
                logger.debug("[WS][player] No initial auth; will wait for auth message (session=%s)", session_id)
                auth_required = True
            else:
                # Other errors (403, 404) should close immediately
                code_map = {403: 4403, 404: 4404}
                close_code = code_map.get(exc.status_code, 1008)
                reason = str(exc.detail)
                await send_error_and_close(websocket, close_code, reason)
                return

        user_email = getattr(user_obj, 'email', None) if user_obj else None
        connection = await campaign_broadcaster.connect_player(
            websocket,
            session_id,
            user_id=getattr(user_obj, 'user_id', None) if user_obj else None,
            user_email=user_email
        )
        connection.auth_required = auth_required
        connection.authenticated_user = user_obj
        logger.debug("[WS][player] Connected: session=%s auth_required=%s", connection.session_id, connection.auth_required)

        # Initialize audio WebSocket handler
        audio_handler = AudioWebSocketHandler(campaign_broadcaster)

        # Custom message handler for player-specific messages
        async def handle_player_message(ws, conn, msg_type, data):
            if msg_type == "yjs_update":
                # Yjs CRDT update payload from a collaborative editor client
                campaign_id = data.get("sessionId") or data.get("campaign_id") or conn.session_id
                update_payload = data.get("update")
                if campaign_id and update_payload is not None:
                    await campaign_broadcaster.broadcast_campaign_update(
                        campaign_id, "yjs_update",
                        {
                            "sessionId": campaign_id,
                            "playerId": data.get("playerId"),
                            "update": update_payload,
                            "timestamp": data.get("timestamp", datetime.now().isoformat())
                        }
                    )

            elif msg_type == "awareness_update":
                # Awareness update keeps remote cursors/selections in sync
                campaign_id = data.get("sessionId") or data.get("campaign_id") or conn.session_id
                update_payload = data.get("update")
                if campaign_id and update_payload is not None:
                    await campaign_broadcaster.broadcast_campaign_update(
                        campaign_id, "awareness_update",
                        {
                            "sessionId": campaign_id,
                            "playerId": data.get("playerId"),
                            "update": update_payload,
                            "timestamp": data.get("timestamp", datetime.now().isoformat())
                        }
                    )

            elif msg_type == "audio_played":
                # Mark audio chunk(s) as played for session persistence
                await audio_handler.handle_audio_played(data, conn.session_id, "player", conn)
            else:
                logger.info(f"Player sent message: {msg_type}")

        # Use generic message loop with custom handler
        await ws_message_loop(websocket, connection, handle_player_message, session_registry, session_id)

    except WebSocketDisconnect:
        logger.info("[WS][player] Disconnected normally (session=%s)", getattr(connection, "session_id", None))
    except Exception as e:
        logger.error("[WS][player] Error in WebSocket: %s", e)
    finally:
        if connection:
            await campaign_broadcaster.disconnect_player(connection)


@app.websocket("/ws/campaign/dm")
async def campaign_dm_websocket(websocket: WebSocket):
    """WebSocket endpoint for DM bidirectional communication (optional)."""
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

    connection = None
    try:
        logger.debug("[WS][dm] Connection attempt from origin=%s ua=%s", websocket.headers.get("origin"), websocket.headers.get("user-agent"))

        # Validate session_id
        session_id = websocket.query_params.get("session_id")
        if not session_id:
            await send_error_and_close(websocket, 4404, "session_id query parameter required")
            return

        # Check if campaign exists before allowing WebSocket connection
        # This prevents creating empty campaigns when connecting to non-existent URLs
        manager = SimpleCampaignManager()
        campaign_dir = manager.storage.resolve_session_dir(session_id, create=False)

        if campaign_dir is None:
            logger.warning(f"Campaign not found, rejecting DM WebSocket: {session_id}")
            await send_error_and_close(websocket, 4404, f"Campaign not found: {session_id}")
            return

        # Enforce Origin allowlist (in prod by default)
        origin = websocket.headers.get("origin")
        if WS_ENFORCE_ORIGIN:
            allowed = _is_origin_allowed(origin)
            logger.info(
                "[WS][dm] Origin check: origin=%s allowed=%s enforce=%s",
                origin,
                allowed,
                WS_ENFORCE_ORIGIN,
            )
        if WS_ENFORCE_ORIGIN and not _is_origin_allowed(origin):
            await send_error_and_close(websocket, 4403, "Forbidden origin")
            return

        # Try to authenticate user from initial connection (headers/cookies)
        # If auth fails but is required, we'll accept the connection and wait for auth message
        session_registry: Optional[SessionRegistry] = getattr(app.state, "session_registry", None)  # type: ignore[name-defined]
        user_obj = None
        auth_required = False

        try:
            user_obj = await authenticate_ws_user(
                websocket, session_registry, session_id, WS_ALLOW_QUERY_TOKEN
            )

            # Check if ACL is required for this session
            if session_registry:
                meta = session_registry.get_metadata(session_id)
                if meta and (
                    meta.get("owner_user_id")
                    or meta.get("owner_email")
                    or (meta.get("member_user_ids") or [])
                    or (meta.get("member_emails") or [])
                ):
                    auth_required = True
            logger.info(
                "[WS][dm] ACL required=%s token_provided=%s via_header=%s via_query=%s via_cookie=%s",
                auth_required,
                bool(websocket.headers.get("authorization")) or bool(websocket.query_params.get("token")) or bool(websocket.cookies),
                bool(websocket.headers.get("authorization")),
                bool(websocket.query_params.get("token")),
                bool(websocket.cookies),
            )

            # Enforce membership/ownership if authentication was provided
            if user_obj and auth_required:
                _enforce_session_access(session_registry, session_id, user_obj)
                logger.info("[WS][dm] Initial auth OK: user_id=%s email=%s", getattr(user_obj, "user_id", None), getattr(user_obj, "email", None))

        except HTTPException as exc:
            # If auth failed but is required, accept connection and wait for auth message
            # The auth message handler will validate the token
            if exc.status_code == 401:
                logger.debug("[WS][dm] No initial auth; will wait for auth message (session=%s)", session_id)
                auth_required = True
            else:
                # Other errors (403, 404) should close immediately
                code_map = {403: 4403, 404: 4404}
                close_code = code_map.get(exc.status_code, 1008)
                reason = str(exc.detail)
                await send_error_and_close(websocket, close_code, reason)
                return

        user_email = getattr(user_obj, 'email', None) if user_obj else None
        connection = await campaign_broadcaster.connect_dm(
            websocket,
            session_id,
            user_id=getattr(user_obj, 'user_id', None) if user_obj else None,
            user_email=user_email
        )
        connection.auth_required = auth_required
        connection.authenticated_user = user_obj
        logger.debug("[WS][dm] Connected: session=%s auth_required=%s", connection.session_id, connection.auth_required)

        # Initialize audio WebSocket handler
        audio_handler = AudioWebSocketHandler(campaign_broadcaster)

        # Custom message handler for DM-specific messages
        async def handle_dm_message(ws, conn, msg_type, data):
            if msg_type == "broadcast_test":
                # Allow DM to trigger test broadcasts
                await campaign_broadcaster.broadcast_campaign_update(
                    conn.session_id,
                    "test_message",
                    {
                        "campaign_id": conn.session_id,
                        "message": data.get("message", "Test broadcast from DM")
                    }
                )
            elif msg_type == "audio_played":
                # Mark audio chunk(s) as played for session persistence
                await audio_handler.handle_audio_played(data, conn.session_id, "dm", conn)
            elif msg_type == "start_audio_stream":
                # Start synchronized audio streaming
                await audio_handler.handle_start_audio_stream(data, conn.session_id)
            elif msg_type == "stop_audio_stream":
                # Stop synchronized audio streaming
                await audio_handler.handle_stop_audio_stream(data, conn.session_id)
            elif msg_type == "clear_audio_queue":
                await audio_handler.handle_clear_audio_queue(data, conn.session_id, ws)
            elif msg_type == "get_stream_position":
                # Get current playback position
                await audio_handler.handle_get_stream_position(data, conn.session_id, ws)
            else:
                logger.info(f"DM sent message: {msg_type}")

        # Use generic message loop with custom handler
        await ws_message_loop(websocket, connection, handle_dm_message, session_registry, session_id)

    except WebSocketDisconnect:
        logger.info("[WS][dm] Disconnected normally (session=%s)", getattr(connection, "session_id", None))
    except Exception as e:
        logger.error("[WS][dm] Error in WebSocket: %s", e)
    finally:
        if connection:
            await campaign_broadcaster.disconnect_dm(connection)


@app.websocket("/ws/collab/session/{session_id}")
async def collaborative_session_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for collaborative text editing sessions.

    This endpoint provides real-time text synchronization using Yjs CRDT
    for any session, independent of campaigns. Perfect for testing and
    general-purpose collaborative editing.
    """
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster, ConnectionInfo
    from gaia.connection.websocket.collaborative import CollaborativeSession
    from gaia.connection.websocket.collaborative.handlers import CollaborativeMessageHandler

    connection = None
    handler = None

    try:
        logger.debug("[WS][collab] Connection attempt for session=%s origin=%s",
                    session_id, websocket.headers.get("origin"))

        # Accept the connection
        await websocket.accept()

        # Create connection info
        connection = ConnectionInfo(
            websocket=websocket,
            session_id=session_id,
            connection_type="collab"
        )

        # Register in session state for broadcasting
        state = campaign_broadcaster._get_state(session_id)
        state.player_connections.append(connection)

        # Get or create collaborative session
        if not hasattr(state, 'collab_session'):
            state.collab_session = CollaborativeSession(session_id)

        # Create message handler
        handler = CollaborativeMessageHandler(
            session=state.collab_session,
            websocket=websocket,
            broadcaster=campaign_broadcaster
        )

        logger.info("[WS][collab] Connected to session=%s (total connections: %d)",
                   session_id, len(state.player_connections))

        # Message handling loop
        while True:
            raw_message = await websocket.receive_text()
            await handler.handle_message(raw_message)

    except WebSocketDisconnect:
        logger.info("[WS][collab] Client disconnected from session=%s", session_id)
    except Exception as e:
        logger.error("[WS][collab] Connection error: %s", e, exc_info=True)
    finally:
        # Clean up connection
        if connection:
            state = campaign_broadcaster.sessions.get(session_id)
            if state and connection in state.player_connections:
                state.player_connections.remove(connection)
                logger.info("[WS][collab] Removed connection from session=%s (remaining: %d)",
                          session_id, len(state.player_connections))

                # Mark player as disconnected (don't unregister - they might reconnect)
                if handler and handler.player_id and hasattr(state, 'collab_session'):
                    player_info = state.collab_session.players.get(handler.player_id)
                    if player_info:
                        from datetime import datetime
                        player_info.disconnected_at = datetime.now()
                        logger.info("[WS][collab] Marked player %s (%s) as disconnected",
                                   player_info.name, handler.player_id)

                        # Broadcast updated roster so clients hide offline players immediately
                        players_payload = state.collab_session.get_all_players()
                        await campaign_broadcaster.broadcast_campaign_update(
                            session_id,
                            "player_list",
                            {
                                "sessionId": session_id,
                                "players": players_payload,
                            },
                        )


@app.get("/api/websocket/stats")
async def get_websocket_stats(
    current_user = optional_auth()
):
    """Get WebSocket connection statistics."""
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
    return campaign_broadcaster.get_connection_stats()

@app.post("/api/websocket/refresh-campaign")
async def refresh_campaign_state(
    session_id: Optional[str] = Query(default=None),
    current_user = optional_auth()
):
    """Force refresh the current campaign state and broadcast to all players."""
    from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
    global orchestrator
    
    if not session_id:
        if not orchestrator or not orchestrator.active_campaign_id:
            raise HTTPException(status_code=400, detail="No active campaign to refresh")
        session_id = orchestrator.active_campaign_id
    
    if not session_id:
        raise HTTPException(status_code=400, detail="No active campaign to refresh")
    
    await campaign_broadcaster.force_refresh_campaign_state(session_id)
    return {"success": True, "message": f"Campaign state for {session_id} refreshed and broadcasted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
