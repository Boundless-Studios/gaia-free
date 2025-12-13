"""Schema for auto-fill character response."""

from pydantic import BaseModel

from gaia.api.schemas.campaign.simple_character import SimpleCharacter


class AutoFillCharacterResponse(BaseModel):
    """Response from auto-filling a character."""
    success: bool = True
    character: SimpleCharacter
