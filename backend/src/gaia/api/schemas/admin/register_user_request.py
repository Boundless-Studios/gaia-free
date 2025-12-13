"""Schema for user registration request."""

from typing import Optional

from pydantic import BaseModel, EmailStr


class RegisterUserRequest(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False
    is_active: bool = True
