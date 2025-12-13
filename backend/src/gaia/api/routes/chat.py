"""
OpenAPI/JSON chat endpoints to replace protobuf communication.
"""

import io
import logging
import asyncio
import mimetypes
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gaia.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MachineResponse,
    StructuredGameData,
    NewCampaignRequest,
    NewCampaignResponse,
    AddContextRequest,
    AddContextResponse,
    ErrorResponse,
    InputType,
    AudioArtifactPayload,
    PlayerCharacterContext,
)
from gaia.services.player_options_service import (
    PlayerOptionsService,
    get_observations_manager,
)
from auth.src.flexible_auth import optional_auth
from gaia.infra.audio.auto_tts_service import auto_tts_service
from gaia.infra.audio.playback_request_writer import PlaybackRequestWriter
from gaia.infra.audio.audio_artifact_store import audio_artifact_store
from gaia.infra.audio.audio_playback_service import audio_playback_service
from gaia_private.session.session_manager import SessionNotFoundError
from auth.src.models import AccessControl, PermissionLevel
from db.src import get_async_db
from gaia.connection.socketio_broadcaster import socketio_broadcaster
from gaia.api.middleware.room_access import RoomAccessGuard

logger = logging.getLogger(__name__)

# Create router for consolidated API endpoints
router = APIRouter(prefix="/api", tags=["chat"])
room_access_guard = RoomAccessGuard()


def _ensure_session_access(session_registry, session_id: str, current_user) -> None:
    """Raise if the caller lacks access to the session (when ownership is claimed)."""
    if not session_registry or not session_id:
        return

    metadata = session_registry.get_metadata(session_id)
    if not metadata:
        return

    user_id = getattr(current_user, "user_id", None) if current_user else None
    user_email = getattr(current_user, "email", None) if current_user else None

    if session_registry.is_authorized(
        session_id,
        user_id=user_id,
        user_email=user_email,
    ):
        return

    if current_user:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this session",
        )

    raise HTTPException(
        status_code=401,
        detail="Authentication required to access this session",
    )


def _extract_player_character_context(chat_request: ChatRequest) -> Optional[PlayerCharacterContext]:
    """Normalize player-character metadata from the chat request."""
    candidate = chat_request.player_character
    if candidate and not candidate.is_empty():
        return candidate

    metadata = chat_request.metadata or {}
    if not isinstance(metadata, dict):
        return None

    search_keys = [
        "player_character",
        "playerCharacter",
        "active_character",
        "activeCharacter",
    ]
    raw_candidates: List[Dict[str, Any]] = []

    for key in search_keys:
        value = metadata.get(key)
        if isinstance(value, dict):
            raw_candidates.append(value)

    turn_info = metadata.get("turn_info") or metadata.get("turnInfo")
    if isinstance(turn_info, dict):
        raw_candidates.append(turn_info)

    if not raw_candidates:
        raw_candidates.append(metadata)

    character_id: Optional[str] = None
    character_name: Optional[str] = None

    def _maybe_extract(source: Dict[str, Any]) -> None:
        nonlocal character_id, character_name
        if not isinstance(source, dict):
            return
        if character_id is None:
            character_id = (
                source.get("character_id")
                or source.get("characterId")
                or source.get("activeCharacterId")
                or source.get("character")
            )
        if character_name is None:
            character_name = (
                source.get("character_name")
                or source.get("characterName")
                or source.get("activeCharacterName")
                or source.get("display_name")
                or source.get("displayName")
            )

    for raw in raw_candidates:
        _maybe_extract(raw)
        if character_id or character_name:
            break

    if not (character_id or character_name):
        return None

    try:
        context = PlayerCharacterContext(
            character_id=character_id,
            character_name=character_name,
        )
    except Exception:
        return None

    return None if context.is_empty() else context


# Global player options service instance
_player_options_service: Optional[PlayerOptionsService] = None


def _get_player_options_service() -> PlayerOptionsService:
    """Get the global player options service instance."""
    global _player_options_service
    if _player_options_service is None:
        _player_options_service = PlayerOptionsService()
    return _player_options_service


