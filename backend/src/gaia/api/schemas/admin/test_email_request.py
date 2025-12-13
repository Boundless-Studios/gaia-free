"""Schema for test email request."""

from pydantic import BaseModel, EmailStr


class TestEmailRequest(BaseModel):
    email: EmailStr
    test_type: str = "welcome"  # welcome, registration_complete, or access_request
