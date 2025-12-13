"""Schema for user response."""

from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel, EmailStr

if TYPE_CHECKING:
    from auth.src.models import User


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    username: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_admin: bool
    is_active: bool
    # Registration fields
    registration_status: str
    eula_accepted_at: Optional[str]
    eula_version_accepted: Optional[str]
    registration_completed_at: Optional[str]
    created_at: Optional[str]
    last_login: Optional[str]

    @staticmethod
    def from_model(user: "User") -> "UserResponse":
        return UserResponse(
            user_id=str(user.user_id),
            email=user.email,
            username=user.username,
            display_name=getattr(user, "display_name", None),
            avatar_url=getattr(user, "avatar_url", None),
            is_admin=bool(getattr(user, "is_admin", False)),
            is_active=bool(getattr(user, "is_active", True)),
            registration_status=getattr(user, "registration_status", "pending"),
            eula_accepted_at=user.eula_accepted_at.isoformat() if user.eula_accepted_at else None,
            eula_version_accepted=getattr(user, "eula_version_accepted", None),
            registration_completed_at=user.registration_completed_at.isoformat() if user.registration_completed_at else None,
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login=user.last_login.isoformat() if user.last_login else None,
        )