def transform_structured_data(data: dict) -> StructuredGameData:
    """Transform orchestrator structured data to Pydantic model."""
    audio_payload = None
    audio_data = data.get("audio")
    if isinstance(audio_data, dict):
        try:
            audio_payload = AudioArtifactPayload(**audio_data)
        except Exception as exc:
            logger.warning("Failed to parse audio payload: %s", exc)

    def parse_field(field):
        if not field:
            return ""
        if isinstance(field, (dict, list)):
            return field
        if isinstance(field, str):
            trimmed = field.strip()
            if trimmed.startswith("{") or trimmed.startswith("["):
                try:
                    import json

                    return json.loads(field)
                except Exception:
                    return field
        return field

    def parse_dict_or_list_field(field):
        if not field:
            return None
        if isinstance(field, (dict, list)):
            return field
        if isinstance(field, str):
            trimmed = field.strip()
            if trimmed.startswith("{") or trimmed.startswith("["):
                try:
                    import json

                    return json.loads(field)
                except Exception:
                    return None
        return None

    combat_state_value = parse_field(data.get("combat_state"))
    if isinstance(combat_state_value, dict):
        status_value = data.get("status", "")
        combat_state_dict = combat_state_value
    else:
        status_value = combat_state_value if isinstance(combat_state_value, str) else data.get("status", "")
        combat_state_dict = None

    # Derive player options from 'turn' text if explicit list not provided
    player_options_value = data.get("player_options", "")
    if not player_options_value:
        turn_text = data.get("turn") or ""
        if isinstance(turn_text, str) and turn_text:
            import re
            # Extract lines like `1) ...`, `2) ...` from a single block
            # Matches from the first digit right after 'Your turn:' if present, otherwise any enumerated list
            opts = re.findall(r"\b\d+\)\s+([^\n]+)", turn_text)
            if opts:
                player_options_value = opts

    # Ensure answer falls back to player_response when missing
    answer_value = data.get("answer") or data.get("player_response") or "Backend did not provide an answer."

    structured = StructuredGameData(
        narrative=parse_field(data.get("narrative", "")),
        turn=data.get("turn", ""),
        status=status_value,
        characters=parse_field(data.get("characters", "")),
        player_options=parse_field(player_options_value),
        combat_status=parse_dict_or_list_field(data.get("combat_status")),
        combat_state=combat_state_dict,
        action_breakdown=parse_dict_or_list_field(data.get("action_breakdown")),
        turn_resolution=parse_dict_or_list_field(data.get("turn_resolution")),
        turn_info=parse_dict_or_list_field(data.get("turn_info")),
        environmental_conditions=data.get("environmental_conditions", ""),
        immediate_threats=data.get("immediate_threats", ""),
        story_progression=data.get("story_progression", ""),
        answer=answer_value,
    )
    if audio_payload:
        structured.audio = audio_payload
    return structured


@router.post("/chat", response_model=ChatResponse, responses={
    200: {"description": "Successful response", "model": ChatResponse},
    500: {"description": "Server error", "model": ErrorResponse},
})
async def chat(
    chat_request: ChatRequest,
    req: Request,
    current_user=optional_auth(),
):
    """
    Send a chat message and receive a structured response.
    """
    logger.info("Chat endpoint called - session=%s input=%s", chat_request.session_id, chat_request.input_type)

    try:
        session_manager = getattr(req.app.state, "session_manager", None)
        orchestrator_fallback = getattr(req.app.state, "orchestrator", None)
        session_registry = getattr(req.app.state, "session_registry", None)

        result = None
        session_context = None
        session_id = chat_request.session_id
        room_access_guard.ensure_dm_present(session_id)
        user_id = getattr(current_user, "user_id", None)
        user_id_str = str(user_id) if user_id is not None else None
        room_access_guard.ensure_player_has_character(session_id, user_id_str)
        player_character_ctx = _extract_player_character_context(chat_request)
        player_character_payload: Optional[Dict[str, Any]] = None
        if player_character_ctx:
            payload = player_character_ctx.model_dump(exclude_none=True)
            if payload:
                player_character_payload = payload

        if session_manager is not None:
            _ensure_session_access(session_registry, chat_request.session_id, current_user)

            try:
                session_context = await session_manager.get_or_create(chat_request.session_id)
            except SessionNotFoundError as exc:
                raise HTTPException(status_code=404, detail=f"Session '{chat_request.session_id}' not found") from exc

            # NOTE: Turn broadcasts (turn_started, input_received) are now handled by
            # the WebSocket submit_turn handler. DM uses WebSocket for submissions.
            # This HTTP endpoint is kept for backward compatibility but Socket.IO
            # has its own HTTP long-polling fallback built-in.

            async with session_context.lock:
                result = await session_context.orchestrator.run_campaign(
                    user_input=chat_request.message,
                    campaign_id=session_context.campaign_id,
                    player_character=player_character_payload,
                    broadcaster=socketio_broadcaster,
                )
                session_context.touch()

                if session_registry:
                    session_registry.touch_session(
                        session_context.session_id,
                        getattr(current_user, "user_id", None),
                        user_email=getattr(current_user, "email", None),
                    )

            session_id = session_context.session_id

            # Clear observations that were included in this turn submission
            # This prevents stale observations from persisting after turn advancement
            try:
                obs_manager = get_observations_manager()
                obs_manager.mark_all_included(session_id)
                obs_manager.clear_included(session_id)
                logger.debug("[Chat] Cleared included observations for session %s", session_id)
            except Exception as obs_err:
                logger.warning("[Chat] Failed to clear observations: %s", obs_err)
        else:
            if orchestrator_fallback is None:
                raise HTTPException(status_code=500, detail="Session manager not initialized")
            # Legacy fallback used by lightweight tests that inject an orchestrator directly.
            result = await orchestrator_fallback.run_campaign(
                user_input=chat_request.message,
                campaign_id=session_id,
                player_character=player_character_payload,
                broadcaster=socketio_broadcaster,
            )

            # Clear observations for legacy path too
            try:
                obs_manager = get_observations_manager()
                obs_manager.mark_all_included(session_id)
                obs_manager.clear_included(session_id)
            except Exception:
                pass

        structured_data_raw = dict(result.get("structured_data", {}) or {})

        structured_data = transform_structured_data(structured_data_raw)

        if "generated_image" in result:
            image_data = result["generated_image"]
            structured_data.generated_image_url = image_data.get("url", "")
            structured_data.generated_image_path = image_data.get("local_path", "")
            structured_data.generated_image_prompt = image_data.get("prompt", "")
            structured_data.generated_image_type = image_data.get("type", "")

        # Generate personalized player options for all connected players
        try:
            service = _get_player_options_service()
            personalized_options = await service.generate_options_dict(
                campaign_id=session_id,
                structured_data=structured_data_raw,
            )
            if personalized_options:
                structured_data.personalized_player_options = personalized_options
                characters = personalized_options.get("characters", {})
                logger.info("[PlayerOptions] Generated personalized options for %d characters", len(characters))

                # Broadcast personalized options via WebSocket
                if characters:
                    await socketio_broadcaster.broadcast_campaign_update(
                        session_id,
                        "personalized_player_options",
                        {"personalized_player_options": personalized_options}
                    )
        except Exception as opts_err:
            logger.warning("[PlayerOptions] Failed to generate personalized options: %s", opts_err)
            # Continue without personalized options - fall back to legacy player_options

        machine_response = MachineResponse(
            session_id=session_id,
            agent_name="Dungeon Master",
            structured_data=structured_data,
        )

        return ChatResponse(success=True, message=machine_response)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in chat endpoint: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "CHAT_ERROR",
                "error_message": str(exc),
                "success": False,
            },
        ) from exc


