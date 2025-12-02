"""Utilities for working with Google authentication in a controlled way."""

from __future__ import annotations

from typing import Tuple, Optional

try:  # pragma: no cover - optional dependency guard
    import google.auth  # type: ignore
    from google.auth.credentials import Credentials  # type: ignore
    from google.auth.transport.requests import Request as GoogleAuthRequest  # type: ignore
    _GOOGLE_AUTH_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    google = None  # type: ignore
    Credentials = None  # type: ignore
    GoogleAuthRequest = None  # type: ignore
    _GOOGLE_AUTH_AVAILABLE = False

try:  # pragma: no cover - optional dependency guard
    import requests  # type: ignore
except Exception:  # pragma: no cover - import guard
    requests = None  # type: ignore


def get_default_credentials(
    timeout_seconds: float = 5.0,
) -> Tuple[Credentials, Optional[str]]:
    """
    Fetch default Google credentials using a session with an enforced timeout.

    Args:
        timeout_seconds: Timeout applied to metadata server HTTP requests.

    Returns:
        Tuple of (credentials, project_id)

    Raises:
        RuntimeError: If google-auth is not installed.
        Exception: Any error raised by google.auth.default.
    """
    if not _GOOGLE_AUTH_AVAILABLE or requests is None:
        raise RuntimeError("google-auth dependencies are not available")

    timeout_seconds = max(timeout_seconds, 0.1)

    class _TimeoutSession(requests.Session):  # type: ignore[misc]
        """Requests session that enforces a default timeout for all calls."""

        def __init__(self, timeout: float) -> None:
            super().__init__()
            self._timeout = timeout

        def request(self, *args, **kwargs):  # type: ignore[override]
            kwargs.setdefault("timeout", self._timeout)
            return super().request(*args, **kwargs)

    session = _TimeoutSession(timeout_seconds)
    request = GoogleAuthRequest(session=session)  # type: ignore[arg-type]
    return google.auth.default(request=request)  # type: ignore[return-value]


__all__ = ["get_default_credentials"]
