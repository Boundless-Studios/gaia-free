"""Schema for user onboarding request."""

from pydantic import BaseModel


class OnboardUserRequest(BaseModel):
    """Request to onboard a user - marks them as active with completed registration."""
    send_welcome_email: bool = True