@router.post("/campaigns/new", response_model=NewCampaignResponse, responses={
    200: {"description": "Campaign created successfully", "model": NewCampaignResponse},
    500: {"description": "Server error", "model": ErrorResponse},
})
async def new_campaign(
    campaign_request: NewCampaignRequest,
    req: Request,
    current_user=optional_auth(),
):
    """
    Start a new campaign (optionally blank).
    """
    logger.info("New campaign endpoint called - blank=%s", campaign_request.blank)

    try:
        session_manager = getattr(req.app.state, "session_manager", None)
        if not session_manager:
            raise HTTPException(status_code=500, detail="Session manager not initialized")

        session_context, result = await session_manager.create_session(blank=campaign_request.blank)

        session_registry = getattr(req.app.state, "session_registry", None)
        if session_registry:
            owner_user_id = getattr(current_user, "user_id", None)
            owner_email = getattr(current_user, "email", None)
            title = None
            if campaign_request.metadata:
                title = campaign_request.metadata.get("name") or campaign_request.metadata.get("title")
            session_registry.register_session(
                session_context.session_id,
                owner_user_id,
                title=title,
                owner_email=owner_email,
            )

        structured_data_raw = dict(result.get("structured_data", {}) or {})

        structured_data = transform_structured_data(structured_data_raw)

        if "generated_image" in result:
            image_data = result["generated_image"]
            structured_data.generated_image_url = image_data.get("url", "")
            structured_data.generated_image_path = image_data.get("local_path", "")
            structured_data.generated_image_prompt = image_data.get("prompt", "")
            structured_data.generated_image_type = image_data.get("type", "")

        machine_response = MachineResponse(
            session_id=session_context.session_id,
            agent_name="Dungeon Master",
            structured_data=structured_data,
        )

        return NewCampaignResponse(
            success=True,
            session_id=session_context.session_id,
            message=machine_response,
            campaign_setup=result.get("campaign_setup"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating new campaign: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "NEW_CAMPAIGN_ERROR",
                "error_message": str(exc),
                "success": False,
            },
        ) from exc


@router.post("/campaigns/add-context", response_model=AddContextResponse, responses={
    200: {"description": "Context added successfully", "model": AddContextResponse},
    500: {"description": "Server error", "model": ErrorResponse},
})
async def add_context(
    context_request: AddContextRequest,
    req: Request,
    current_user=optional_auth(),
):
    """
    Add context to a campaign without triggering a DM response.
    """
    logger.info("Add context endpoint called - session=%s", context_request.session_id)

    try:
        session_manager = getattr(req.app.state, "session_manager", None)
        if not session_manager:
            raise HTTPException(status_code=500, detail="Session manager not initialized")

        session_registry = getattr(req.app.state, "session_registry", None)
        _ensure_session_access(session_registry, context_request.session_id, current_user)

        try:
            session_context = await session_manager.get_or_create(context_request.session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Session '{context_request.session_id}' not found") from exc

        async with session_context.lock:
            success = await session_context.orchestrator.add_context(
                context_request.context,
                session_context.campaign_id,
            )
            session_context.touch()
            if session_registry:
                session_registry.touch_session(
                    session_context.session_id,
                    getattr(current_user, "user_id", None),
                    user_email=getattr(current_user, "email", None),
                )

        if success:
            return AddContextResponse(success=True, message="Context added successfully")
        return AddContextResponse(success=False, message="Failed to add context to campaign")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error adding context: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "ADD_CONTEXT_ERROR",
                "error_message": str(exc),
                "success": False,
            },
        ) from exc


