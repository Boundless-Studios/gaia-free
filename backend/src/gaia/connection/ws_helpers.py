"""WebSocket helper functions for authentication, authorization, and common patterns."""
import json
import logging
import uuid
from typing import Optional
from datetime import datetime
from fastapi import WebSocket, HTTPException
from sqlalchemy import select

from db.src.connection import db_manager
from auth.src.models import User as AuthUser, OAuthAccount, RegistrationStatus

logger = logging.getLogger(__name__)


async def send_error_and_close(websocket: WebSocket, code: int, reason: str) -> None:
    """Send error message and close WebSocket connection."""
    try:
        await websocket.accept(subprotocol=websocket.scope.get("subprotocol"))
    except Exception:
        pass
    try:
        await websocket.send_json({
            "type": "error",
            "code": code,
            "reason": reason
        })
    except Exception:
        pass
    await websocket.close(code=code, reason=reason)


def _extract_token_from_query(websocket: WebSocket, allow_query_token: bool) -> Optional[str]:
    """Extract token from query parameter if allowed."""
    if not allow_query_token:
        if websocket.query_params.get("token"):
            logger.warning(
                "Rejected token in query param on WS. origin=%s",
                websocket.headers.get("origin"),
            )
        return None
    return websocket.query_params.get("token")


def _extract_token_from_header(websocket: WebSocket) -> Optional[str]:
    """Extract token from Authorization header."""
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def _extract_token_from_cookie(websocket: WebSocket) -> Optional[str]:
    """Extract token from cookie."""
    try:
        from auth.src.cookies import ACCESS_TOKEN_COOKIE_NAME
        return websocket.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    except Exception:
        return None


def _extract_token_from_subprotocol(websocket: WebSocket) -> Optional[str]:
    """Extract token from Sec-WebSocket-Protocol header."""
    header_protocol = websocket.headers.get("sec-websocket-protocol")
    if not header_protocol:
        return None

    parts = [p.strip() for p in header_protocol.split(",")]
    for p in parts:
        if p.lower().startswith("bearer "):
            return p.split(" ", 1)[1]
        if p.count(".") == 2:  # looks like a JWT
            return p

    return None


async def extract_ws_token(websocket: WebSocket, allow_query_token: bool) -> Optional[str]:
    """Extract authentication token from WebSocket connection.

    Checks (in order):
    1. Query parameter (if allowed)
    2. Authorization header
    3. Cookie
    4. Subprotocol header

    Args:
        websocket: WebSocket connection
        allow_query_token: Whether to allow token in query parameters

    Returns:
        Token string or None if not found
    """
    # Try each extraction method in order
    token = _extract_token_from_query(websocket, allow_query_token)
    if token:
        logger.debug(
            "[WS-AUTH] Token found via query param (allowed=%s) origin=%s",
            allow_query_token,
            websocket.headers.get("origin"),
        )
        return token

    token = _extract_token_from_header(websocket)
    if token:
        logger.debug(
            "[WS-AUTH] Token found via Authorization header origin=%s",
            websocket.headers.get("origin"),
        )
        return token

    token = _extract_token_from_cookie(websocket)
    if token:
        logger.debug(
            "[WS-AUTH] Token found via cookie origin=%s",
            websocket.headers.get("origin"),
        )
        return token

    token = _extract_token_from_subprotocol(websocket)
    if token:
        logger.debug(
            "[WS-AUTH] Token found via subprotocol origin=%s",
            websocket.headers.get("origin"),
        )
    return token


class _WSUser:
    """Simple user object for WebSocket connections."""
    def __init__(
        self,
        *,
        gaia_user_id: str,
        email: Optional[str],
        auth0_user_id: Optional[str],
    ) -> None:
        # Canonical GAIA user ID (UUID string)
        self.user_id = gaia_user_id
        self.gaia_user_id = gaia_user_id
        self.email = email
        self.auth0_user_id = auth0_user_id


def _lookup_gaia_user(auth0_user_id: Optional[str], email: Optional[str]) -> Optional[AuthUser]:
    """Resolve the canonical GAIA user for a WebSocket token."""
    with db_manager.get_sync_session() as session:
        user: Optional[AuthUser] = None

        if auth0_user_id:
            oauth = session.execute(
                select(OAuthAccount).where(
                    OAuthAccount.provider == "auth0",
                    OAuthAccount.provider_account_id == auth0_user_id,
                )
            ).scalar_one_or_none()
            if oauth:
                user = session.get(AuthUser, oauth.user_id)

        if not user and email:
            user = session.execute(
                select(AuthUser).where(AuthUser.email == email)
            ).scalar_one_or_none()

        return user


def _build_ws_user_from_payload(payload: Optional[dict]) -> _WSUser:
    """Create a WS user object from a verified Auth0 payload."""
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication",
        )

    auth0_user_id = payload.get("user_id") or payload.get("sub")
    email = payload.get("email")

    user = _lookup_gaia_user(auth0_user_id, email)
    if not user:
        raise HTTPException(
            status_code=403,
            detail="User not registered",
        )

    if user.registration_status == RegistrationStatus.PENDING.value:
        raise HTTPException(
            status_code=403,
            detail="Registration incomplete",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User inactive",
        )

    return _WSUser(
        gaia_user_id=str(user.user_id),
        email=email or user.email,
        auth0_user_id=auth0_user_id,
    )


