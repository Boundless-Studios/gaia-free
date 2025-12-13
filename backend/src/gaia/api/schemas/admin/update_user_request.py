"""Schema for user update request."""

from typing import Optional

from pydantic import BaseModel


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