@router.get("/media/audio/{session_id}/{filename}", tags=["media"])
async def proxy_audio_artifact(
    session_id: str,
    filename: str,
    req: Request,
    token: Optional[str] = None,
    current_user=optional_auth(),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Stream an audio artifact via the API when signed URLs are not used.

    Supports authentication via:
    1. Authorization header (for API calls)
    2. Query parameter ?token=... (for HTML audio elements)
    """
    if not auto_tts_service.client_audio_enabled or not audio_artifact_store.enabled:
        raise HTTPException(status_code=404, detail="Audio artifacts unavailable")

    # If no user from header auth, try token query param
    # Diagnostics: summarize request auth context without exposing secrets
    try:
        logger.info(
            "[AUDIO][media] GET /api/media/audio session=%s file=%s origin=%s auth_header=%s query_token=%s",
            session_id,
            filename,
            req.headers.get("origin"),
            bool(req.headers.get("authorization")),
            bool(token),
        )
    except Exception:
        pass

    user_from_token = None
    if current_user is None and token:
        try:
            from auth.src.auth0_jwt_verifier import get_auth0_verifier
            from auth.src.models import User, OAuthAccount
            auth0_verifier = get_auth0_verifier()
            if auth0_verifier:
                user_info = auth0_verifier.verify_token(token)
                if user_info:
                    auth0_user_id = user_info.get("user_id")
                    email = user_info.get("email")
                    if auth0_user_id and email:
                        # Look up user by OAuth account
                        result = await db.execute(
                            select(OAuthAccount).where(
                                OAuthAccount.provider == "auth0",
                                OAuthAccount.provider_account_id == auth0_user_id
                            )
                        )
                        oauth_account = result.scalar_one_or_none()
                        if oauth_account:
                            result = await db.execute(
                                select(User).where(User.user_id == oauth_account.user_id)
                            )
                            user_from_token = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                "[AUDIO][media] Token verification failed: %s",
                str(e)[:200]
            )

    # Use whichever auth method succeeded
    effective_user = current_user or user_from_token

    if effective_user is None:
        raise HTTPException(status_code=403, detail="Authentication required for media access")

    authorized = getattr(effective_user, "is_admin", False)

    if not authorized:
        session_registry = getattr(req.app.state, "session_registry", None)
        if session_registry:
            try:
                authorized = session_registry.is_authorized(
                    session_id,
                    user_id=getattr(effective_user, "user_id", None),
                    user_email=getattr(effective_user, "email", None),
                )
            except Exception:  # noqa: BLE001
                authorized = False

    if not authorized:
        stmt = (
            select(func.count())
            .select_from(AccessControl)
            .where(
                AccessControl.resource_type == "campaign",
                AccessControl.resource_id == session_id,
                AccessControl.user_id == effective_user.user_id,
                AccessControl.permission_level.in_([
                    PermissionLevel.READ.value,
                    PermissionLevel.WRITE.value,
                    PermissionLevel.ADMIN.value,
                ]),
            )
        )
        result = await db.execute(stmt)
        authorized = (result.scalar_one() or 0) > 0

    if not authorized:
        logger.warning(
            "[AUDIO][media] Unauthorized media request session=%s file=%s user_id=%s email=%s",
            session_id,
            filename,
            getattr(effective_user, "user_id", None),
            getattr(effective_user, "email", None),
        )
        raise HTTPException(status_code=403, detail="Not authorized to access this session's media")

    try:
        audio_bytes = audio_artifact_store.read_artifact_bytes(session_id, filename)
    except FileNotFoundError as exc:
        logger.warning(
            "[AUDIO][media] Audio artifact not found session=%s file=%s",
            session_id,
            filename,
        )
        raise HTTPException(status_code=404, detail="Audio artifact not found") from exc

    media_type, _ = mimetypes.guess_type(filename)
    media_type = media_type or "audio/mpeg"
    try:
        logger.debug(
            "[AUDIO][media] Streaming artifact session=%s file=%s bytes=%s content_type=%s",
            session_id,
            filename,
            len(audio_bytes) if audio_bytes else 0,
            media_type,
        )
    except Exception:
        pass

    return StreamingResponse(io.BytesIO(audio_bytes), media_type=media_type)


@router.get("/media/images/{session_id}/{filename}", tags=["media"])
async def proxy_image_artifact(
    session_id: str,
    filename: str,
    req: Request,
    token: Optional[str] = None,
    current_user=optional_auth(),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Stream an image artifact via the API (portraits, scenes, etc).

    Supports authentication via:
    1. Authorization header (for API calls)
    2. Query parameter ?token=... (for HTML img elements)
    """
    from gaia.infra.image.image_artifact_store import image_artifact_store

    if not image_artifact_store.enabled:
        raise HTTPException(status_code=404, detail="Image artifacts unavailable")

    # If no user from header auth, try token query param
    user_from_token = None
    if current_user is None and token:
        try:
            from auth.src.auth0_jwt_verifier import get_auth0_verifier
            from auth.src.models import User, OAuthAccount
            auth0_verifier = get_auth0_verifier()
            if auth0_verifier:
                user_info = auth0_verifier.verify_token(token)
                if user_info:
                    auth0_user_id = user_info.get("user_id")
                    email = user_info.get("email")
                    if auth0_user_id and email:
                        # Look up user by OAuth account
                        result = await db.execute(
                            select(OAuthAccount).where(
                                OAuthAccount.provider == "auth0",
                                OAuthAccount.provider_account_id == auth0_user_id
                            )
                        )
                        oauth_account = result.scalar_one_or_none()
                        if oauth_account:
                            result = await db.execute(
                                select(User).where(User.user_id == oauth_account.user_id)
                            )
                            user_from_token = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                "[AUDIO][media] Token verification failed: %s",
                str(e)[:200]
            )

    # Use whichever auth method succeeded
    effective_user = current_user or user_from_token

    if effective_user is None:
        raise HTTPException(status_code=403, detail="Authentication required for media access")

    authorized = getattr(effective_user, "is_admin", False)

    if not authorized:
        session_registry = getattr(req.app.state, "session_registry", None)
        if session_registry:
            try:
                authorized = session_registry.is_authorized(
                    session_id,
                    user_id=getattr(effective_user, "user_id", None),
                    user_email=getattr(effective_user, "email", None),
                )
            except Exception:  # noqa: BLE001
                authorized = False

    if not authorized:
        stmt = (
            select(func.count())
            .select_from(AccessControl)
            .where(
                AccessControl.resource_type == "campaign",
                AccessControl.resource_id == session_id,
                AccessControl.user_id == getattr(effective_user, "user_id", None),
                AccessControl.permission_level.in_([
                    PermissionLevel.READ.value,
                    PermissionLevel.WRITE.value,
                    PermissionLevel.ADMIN.value,
                ]),
            )
        )
        result = await db.execute(stmt)
        authorized = (result.scalar_one() or 0) > 0

    if not authorized:
        logger.warning(
            "[IMAGE][media] Unauthorized media request session=%s file=%s user_id=%s email=%s",
            session_id,
            filename,
            getattr(effective_user, "user_id", None),
            getattr(effective_user, "email", None),
        )
        raise HTTPException(status_code=403, detail="Not authorized to access this session's media")

    try:
        image_bytes = image_artifact_store.read_artifact_bytes(session_id, filename)
    except FileNotFoundError as exc:
        logger.warning(
            "[IMAGE][media] Image artifact not found session=%s file=%s",
            session_id,
            filename,
        )
        raise HTTPException(status_code=404, detail="Image artifact not found") from exc

    media_type, _ = mimetypes.guess_type(filename)
    media_type = media_type or "image/png"
    try:
        logger.debug(
            "[IMAGE][media] Streaming artifact session=%s file=%s bytes=%s content_type=%s",
            session_id,
            filename,
            len(image_bytes) if image_bytes else 0,
            media_type,
        )
    except Exception:
        pass

    return StreamingResponse(io.BytesIO(image_bytes), media_type=media_type)


