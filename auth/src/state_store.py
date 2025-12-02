"""
OAuth2 state and PKCE management for CSRF protection and enhanced security
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class AuthorizationState:
    """Stores OAuth2 authorization state and PKCE parameters"""
    state: str
    code_verifier: Optional[str] = None
    code_challenge: Optional[str] = None
    nonce: Optional[str] = None  # For OpenID Connect
    redirect_uri: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))


class StateStore:
    """
    In-memory store for OAuth2 state and PKCE parameters.
    In production, consider using Redis or another persistent store.
    """
    
    def __init__(self):
        self._states: Dict[str, AuthorizationState] = {}
        
    def create_authorization_state(
        self, 
        provider: str,
        redirect_uri: str,
        use_pkce: bool = True,
        use_nonce: bool = False
    ) -> AuthorizationState:
        """
        Create and store a new authorization state
        
        Args:
            provider: OAuth2 provider name
            redirect_uri: Redirect URI for callback
            use_pkce: Whether to generate PKCE parameters
            use_nonce: Whether to generate a nonce (for OIDC)
            
        Returns:
            AuthorizationState object with generated parameters
        """
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        auth_state = AuthorizationState(
            state=state,
            provider=provider,
            redirect_uri=redirect_uri
        )
        
        # Generate PKCE parameters if requested
        if use_pkce:
            code_verifier = secrets.token_urlsafe(32)
            # Create code challenge using SHA256
            challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
            code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip('=')
            
            auth_state.code_verifier = code_verifier
            auth_state.code_challenge = code_challenge
        
        # Generate nonce if requested (for OpenID Connect)
        if use_nonce:
            auth_state.nonce = secrets.token_urlsafe(32)
        
        # Store the state
        self._states[state] = auth_state
        
        # Clean up expired states
        self._cleanup_expired()
        
        return auth_state
    
    def validate_state(self, state: str) -> Optional[AuthorizationState]:
        """
        Validate and retrieve authorization state
        
        Args:
            state: State parameter from OAuth2 callback
            
        Returns:
            AuthorizationState if valid, None otherwise
        """
        # Clean up expired states first
        self._cleanup_expired()
        
        # Retrieve and remove state (one-time use)
        auth_state = self._states.pop(state, None)
        
        if auth_state is None:
            return None
        
        # Check if state has expired
        if datetime.utcnow() > auth_state.expires_at:
            return None
        
        return auth_state
    
    def _cleanup_expired(self):
        """Remove expired states from the store"""
        now = datetime.utcnow()
        expired_states = [
            state for state, auth_state in self._states.items()
            if now > auth_state.expires_at
        ]
        for state in expired_states:
            del self._states[state]
    
    def get_stats(self) -> dict:
        """Get statistics about the state store"""
        self._cleanup_expired()
        return {
            "active_states": len(self._states),
            "providers": list(set(s.provider for s in self._states.values() if s.provider))
        }


# Global state store instance
# In production, this should be replaced with Redis or another persistent store
_state_store = StateStore()


def get_state_store() -> StateStore:
    """Get the global state store instance"""
    return _state_store