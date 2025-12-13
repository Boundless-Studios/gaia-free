"""Schema for auto-fill character request."""

from pydantic import BaseModel


class AutoFillCharacterRequest(BaseModel):
    """Request to auto-fill a character."""
    slot_id: int