@router.post("/chat/compat", response_model=ChatResponse, responses={
    200: {"description": "Successful response", "model": ChatResponse},
    500: {"description": "Server error", "model": ErrorResponse},
})
async def chat_compat(
    chat_request: ChatRequest,
    req: Request,
    current_user=optional_auth(),
):
    """
    Compatibility endpoint that accepts the same request format as the protobuf version.
    """
    if isinstance(chat_request.input_type, str):
        chat_request.input_type = InputType(chat_request.input_type)

    if chat_request.input_type in {InputType.NEW_CAMPAIGN, InputType.BLANK_CAMPAIGN}:
        new_campaign_req = NewCampaignRequest(blank=(chat_request.input_type == InputType.BLANK_CAMPAIGN))
        return await new_campaign(new_campaign_req, req, current_user)

    if chat_request.input_type == InputType.CONTEXT:
        add_context_req = AddContextRequest(
            context=chat_request.message,
            session_id=chat_request.session_id,
        )
        response = await add_context(add_context_req, req, current_user)
        return ChatResponse(
            success=response.success,
            message=MachineResponse(
                session_id=chat_request.session_id,
                agent_name="System",
                structured_data=StructuredGameData(answer=response.message),
            ),
        )

    return await chat(chat_request, req, current_user)


# Audio playback endpoints