async def authenticate_ws_user_from_token(
    token: str
) -> Optional[_WSUser]:
    """Authenticate user from token string.

    Args:
        token: JWT token string

    Returns:
        User object if authentication successful

    Raises:
        HTTPException: If authentication fails
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # Verify token via Auth0 verifier
    from auth.src.auth0_jwt_verifier import get_auth0_verifier
    verifier = get_auth0_verifier()
    payload = verifier.verify_access_token(token) if verifier else None

    return _build_ws_user_from_payload(payload)


async def authenticate_ws_user(
    websocket: WebSocket,
    session_registry,
    session_id: str,
    allow_query_token: bool
) -> Optional[_WSUser]:
    """Authenticate WebSocket user if session requires ACL.

    Args:
        websocket: WebSocket connection
        session_registry: SessionRegistry instance
        session_id: Session/campaign ID
        allow_query_token: Whether to allow token in query parameters

    Returns:
        User object if authentication required and successful, None if no ACL required

    Raises:
        HTTPException: If authentication fails
    """
    # Check if access control applies (session has claims)
    requires_acl = False
    if session_registry:
        meta = session_registry.get_metadata(session_id)
        if meta and (
            meta.get("owner_user_id")
            or meta.get("owner_email")
            or (meta.get("member_user_ids") or [])
            or (meta.get("member_emails") or [])
        ):
            requires_acl = True

    # Extract token (even if ACL not required; we still map identity when provided)
    token = await extract_ws_token(websocket, allow_query_token)

    if not token:
        if requires_acl:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        return None

    # Verify token via Auth0 verifier
    from auth.src.auth0_jwt_verifier import get_auth0_verifier
    verifier = get_auth0_verifier()
    payload = verifier.verify_access_token(token) if verifier else None

    return _build_ws_user_from_payload(payload)


async def handle_common_ws_message(
    websocket: WebSocket,
    connection,
    message_type: str,
    data: dict,
    session_registry=None,
    session_id: str = None
) -> bool:
    """Handle common WebSocket message types (ping, heartbeat).

    Args:
        websocket: WebSocket connection
        connection: Connection object with last_heartbeat attribute
        message_type: Type of message
        data: Message data

    Returns:
        True if message was handled, False if not a common message type
    """
    if message_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })
        return True

    elif message_type == "heartbeat":
        connection.last_heartbeat = datetime.now()

        # Update connection registry if connection has registry_id
        if hasattr(connection, 'registry_connection_id') and connection.registry_connection_id:
            from gaia.connection.connection_registry import connection_registry
            import uuid
            try:
                connection_registry.update_heartbeat(uuid.UUID(connection.registry_connection_id))
            except Exception as exc:
                logger.debug(f"Failed to update connection registry heartbeat: {exc}")

        await websocket.send_json({
            "type": "heartbeat_ack",
            "timestamp": datetime.now().isoformat()
        })
        return True

    elif message_type == "auth":
        # Handle post-connection authentication
        token = data.get("token")
        if token:
            try:
                # Validate the token
                user_obj = await authenticate_ws_user_from_token(token)

                # Enforce session access if session_registry provided
                if session_registry and session_id and user_obj:
                    from fastapi import HTTPException
                    # Import the enforcement function
                    from gaia.api.app import _enforce_session_access
                    try:
                        _enforce_session_access(session_registry, session_id, user_obj)
                    except HTTPException as exc:
                        logger.warning(f"Session access denied: {exc.detail}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Access denied: {exc.detail}",
                            "timestamp": datetime.now().isoformat()
                        })
                        return True

                # Store authenticated user in connection
                if hasattr(connection, '__dict__') and user_obj:
                    connection.authenticated_user = user_obj
                    connection.user_id = user_obj.user_id
                    connection.user_email = user_obj.email
                    logger.info(
                        "[WS] Updated connection identity (user_id=%s email=%s)",
                        connection.user_id,
                        connection.user_email,
                    )
                    if hasattr(connection, "registry_connection_id") and connection.registry_connection_id:
                        from gaia.connection.connection_registry import connection_registry
                        try:
                            connection_registry.update_connection_identity(
                                uuid.UUID(connection.registry_connection_id),
                                connection.user_id,
                                connection.user_email,
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Failed to persist WS identity update: %s", exc)
                    callback = getattr(connection, "identity_update_callback", None)
                    if callable(callback):
                        try:
                            callback()
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Identity update callback failed: %s", exc)
                logger.debug(
                    "[WS] Auth message accepted: email=%s session=%s",
                    (user_obj.email if user_obj else "unknown"),
                    session_id or "unknown",
                )
                await websocket.send_json({
                    "type": "auth_ack",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"WebSocket auth failed: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Authentication failed: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
        else:
            await websocket.send_json({
                "type": "error",
                "message": "auth message requires token field",
                "timestamp": datetime.now().isoformat()
            })
        return True

    return False


async def ws_message_loop(
    websocket: WebSocket,
    connection,
    message_handler: callable,
    session_registry=None,
    session_id: str = None
) -> None:
    """Generic WebSocket message receiving loop.

    Args:
        websocket: WebSocket connection
        connection: Connection object
        message_handler: Async function to handle non-common messages
        session_registry: Optional session registry for ACL checks
        session_id: Optional session ID for ACL checks
    """
    while True:
        try:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                message_type = data.get("type")

                # Try common handlers first (includes auth)
                handled = await handle_common_ws_message(
                    websocket, connection, message_type, data,
                    session_registry, session_id
                )

                # If not a common message, pass to custom handler
                if not handled:
                    await message_handler(websocket, connection, message_type, data)

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {message}")

        except Exception as e:
            logger.error(f"Error receiving WebSocket message: {e}")
            break
