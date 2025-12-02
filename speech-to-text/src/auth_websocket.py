"""
WebSocket authentication handler with Auth0 support
"""

import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, Query, Header

from .auth0_jwt_verifier import get_auth0_verifier

logger = logging.getLogger(__name__)


async def websocket_auth_with_auth0(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None)
) -> Optional[Dict[str, Any]]:
    """
    Authenticate WebSocket connection with Auth0 support
    
    Tries Auth0 first, then falls back to legacy auth
    """
    # Extract token from various sources
    auth_token = None
    
    # 1. Try query parameter
    if token:
        auth_token = token
        logger.debug("Token found in query parameter")
    
    # 2. Try Authorization header
    elif authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
        else:
            auth_token = authorization
        logger.debug("Token found in Authorization header")
    
    # 3. Try WebSocket subprotocol header
    elif hasattr(websocket, 'headers'):
        subprotocols = websocket.headers.get('sec-websocket-protocol', '')
        if subprotocols:
            # Token might be passed as subprotocol
            parts = [p.strip() for p in subprotocols.split(',')]
            for part in parts:
                if part.lower().startswith('bearer '):
                    auth_token = part.split(' ', 1)[1]
                    logger.debug("Token found in WebSocket subprotocol (Bearer)")
                    break
                if part.startswith('token.'):
                    auth_token = part[6:]
                    logger.debug("Token found in WebSocket subprotocol (token.*)")
                    break
                # If it looks like a JWT (three dot-separated segments), accept it
                if part.count('.') == 2:
                    auth_token = part
                    logger.debug("Token found in WebSocket subprotocol (raw JWT)")
                    break
    
    # 4. Try cookie
    elif cookie:
        # Parse cookie for access_token
        cookies = {}
        for item in cookie.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        auth_token = cookies.get('access_token')
        if auth_token:
            logger.debug("Token found in cookie")
    
    if not auth_token:
        logger.debug("No authentication token found in WebSocket connection")
        # No token means no authentication
        return None
    
    # Try Auth0 verification only
    auth0_verifier = get_auth0_verifier()
    if auth0_verifier:
        user_info = auth0_verifier.verify_token(auth_token)
        if user_info:
            logger.info(f"Auth0 WebSocket authentication successful for user: {user_info.get('user_id')}")
            return user_info
        else:
            logger.debug("Auth0 token verification failed")
            return None
    else:
        logger.warning("Auth0 verifier not available")
        return None


# Export the new auth function
websocket_auth = websocket_auth_with_auth0