@router.get("/campaigns/{campaign_id}/audio/queue")
async def get_audio_queue(
    request: Request,
    campaign_id: str,
    current_user=optional_auth(),
):
    """Get comprehensive audio playback queue status for a campaign.

    Returns the currently playing request, all pending requests, and queue statistics.
    This is the primary endpoint for checking audio queue state.

    Returns:
        currently_playing: Dict with request info if GENERATING, None otherwise
        pending_requests: List of pending request dicts
        total_pending_requests: int
        total_pending_chunks: int
        status_message: str - Human-readable status
    """
    try:
        # Check session access if needed
        session_registry = getattr(request.app.state, "session_registry", None)
        _ensure_session_access(session_registry, campaign_id, current_user)

        # Get comprehensive queue status from service
        queue_status = audio_playback_service.get_queue_status(campaign_id)

        logger.debug(
            "[AUDIO_API] Retrieved queue status for campaign %s: %s",
            campaign_id,
            queue_status.get("status_message"),
        )

        return {
            "success": True,
            "campaign_id": campaign_id,
            **queue_status,
        }

    except Exception as exc:
        logger.error("Failed to get audio queue for campaign %s: %s", campaign_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/audio/queue/{user_id}/{campaign_id}")
async def get_user_audio_queue(
    request: Request,
    user_id: str,
    campaign_id: str,
    current_user=optional_auth(),
):
    """Get pending audio chunks for a specific user in a campaign.

    This is the primary endpoint for user-scoped audio playback:
    - Returns all chunks the user hasn't played yet
    - Ordered by request time and sequence number
    - Client calls this on connect/reconnect
    - Client calls this when receiving 'audio_available' WebSocket notification

    Returns:
        chunks: List of pending chunk dicts with queue metadata
        total_chunks: int
        campaign_id: str
        user_id: str
    """
    from gaia.infra.audio.audio_playback_service import audio_playback_service

    logger.info(
        "[AUDIO_DEBUG] 🎬 GET /audio/queue/%s/%s - Frontend requesting user queue",
        user_id,
        campaign_id,
    )

    try:
        # Check session access
        session_registry = getattr(request.app.state, "session_registry", None)
        _ensure_session_access(session_registry, campaign_id, current_user)

        # Get user's pending queue from service
        chunks = audio_playback_service.get_user_pending_queue(user_id, campaign_id)

        logger.info(
            "[AUDIO_DEBUG] 🎯 Retrieved %d pending chunks for user %s in campaign %s",
            len(chunks),
            user_id,
            campaign_id,
        )

        return {
            "success": True,
            "campaign_id": campaign_id,
            "user_id": user_id,
            "chunks": chunks,
            "total_chunks": len(chunks),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get audio queue for user %s in campaign %s: %s",
            user_id,
            campaign_id,
            exc,
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/audio/played/{chunk_id}")
async def mark_audio_played(
    chunk_id: str,
    current_user=optional_auth(),
):
    """Mark an audio chunk as played (legacy - use /audio/user/played/{queue_id} instead).

    Called by frontend when audio playback completes.
    Updates database state and can trigger cleanup of old chunks.
    """
    from gaia.infra.audio.audio_playback_service import audio_playback_service

    try:
        success = audio_playback_service.mark_chunk_played(chunk_id)

        if not success:
            logger.warning("[AUDIO_API] Chunk %s not found or already played", chunk_id)
            raise HTTPException(status_code=404, detail="Chunk not found")

        logger.debug("[AUDIO_API] Marked chunk %s as played", chunk_id)

        return {
            "success": True,
            "chunk_id": chunk_id,
            "message": "Chunk marked as played",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to mark chunk %s as played: %s", chunk_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/audio/user/delivered/{queue_id}")
async def mark_user_chunk_delivered(
    queue_id: str,
    current_user=optional_auth(),
):
    """Mark a chunk as delivered to a user (user-scoped queue).

    Called when the client receives/acknowledges the chunk.
    Updates the user's queue entry with delivered timestamp.

    Args:
        queue_id: User queue entry UUID (from get_user_audio_queue response)
    """
    from gaia.infra.audio.audio_playback_service import audio_playback_service

    try:
        success = audio_playback_service.mark_chunk_delivered_to_user(queue_id)

        if not success:
            logger.warning("[AUDIO_API] Queue entry %s not found", queue_id)
            raise HTTPException(status_code=404, detail="Queue entry not found")

        logger.debug("[AUDIO_API] Marked queue entry %s as delivered", queue_id)

        return {
            "success": True,
            "queue_id": queue_id,
            "message": "Chunk marked as delivered",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to mark queue entry %s as delivered: %s", queue_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/audio/user/played/{queue_id}")
async def mark_user_chunk_played(
    queue_id: str,
    current_user=optional_auth(),
):
    """Mark a chunk as played by a user (user-scoped queue).

    Called when the client finishes playing the chunk.
    Updates the user's queue entry with played timestamp.

    Args:
        queue_id: User queue entry UUID (from get_user_audio_queue response)
    """
    from gaia.infra.audio.audio_playback_service import audio_playback_service

    try:
        success = audio_playback_service.mark_chunk_played_by_user(queue_id)

        if not success:
            logger.warning("[AUDIO_API] Queue entry %s not found", queue_id)
            raise HTTPException(status_code=404, detail="Queue entry not found")

        logger.debug("[AUDIO_API] Marked queue entry %s as played", queue_id)

        return {
            "success": True,
            "queue_id": queue_id,
            "message": "Chunk marked as played",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to mark queue entry %s as played: %s", queue_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/audio/stream/{campaign_id}")
async def stream_synchronized_audio(
    campaign_id: str,
    request: Request,
    current_user=optional_auth(),
):
    """Stream synchronized audio for a campaign.

    All clients listening to this stream will hear the same audio at the same time.
    This endpoint concatenates pending audio chunks into a continuous stream.

    Use WebSocket signaling to control playback (start/stop/position).
    Pass ?start_offset=<seconds> to begin playback near the live position.
    """
    from gaia.infra.audio.audio_artifact_store import audio_artifact_store

    try:
        # Check session access
        session_registry = getattr(request.app.state, "session_registry", None)
        _ensure_session_access(session_registry, campaign_id, current_user)

        start_offset_param = request.query_params.get("start_offset")
        start_offset = 0.0
        if start_offset_param:
            try:
                start_offset = max(0.0, float(start_offset_param))
            except ValueError:
                logger.warning(
                    "[AUDIO_STREAM] Invalid start_offset=%s for campaign %s; defaulting to 0",
                    start_offset_param,
                    campaign_id,
                )
                start_offset = 0.0

        # Get request_id to filter chunks for this specific audio generation session
        request_id = request.query_params.get("request_id")

        logger.info(
            "[AUDIO_STREAM] Starting progressive stream for campaign %s (request_id=%s)",
            campaign_id,
            request_id,
        )

        async def audio_stream_generator():
            """Generate continuous audio stream by yielding chunks as they become available."""
            import asyncio
            from datetime import datetime, timedelta
            from gaia.infra.audio.audio_playback_service import audio_playback_service

            # Mark request as STREAMING when playback actually starts
            if request_id:
                try:
                    # Get request details before marking as streaming
                    from sqlalchemy import select
                    from gaia.infra.audio.audio_models import AudioPlaybackRequest
                    session = audio_playback_service._get_session()
                    if session:
                        try:
                            import uuid
                            request_uuid = uuid.UUID(request_id)
                            stmt = select(AudioPlaybackRequest).where(AudioPlaybackRequest.request_id == request_uuid)
                            req = session.execute(stmt).scalar_one_or_none()
                            if req:
                                logger.info(
                                    "[AUDIO_DEBUG] 🎬 STARTING STREAM | request_id=%s campaign=%s chunks=%d text='%s'",
                                    request_id,
                                    campaign_id,
                                    req.total_chunks or 0,
                                    (req.text or "(no text)")[:200],
                                )
                        finally:
                            session.close()

                    audio_playback_service.mark_request_started(request_id)
                    logger.info(
                        "[AUDIO_STREAM] Marked request %s as STREAMING for campaign %s",
                        request_id,
                        campaign_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "[AUDIO_STREAM] Failed to mark request %s as STREAMING: %s",
                        request_id,
                        exc,
                    )

            streamed_chunk_ids = set()
            last_chunk_time = datetime.now()
            idle_timeout = timedelta(seconds=60)  # Keep stream alive longer for ongoing playback
            poll_interval = 0.1  # Poll for new chunks every 100ms
            remaining_offset = start_offset
            total_chunks_expected = None

            while True:
                # Get chunks from database via audio_playback_service
                chunks = audio_playback_service.get_pending_chunks(campaign_id)

                logger.debug(
                    "[AUDIO_DEBUG] 🔄 Stream polling | campaign=%s request_id=%s all_chunks=%d streamed=%d",
                    campaign_id,
                    request_id,
                    len(chunks),
                    len(streamed_chunk_ids),
                )

                # Filter by request_id if provided (only serve chunks from this generation session)
                if request_id:
                    chunks_before = len(chunks)
                    chunks = [c for c in chunks if c.get("request_id") == request_id]
                    logger.debug(
                        "[AUDIO_DEBUG] 🔍 Filtered by request_id | before=%d after=%d",
                        chunks_before,
                        len(chunks),
                    )

                # Get total_chunks from the database if not yet known
                if chunks and total_chunks_expected is None and request_id:
                    try:
                        from uuid import UUID
                        req_uuid = UUID(request_id)
                        session = audio_playback_service._get_session()
                        if session:
                            try:
                                from gaia.infra.audio.audio_models import AudioPlaybackRequest
                                from sqlalchemy import select
                                stmt = select(AudioPlaybackRequest).where(AudioPlaybackRequest.request_id == req_uuid)
                                req_obj = session.execute(stmt).scalar_one_or_none()
                                if req_obj and req_obj.total_chunks is not None:
                                    total_chunks_expected = req_obj.total_chunks
                                    logger.debug(
                                        "[AUDIO_DEBUG] 📊 Discovered total_chunks=%s for request_id=%s",
                                        total_chunks_expected,
                                        request_id,
                                    )
                            finally:
                                session.close()
                    except Exception as exc:
                        logger.warning("Failed to get total_chunks: %s", exc)

                # Find chunks we haven't streamed yet
                new_chunks = [c for c in chunks if c.get("chunk_id") not in streamed_chunk_ids]

                if new_chunks:
                    logger.info(
                        "[AUDIO_DEBUG] 📦 Found %d new chunks | streamed=%d/%s",
                        len(new_chunks),
                        len(streamed_chunk_ids),
                        total_chunks_expected or "?",
                    )

                if new_chunks:
                    last_chunk_time = datetime.now()

                    for chunk in new_chunks:
                        try:
                            # Extract filename from URL or storage_path
                            url = chunk.get("url", "")
                            storage_path = chunk.get("storage_path", "")
                            url_parts = url.split("/") if url else storage_path.split("/")
                            filename = url_parts[-1] if url_parts else chunk.get("artifact_id", "")

                            duration_sec = float(chunk.get("duration_sec") or 0.0)
                            size_bytes = int(chunk.get("size_bytes") or 0)
                            skip_bytes = 0

                            if remaining_offset > 0:
                                if duration_sec > 0 and size_bytes > 0:
                                    if remaining_offset >= duration_sec:
                                        remaining_offset = max(0.0, remaining_offset - duration_sec)
                                        streamed_chunk_ids.add(chunk["chunk_id"])
                                        logger.debug(
                                            "[AUDIO_STREAM] Skipping entire chunk %s (remaining_offset=%.2fs)",
                                            chunk["chunk_id"],
                                            remaining_offset,
                                        )
                                        continue
                                    ratio = min(1.0, remaining_offset / duration_sec)
                                    skip_bytes = min(
                                        max(size_bytes - 1, 0),
                                        max(0, int(round(ratio * size_bytes))),
                                    )
                                    remaining_offset = 0.0
                                    logger.debug(
                                        "[AUDIO_STREAM] Skipping %d bytes of chunk %s to honour start_offset",
                                        skip_bytes,
                                        chunk["chunk_id"],
                                    )
                                else:
                                    # Duration unknown, cannot accurately skip - reset offset
                                    logger.debug(
                                        "[AUDIO_STREAM] Cannot apply start_offset (missing metadata) for chunk %s",
                                        chunk["chunk_id"],
                                    )
                                    remaining_offset = 0.0

                            # Read audio bytes from artifact store
                            audio_bytes = audio_artifact_store.read_artifact_bytes(campaign_id, filename)

                            if audio_bytes:
                                if skip_bytes > 0:
                                    audio_bytes = audio_bytes[skip_bytes:]

                                logger.debug(
                                    "[AUDIO_STREAM] Streaming chunk %s (%d bytes)",
                                    chunk["chunk_id"],
                                    len(audio_bytes),
                                )
                                yield audio_bytes
                                streamed_chunk_ids.add(chunk["chunk_id"])
                            else:
                                logger.warning(
                                    "[AUDIO_STREAM] Empty audio bytes for chunk %s",
                                    chunk["chunk_id"],
                                )

                        except FileNotFoundError:
                            logger.warning(
                                "[AUDIO_STREAM] Chunk %s not found in artifact store, skipping",
                                chunk["chunk_id"],
                            )
                            continue
                        except Exception as exc:
                            logger.error(
                                "[AUDIO_STREAM] Error streaming chunk %s: %s",
                                chunk["chunk_id"],
                                exc,
                            )
                            continue

                # Check if all chunks have been streamed (when total_chunks is known)
                if total_chunks_expected is not None and len(streamed_chunk_ids) >= total_chunks_expected:
                    logger.info(
                        "[AUDIO_DEBUG] ✅ STREAM COMPLETE | request_id=%s chunks=%d/%d campaign=%s",
                        request_id,
                        len(streamed_chunk_ids),
                        total_chunks_expected,
                        campaign_id,
                    )
                    break

                # Check if we should stop (no new chunks for idle_timeout)
                if datetime.now() - last_chunk_time > idle_timeout:
                    logger.info(
                        "[AUDIO_STREAM] No new chunks for %s, ending stream (total chunks: %d)",
                        idle_timeout,
                        len(streamed_chunk_ids),
                    )
                    break

                # Wait before polling again
                await asyncio.sleep(poll_interval)

        return StreamingResponse(
            audio_stream_generator(),
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes",
                "X-Campaign-ID": campaign_id,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "[AUDIO_STREAM] Failed to create stream for campaign %s: %s",
            campaign_id,
            exc,
        )
        raise HTTPException(status_code=500, detail=str(exc))
