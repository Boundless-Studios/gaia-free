"""Campaign management service for Gaia API."""

import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException
import logging
from pathlib import Path
from datetime import datetime, timezone

from gaia.models.campaign import CampaignData, GameStyle, GameTheme
from gaia.models.character import CharacterInfo
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.api.routes.campaign_generation import PreGeneratedContent, CampaignInitializer
from gaia.api.routes.arena import create_arena_characters, create_arena_scene, build_arena_prompt
from gaia.infra.storage.scene_repository import SceneRepository
from gaia.api.schemas.campaign import (
    ActiveCampaignResponse,
    PlayerCampaignResponse,
    PlayerCampaignMessage
)
from gaia.api.schemas.chat import StructuredGameData, AudioArtifactPayload
import re

logger = logging.getLogger(__name__)

from db.src.connection import db_manager
from sqlalchemy import select
from gaia_private.session.session_models import CampaignSession, RoomSeat
from gaia_private.session.room_service import RoomService

def _extract_player_options_from_turn(structured_data: Dict[str, Any]) -> List[str]:
    """
    Extract numbered player options from the turn field and convert to a list.
    
    Args:
        structured_data: The structured data dictionary containing turn and player_options
        
    Returns:
        List of player options, or empty list if none found
    """
    # First check if player_options already exists and is not empty
    existing_options = structured_data.get("player_options")
    if existing_options:
        if isinstance(existing_options, list):
            return existing_options
        elif isinstance(existing_options, str) and existing_options.strip():
            return [existing_options.strip()]
    
    # Extract from turn field if player_options is empty/None
    turn_text = structured_data.get("turn", "")
    if not turn_text or not isinstance(turn_text, str):
        return []
    
    # Look for numbered options (1., 2., 3., etc. or 1) 2) 3) etc.)
    options = []
    
    # Pattern 1: Handle comma-separated numbered options like "1) Option, 2) Option, 3) Option"
    pattern1 = r'(\d+\)\s*[^,]+(?:,\s*\d+\)\s*[^,]+)*)'
    matches1 = re.findall(pattern1, turn_text)
    
    if matches1:
        # Split by comma and extract individual options
        for match in matches1:
            # Split by pattern that looks like "number) option"
            individual_options = re.findall(r'(\d+\)\s*[^,]+)', match)
            for option in individual_options:
                # Remove the number and parenthesis, clean up
                cleaned_option = re.sub(r'^\d+\)\s*', '', option).strip()
                if cleaned_option:
                    options.append(cleaned_option)
    
    # Pattern 2: "1. Option text" or "1) Option text" (line by line format)
    if not options:
        pattern2 = r'^\s*(\d+)[.)]\s*(.+?)(?=\n\s*\d+[.)]|\n\s*$|$)'
        matches2 = re.findall(pattern2, turn_text, re.MULTILINE | re.DOTALL)
        
        if matches2:
            for _, option_text in matches2:
                cleaned_option = option_text.strip()
                if cleaned_option:
                    options.append(cleaned_option)
    
    # Pattern 3: Look for bullet points or dashes if no numbered options found
    if not options:
        # Look for lines starting with bullet points, dashes, or asterisks
        pattern3 = r'^\s*[•\-\*]\s*(.+?)(?=\n|$)'
        matches3 = re.findall(pattern3, turn_text, re.MULTILINE)
        
        for match in matches3:
            cleaned_option = match.strip()
            if cleaned_option:
                options.append(cleaned_option)
    
    # Pattern 4: If still no options, look for lines that might be options (shorter lines)
    if not options:
        lines = turn_text.split('\n')
        for line in lines:
            line = line.strip()
            # Consider lines that are reasonably short and don't start with common narrative words
            if (10 <= len(line) <= 100 and 
                not line.lower().startswith(('the ', 'you ', 'as ', 'in ', 'on ', 'at ', 'with ', 'from '))):
                options.append(line)
    
    return options

# Request/Response models for API
class CreateCampaignRequest(BaseModel):
    """Request to create a new campaign."""
    name: str
    description: Optional[str] = None
    setting: Optional[str] = "Forgotten Realms"
    player_count: Optional[int] = 4
    game_style: Optional[str] = "balanced"

class UpdateCampaignRequest(BaseModel):
    """Request to update campaign metadata."""
    name: Optional[str] = None
    description: Optional[str] = None
    setting: Optional[str] = None
    player_count: Optional[int] = None
    status: Optional[str] = None

class AutoFillCampaignRequest(BaseModel):
    """Request for auto-filling campaign data."""
    style: Optional[str] = None

class AutoFillCharacterRequest(BaseModel):
    """Request for auto-filling character data."""
    slot_id: int
    character_name: Optional[str] = None  # Optional: specific character to use

class CharacterSlotRequest(BaseModel):
    """Configuration for a single character slot."""
    slot_id: int
    seat_id: Optional[str] = None
    use_pregenerated: bool = False
    character_data: Optional[Dict[str, Any]] = None

class CampaignInitializeRequest(BaseModel):
    """Request to initialize and start a campaign."""
    campaign_id: str
    campaign_info: Optional[Dict[str, Any]] = None
    use_pregenerated_campaign: bool = False
    character_slots: List[CharacterSlotRequest]

# Legacy models for backwards compatibility (can be removed once frontend is updated)
class CampaignGenerateRequest(BaseModel):
    """Legacy request model for generating a campaign."""
    theme: Optional[str] = None
    setting: Optional[str] = None
    style: Optional[str] = None

class CampaignQuickStartRequest(BaseModel):
    """Request model for quick-starting a campaign with all pre-generated content."""
    player_count: int = 4
    style: Optional[str] = None

class ArenaQuickStartRequest(BaseModel):
    """Request model for quick-starting an arena combat session."""
    player_count: int = 2  # Fixed at 2 players
    npc_count: int = 2     # Fixed at 2 NPCs
    difficulty: Optional[str] = "medium"  # easy, medium, hard, deadly


class CampaignService:
    """Campaign management service."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        # Use the campaign_manager from orchestrator
        self.campaign_manager: SimpleCampaignManager = orchestrator.campaign_manager
        self.services = getattr(orchestrator, "services", None)
        self.pregen_content = PreGeneratedContent()
        self.initializer = CampaignInitializer(self.pregen_content)
    
    async def list_campaigns(self, limit: int = 100, offset: int = 0, 
                           sort_by: str = "last_played", ascending: bool = False) -> Dict[str, Any]:
        """List all campaigns with pagination."""
        campaigns_result = self.campaign_manager.list_campaigns(
            sort_by=sort_by, 
            ascending=ascending, 
            limit=limit, 
            offset=offset
        )
        
        return {
            "campaigns": campaigns_result["campaigns"],
            "total": campaigns_result["total_count"],
            "limit": limit,
            "offset": offset
        }
    
    async def create_campaign(
        self,
        request: CreateCampaignRequest,
        *,
        owner_user_id: Optional[str] = None,
        owner_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new campaign with full production setup.

        Delegates core creation to SimpleCampaignManager.create_campaign(), then adds
        API-specific setup (world settings, room structure, ownership).
        """
        # Generate campaign ID
        campaign_id = self._get_next_campaign_id()

        # Use SimpleCampaignManager for core campaign creation
        result = self.campaign_manager.create_campaign(
            session_id=campaign_id,
            title=request.name,
            description=request.description or f"A new adventure in {request.setting}",
            game_style=request.game_style or "balanced",
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to create campaign")

        # Add API-specific setup: world settings and room structure
        max_player_seats = request.player_count or 4
        world_settings = {
            "setting": request.setting,
            "game_style": request.game_style,
            "description": request.description,
            "player_count": request.player_count,
        }

        self._persist_world_settings(campaign_id, world_settings, max_player_seats)
        self._ensure_room_structure(
            campaign_id,
            owner_user_id=owner_user_id,
            owner_email=owner_email,
            max_player_seats=max_player_seats,
        )

        logger.info(f"Created new campaign: {campaign_id}")

        return {
            "id": campaign_id,
            "name": result["title"],
            "description": result["description"],
            "created_at": result["created_at"],
            "campaign_id": campaign_id,
            "success": True
        }
    
    async def load_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Load a specific campaign."""
        campaign = self.campaign_manager.load_campaign(campaign_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
        
        # Convert to dict for API response
        campaign_dict = campaign.to_dict()
        
        # Load associated chat history if available
        history_files = self._find_chat_history(campaign_id)
        if history_files:
            campaign_dict["chat_history_files"] = history_files
        
        return campaign_dict
    
    async def save_campaign(self, campaign_id: str, auto_save: bool = False) -> Dict[str, Any]:
        """Save current campaign state."""
        # Load existing campaign
        campaign = self.campaign_manager.load_campaign(campaign_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
        
        # Extract current state from orchestrator
        if hasattr(self.orchestrator, 'get_campaign_state'):
            current_state = self.orchestrator.get_campaign_state(campaign_id)
            # Update campaign with current state
            # This would need to be implemented based on orchestrator design
        
        # Save campaign using campaign manager
        save_success = self.campaign_manager.save_campaign_data(campaign_id, campaign)
        
        if not save_success:
            raise HTTPException(status_code=500, detail="Failed to save campaign")
        
        return {
            "status": "saved",
            "campaign_id": campaign_id,
            "auto_save": auto_save
        }
    
    async def delete_campaign(self, campaign_id: str) -> Dict[str, str]:
        """Delete a campaign."""
        success = self.campaign_manager.delete_campaign(campaign_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
        
        return {"status": "deleted", "campaign_id": campaign_id}
    
    async def update_campaign(self, campaign_id: str, request: UpdateCampaignRequest) -> Dict[str, Any]:
        """Update campaign metadata."""
        campaign = self.campaign_manager.load_campaign(campaign_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
        
        # Track what was updated
        updated_fields = {}
        old_title = campaign.title
        
        # Update fields
        if request.name:
            campaign.title = request.name
            updated_fields["name"] = {"old": old_title, "new": request.name}
        if request.description:
            old_desc = campaign.description
            campaign.description = request.description
            updated_fields["description"] = {"old": old_desc, "new": request.description}
        if request.status == "archived":
            # Note: Archive functionality not yet implemented in SimpleCampaignManager
            return {"status": "archived", "campaign_id": campaign_id}
        
        # Save updated campaign
        save_success = self.campaign_manager.save_campaign_data(campaign_id, campaign)
        
        if not save_success:
            raise HTTPException(status_code=500, detail="Failed to save campaign")
        
        # Log the update
        if request.name:
            logger.info(f"📝 Campaign title updated: '{old_title}' -> '{request.name}' (ID: {campaign_id})")
            logger.info(f"📁 Note: Associated files remain named with campaign ID '{campaign_id}' for consistency")
        
        # Get file information
        file_info = self._build_campaign_file_info(campaign_id)
        
        return {
            "status": "updated",
            "campaign_id": campaign_id,
            "updated_fields": updated_fields,
            "file_info": file_info,
            "message": f"Campaign updated successfully. Files remain associated with campaign ID '{campaign_id}'."
        }
    
    def _find_chat_history(self, campaign_id: str) -> List[str]:
        """Find chat history files for a campaign."""
        chat_history_dir = Path("logs/chat_history")
        if not chat_history_dir.exists():
            return []
        
        # Find files matching the campaign ID
        matching_files = []
        for history_file in chat_history_dir.glob(f"{campaign_id}_*.json"):
            matching_files.append(str(history_file))
        
        return matching_files

    def _build_campaign_file_info(self, campaign_id: str) -> Dict[str, Any]:
        """Assemble campaign file locations using SimpleCampaignManager layout."""
        session_dir = self.campaign_manager.storage.resolve_session_dir(campaign_id)
        if not session_dir:
            return {
                "campaign_id": campaign_id,
                "files": {},
                "note": "Campaign has not been persisted yet."
            }

        data_dir = session_dir / "data"
        logs_dir = session_dir / "logs"
        characters_dir = data_dir / "characters"
        structured_dir = data_dir / "structured"
        turns_dir = data_dir / "turns"

        file_info = {
            "campaign_id": campaign_id,
            "files": {
                "data_dir": str(data_dir),
                "logs_dir": str(logs_dir),
                "characters_dir": str(characters_dir),
                "structured_dir": str(structured_dir),
                "turns_dir": str(turns_dir),
            },
            "note": "Paths reflect the per-campaign session directory managed by SimpleCampaignManager."
        }

        counts: Dict[str, int] = {}
        if structured_dir.exists():
            counts["structured_entries"] = len(list(structured_dir.glob("*.json")))
        if turns_dir.exists():
            counts["turn_files"] = len(list(turns_dir.glob("*.json")))
        if counts:
            file_info["file_counts"] = counts

        return file_info
    
    async def import_legacy_campaigns(self) -> Dict[str, Any]:
        """Import legacy chat history files as campaigns."""
        return {
            "imported": 0,
            "message": "Legacy campaign import is no longer supported; campaigns should be created via the current API."
        }
    
    async def get_structured_data(self, campaign_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get structured data for a campaign."""
        # Return empty structured data - this endpoint is called by frontend
        # but structured data is now embedded in messages
        return {
            "campaign_id": campaign_id,
            "entries": [],
            "total": 0
        }
    
    async def get_structured_data_summary(self, campaign_id: str) -> Dict[str, Any]:
        """Get a summary of structured data for a campaign."""
        # Return empty summary - structured data is now embedded in messages
        return {
            "campaign_id": campaign_id,
            "total_entries": 0,
            "last_updated": None
        }
    
    async def auto_fill_campaign(self, request: AutoFillCampaignRequest) -> Dict[str, Any]:
        """Get pre-generated campaign data for auto-fill."""
        campaign = self.pregen_content.get_random_campaign(request.style)
        
        return {
            "success": True,
            "campaign": {
                "title": campaign.get("title", ""),
                "description": campaign.get("description", ""),
                "game_style": "balanced",
                "setting": campaign.get("setting", ""),
                "theme": campaign.get("theme", ""),
                "starting_location": campaign.get("starting_location", ""),
                "main_conflict": campaign.get("main_conflict", ""),
                "key_npcs": campaign.get("key_npcs", []),
                "potential_quests": campaign.get("potential_quests", [])
            }
        }
    
    async def auto_fill_character(self, request: AutoFillCharacterRequest) -> Dict[str, Any]:
        """Get pre-generated character data for auto-fill."""
        if request.character_name:
            # Get specific character by name
            character = self.pregen_content.get_character_by_name(request.character_name)
            if not character:
                # Fall back to random if name not found
                logger.warning(f"Character '{request.character_name}' not found, using random")
                character = self.pregen_content.get_random_character()
        else:
            # Get random character
            character = self.pregen_content.get_random_character()

        return {
            "success": True,
            "character": character,
            "stored": False  # Not stored until campaign is finalized
        }

    async def list_pregenerated_characters(self) -> Dict[str, Any]:
        """Get all pre-generated characters."""
        characters = self.pregen_content.get_all_characters()

        return {
            "success": True,
            "characters": characters,
            "total": len(characters)
        }

    def _process_character_slots(self, character_slots: List[CharacterSlotRequest]) -> List[Dict[str, Any]]:
        """Process character slots, handling both pre-generated and user-provided characters.

        Args:
            character_slots: List of character slot configurations

        Returns:
            List of processed character data dictionaries
        """
        characters = []
        used_pregen_indices = set()

        for slot in character_slots:
            # Always use provided character data if available
            if slot.character_data:
                char = slot.character_data.copy()
                char['slot_id'] = slot.slot_id
                if slot.seat_id:
                    char['seat_id'] = slot.seat_id
                characters.append(char)

                # Track which pregenerated character was used to prevent duplicates
                if slot.use_pregenerated:
                    # Find the index of this character in the pregen list
                    char_name = char.get('name', '')
                    for idx, pregen_char in enumerate(self.pregen_content.characters):
                        if pregen_char.get('name') == char_name:
                            used_pregen_indices.add(idx)
                            break
                    logger.info(f"   Slot {slot.slot_id}: Using pre-gen character '{char_name}' (unmodified)")
                else:
                    logger.info(f"   Slot {slot.slot_id}: Using provided character '{char.get('name')}'")
            elif slot.use_pregenerated:
                # Fallback: get random pre-generated character if no data provided
                chars = self.pregen_content.get_random_characters(1, used_pregen_indices)
                if chars:
                    char = chars[0]
                    char['slot_id'] = slot.slot_id
                    if slot.seat_id:
                        char['seat_id'] = slot.seat_id
                    characters.append(char)

                    # Track which character was selected to prevent duplicates
                    char_name = char.get('name', '')
                    for idx, pregen_char in enumerate(self.pregen_content.characters):
                        if pregen_char.get('name') == char_name:
                            used_pregen_indices.add(idx)
                            logger.info(f"   Slot {slot.slot_id}: Using random pre-gen character '{char_name}' (index {idx})")
                            break

        return characters

    async def _generate_first_turn_async(self, campaign_id: str, initial_prompt: str, campaign_info: Dict, characters: List[Dict]) -> None:
        """Generate the first turn asynchronously and broadcast via WebSocket.

        This method runs in the background to avoid blocking the initialize_campaign response.
        The generated narrative is broadcast to connected clients via WebSocket.

        Args:
            campaign_id: The campaign identifier
            initial_prompt: The initial campaign prompt
            campaign_info: Campaign metadata
            characters: List of character data
        """
        try:
            logger.info(f"🎬 Starting async first turn generation for {campaign_id}")

            # Run the first turn through orchestrator
            broadcaster = getattr(self.orchestrator, "campaign_broadcaster", None)
            logger.info(
                f"[CAMPAIGN_START_FLOW] Broadcaster obtained from orchestrator | campaign_id={campaign_id} broadcaster_available={broadcaster is not None}"
            )
            if broadcaster:
                logger.info(
                    f"[CAMPAIGN_START_FLOW] Broadcaster type: {type(broadcaster).__name__}"
                )
            result = await self.orchestrator.run_campaign(
                user_input=initial_prompt,
                campaign_id=campaign_id,
                broadcaster=broadcaster,
            )
            logger.info(
                f"[CAMPAIGN_START_FLOW] orchestrator.run_campaign completed | campaign_id={campaign_id} has_result={result is not None}"
            )

            # The orchestrator already broadcasts via WebSocket in its run_campaign method
            logger.info(f"✅ First turn generated for {campaign_id}")

        except Exception as e:
            logger.error(f"❌ Error generating first turn for {campaign_id}: {e}")
            # Broadcast error to frontend via WebSocket
            if hasattr(self.orchestrator, 'campaign_broadcaster') and self.orchestrator.campaign_broadcaster:
                try:
                    await self.orchestrator.campaign_broadcaster.broadcast_campaign_update(
                        campaign_id,
                        "initialization_error",
                        {"error": str(e), "campaign_id": campaign_id}
                    )
                except Exception as broadcast_error:
                    logger.error(f"Failed to broadcast initialization error: {broadcast_error}")

    async def initialize_campaign(self, request: CampaignInitializeRequest) -> Dict[str, Any]:
        """Initialize a campaign with full context and send the opening prompt."""
        logger.info(f"🎮 Initializing campaign: {request.campaign_id}")
        logger.info(f"   Pre-gen campaign: {request.use_pregenerated_campaign}")
        
        # Get campaign info
        if request.use_pregenerated_campaign:
            campaign_info = self.pregen_content.get_random_campaign()
            logger.info(f"   Selected pre-gen campaign: {campaign_info.get('title')}")
        else:
            campaign_info = request.campaign_info or {}
            logger.info(f"   Using provided campaign: {campaign_info.get('title', 'Custom Campaign')}")
        
        # Process characters (simple format)
        characters = self._process_character_slots(request.character_slots)

        # Normalize portrait/visual metadata before persisting characters
        if characters:
            # Check for missing portraits
            characters_without_portraits = [
                char for char in characters
                if not char.get('portrait_url') and not char.get('portrait_path')
            ]

            if characters_without_portraits:
                character_names = ', '.join(
                    char.get('name', 'Unnamed character')
                    for char in characters_without_portraits
                )
                logger.warning(
                    "⚠️ Proceeding without portraits for characters: %s",
                    character_names
                )
            else:
                logger.info("✅ All characters have portraits")

            # Apply default values for missing visual metadata
            default_visual_values = {
                'gender': 'non-binary',
                'facial_expression': 'determined',
                'build': 'average'
            }

            for char in characters:
                char_name = char.get('name', 'Unnamed character')
                applied_defaults = []

                for field, default_value in default_visual_values.items():
                    if not char.get(field):
                        char[field] = default_value
                        applied_defaults.append(f"{field}={default_value}")

                if applied_defaults:
                    logger.info(f"   Applied defaults to {char_name}: {', '.join(applied_defaults)}")

            logger.info(f"✅ Normalized visual metadata for {len(characters)} characters")

        # Load or create campaign data
        campaign_data = self.campaign_manager.load_campaign(request.campaign_id)
        if not campaign_data:
            # Create new campaign if it doesn't exist
            campaign_data = CampaignData(
                campaign_id=request.campaign_id,
                title=campaign_info.get('title', 'Adventure'),
                description=campaign_info.get('description', ''),
                game_style=self._parse_game_style(campaign_info.get('game_style', 'balanced')),
                game_theme=GameTheme.FANTASY
            )
        
        # Get CharacterManager for this campaign
        character_manager = self.campaign_manager.get_character_manager(request.campaign_id)
        created_characters = character_manager.create_characters_from_slots(characters)

        # Persist characters to campaign data structure
        character_manager.persist_to_campaign(campaign_data)

        # CRITICAL: Actually persist characters to storage!
        character_manager.persist_characters()

        # Persist updated campaign data (including character roster)
        if hasattr(self.campaign_manager, "save_campaign_data"):
            self.campaign_manager.save_campaign_data(request.campaign_id, campaign_data)

        # Save campaign with characters
        self.campaign_manager.save_campaign(request.campaign_id, [], name=campaign_data.title)

        # GAME ROOM: Assign pre-created characters to room seats
        # This is optional - if DM didn't create characters, seats remain empty for players to claim
        if created_characters:
            logger.info(f"Assigning {len(created_characters)} pre-created characters to room seats")
            try:
                # db_manager is already imported at the top of the file
                db_manager.initialize()
                with db_manager.get_sync_session() as db_session:
                    room_service = RoomService(db_session)

                    # Get all player seats for this campaign
                    from sqlalchemy import select
                    stmt = (
                        select(RoomSeat)
                        .where(
                            RoomSeat.campaign_id == request.campaign_id,
                            RoomSeat.seat_type == 'player'
                        )
                        .order_by(RoomSeat.slot_index)
                    )
                    player_seats = list(db_session.execute(stmt).scalars().all())

                    # Map each created character to its corresponding seat by slot_index
                    for idx, (char_info, slot_id) in enumerate(created_characters):
                        character_id = getattr(char_info, 'character_id', None)
                        effective_slot = slot_id if slot_id is not None else idx
                        preferred_seat_id = None
                        if idx < len(characters):
                            preferred_seat_id = characters[idx].get('seat_id')

                        if character_id is None:
                            continue

                        matching_seat = None
                        if preferred_seat_id:
                            matching_seat = next(
                                (seat for seat in player_seats if str(seat.seat_id) == preferred_seat_id),
                                None
                            )
                        if not matching_seat:
                            matching_seat = next(
                                (seat for seat in player_seats if seat.slot_index == effective_slot),
                                None
                            )

                        if matching_seat and not matching_seat.character_id:
                            matching_seat.character_id = character_id
                            logger.info(
                                f"  ✓ Assigned character {character_id} (slot {effective_slot}) "
                                f"to seat {matching_seat.seat_id}"
                            )

                    db_session.commit()
                    logger.info("✅ Characters successfully assigned to seats")
            except Exception as exc:
                logger.warning(f"Failed to assign characters to seats: {exc}", exc_info=True)
        
        # Store character manager for orchestrator access
        if hasattr(self.orchestrator, 'set_character_manager'):
            self.orchestrator.set_character_manager(character_manager)
            if hasattr(self.orchestrator, 'set_campaign_data'):
                self.orchestrator.set_campaign_data(campaign_data)

        # Skip first-turn generation; DM will start campaign later
        logger.info(
            "🕒 Campaign %s initialized in setup state. Awaiting DM start.",
            request.campaign_id,
        )

        return {
            "success": True,
            "campaign_id": request.campaign_id,
            "campaign_info": campaign_info,
            "characters": characters,
            "initializing": False,
            "campaign_status": "setup",
            "message": "Campaign saved. Use the room management panel to start when ready."
        }
    
    async def quick_start_campaign(self, request: CampaignQuickStartRequest) -> Dict[str, Any]:
        """Quick-start a new campaign with all pre-generated content."""
        try:
            # Generate a new campaign ID
            campaign_id = self._get_next_campaign_id()

            # Get pre-generated campaign
            campaign_info = self.pregen_content.get_random_campaign(request.style)

            # Get pre-generated characters
            characters = self.pregen_content.get_random_characters(request.player_count)

            # Create the campaign in storage
            campaign_data = CampaignData(
                campaign_id=campaign_id,
                title=campaign_info.get("title", "Quick Adventure"),
                description=campaign_info.get("description", "A quick-start adventure"),
                game_style=GameStyle.BALANCED,
                game_theme=GameTheme.FANTASY
            )

            # Save the campaign
            save_success = self.campaign_manager.save_campaign(
                campaign_id,
                [],
                name=campaign_data.title
            )

            if not save_success:
                raise HTTPException(status_code=500, detail="Failed to create campaign")

            # Build and send the initial prompt
            initial_prompt = self.initializer.build_initial_prompt(campaign_info, characters)

            # Run the campaign with the initial prompt
            result = await self.orchestrator.run_campaign(
                user_input=initial_prompt,
                campaign_id=campaign_id
            )

            return {
                "success": True,
                "campaign_id": campaign_id,
                "campaign_info": campaign_info,
                "characters": characters,
                "response": result.get("response", ""),
                "message": "Campaign quick-started successfully!"
            }

        except Exception as e:
            logger.error(f"Error quick-starting campaign: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to quick-start campaign: {str(e)}")

    async def arena_quick_start(self, request: ArenaQuickStartRequest, user_id: str) -> Dict[str, Any]:
        """Quick-start an arena combat session with 2 players vs 2 NPCs."""
        try:
            # Generate a new campaign ID
            campaign_id = self._get_next_campaign_id()

            # Create arena campaign data
            campaign_data = CampaignData(
                campaign_id=campaign_id,
                title="Arena Combat",
                description="A gladiatorial combat in the grand arena!",
                game_style=GameStyle.COMBAT_HEAVY,
                game_theme=GameTheme.FANTASY
            )

            # Create arena characters using dedicated arena setup module
            arena_characters, arena_npcs = create_arena_characters()

            # Get CharacterManager for this campaign
            character_manager = self.campaign_manager.get_character_manager(campaign_id)

            # Create all combatants (PCs and NPCs) in one call
            # The method auto-detects NPCs based on the 'hostile' flag
            all_combatants = character_manager.create_characters_from_slots(arena_characters + arena_npcs)
            combatant_infos = [char_info for char_info, _ in all_combatants]

            # Persist characters and NPCs to campaign data structure
            character_manager.persist_to_campaign(campaign_data)

            # Actually persist characters to storage
            character_manager.persist_characters()

            # Save the campaign with characters
            save_success = self.campaign_manager.save_campaign(
                campaign_id,
                [],
                name=campaign_data.title
            )

            if not save_success:
                raise HTTPException(status_code=500, detail="Failed to create arena campaign")

            # Create arena scene with proper character roster
            arena_scene = create_arena_scene(campaign_id, combatant_infos, request.difficulty or "medium")

            # Save scene to database (source of truth)
            import uuid
            scene_repo = SceneRepository()
            try:
                campaign_uuid = uuid.UUID(campaign_id) if isinstance(campaign_id, str) else campaign_id
                await scene_repo.create_scene(arena_scene, campaign_uuid)
                logger.info(f"Created arena scene in database: {arena_scene.scene_id}")
            except Exception as e:
                logger.error(f"Failed to save arena scene to database: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to create arena scene: {e}")

            # Set as current scene in runtime cache (for session state)
            if hasattr(self.orchestrator, 'campaign_runner') and hasattr(self.orchestrator.campaign_runner, 'scene_integration'):
                scene_summary = {
                    'scene_id': arena_scene.scene_id,
                    'title': arena_scene.title,
                    'description': arena_scene.description,
                    'scene_type': arena_scene.scene_type,
                    'pcs_present': arena_scene.pcs_present,
                    'npcs_present': arena_scene.npcs_present,
                    'participants': [p.model_dump() if hasattr(p, 'model_dump') else vars(p) for p in arena_scene.participants],
                }
                self.orchestrator.campaign_runner.scene_integration.current_scenes[campaign_id] = scene_summary
                logger.info(f"Created arena scene: {arena_scene.scene_id} with {len(arena_scene.participants)} participants")

            # Build arena combat prompt
            arena_prompt = build_arena_prompt(request.difficulty or "medium")

            # Run the campaign with the arena prompt
            result = await self.orchestrator.run_campaign(
                user_input=arena_prompt,
                campaign_id=campaign_id
            )

            logger.info(f"Arena combat session created: {campaign_id} for user {user_id}")

            return {
                "success": True,
                "campaign_id": campaign_id,
                "title": "Arena Combat",
                "description": "2v2 gladiatorial combat",
                "response": result.get("response", ""),
                "message": "Arena combat initiated! Let the battle begin!"
            }

        except Exception as e:
            logger.error(f"Error creating arena combat: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start arena combat: {str(e)}")
    
    async def get_campaign_file_info(self, campaign_id: str) -> Dict[str, Any]:
        """Get information about files associated with a campaign."""
        campaign = self.campaign_manager.load_campaign(campaign_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
        
        file_info = self.campaign_manager.get_campaign_file_info(campaign_id)
        
        return {
            "campaign_id": campaign_id,
            "campaign_title": campaign.title,
            "file_info": file_info
        }

    def _get_campaign_data(self, campaign_id: str) -> Dict[str, Any]:
        """
        Extract common campaign data logic shared between load and read operations.
        
        This method handles:
        - Loading campaign history from disk
        - Extracting structured data from the last assistant message
        - Determining if the campaign needs an AI response
        - Creating default structured data if none exists
        
        Args:
            campaign_id: The campaign identifier
            
        Returns:
            Dictionary containing messages, structured_data, and needs_response flag
            
        Raises:
            HTTPException: If campaign not found or has no history
        """
        # Load campaign history from the campaign manager
        messages = self.campaign_manager.load_campaign_history(campaign_id)

        # For newly created campaigns with no history, return empty data instead of error
        if not messages:
            logger.info(f"Campaign {campaign_id} has no history yet (newly created)")
            return {
                "messages": [],
                "structured_data": {},
                "needs_response": False
            }
        
        # Check if the last message was from the user (needs AI response)
        needs_response = False
        if messages and messages[-1].get("role") == "user":
            needs_response = True
            logger.info(f"📝 Last message was from user, campaign needs AI response")
        
        # Extract the last assistant message's structured data
        structured_data = None
        last_dm_message = None
        
        # Find the last assistant message by searching backwards through history
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_dm_message = msg
                break
        
        # Extract structured data from the last DM message
        if last_dm_message:
            content = last_dm_message.get("content", "")
            # If content is already a dict (structured data), use it directly
            if isinstance(content, dict):
                structured_data = content
            else:
                # Try to parse it as JSON
                try:
                    import json
                    structured_data = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    # If not JSON, create a simple structure with the text content
                    structured_data = {
                        "answer": content,
                        "narrative": content,
                        "turn": "",
                        "status": "",
                        "combat_status": None,
                        "combat_state": None
                    }
        
        # If no structured data found, create a default welcome message
        if not structured_data:
            structured_data = {
                "answer": "Campaign loaded successfully. Please continue your adventure.",
                "narrative": "Your adventure continues...",
                "turn": "",
                "status": "",
                "combat_status": None,
                "combat_state": None
            }
        
        return {
            "messages": messages,
            "structured_data": structured_data,
            "needs_response": needs_response
        }

    def _build_campaign_response(self, campaign_id: str, data: Dict[str, Any], activated: bool) -> Dict[str, Any]:
        """
        Build the standardized campaign response object.
        
        This method creates a consistent response format for both load and read operations,
        with appropriate flags based on whether the campaign was activated.
        
        Args:
            campaign_id: The campaign identifier
            data: Dictionary containing messages, structured_data, and needs_response from _get_campaign_data
            activated: Whether the campaign was activated in the orchestrator
            
        Returns:
            Standardized campaign response dictionary
        """
        return {
            "structured_data": data["structured_data"],
            "session_id": campaign_id,
            "campaign_id": campaign_id,
            "timestamp": datetime.now().isoformat(),
            "success": activated if activated else True,  # Always successful for read operations
            "activated": activated,  # Key difference between load and read
            "messages": data["messages"],  # Include for backward compatibility
            "message_count": len(data["messages"]),
            "needs_response": data["needs_response"] if activated else False  # Only DM view needs responses
        }

    async def load_simple_campaign(self, campaign_id: str, *, orchestrator=None) -> Dict[str, Any]:
        """
        Load a campaign and activate it in the orchestrator for DM use.
        
        This method:
        - Activates the campaign in the orchestrator (loads history and characters)
        - Extracts campaign data and structured information
        - Returns data formatted for the DM interface
        
        Args:
            campaign_id: The campaign identifier
            
        Returns:
            Campaign data with activated=True and needs_response flag set appropriately
        """
        # Choose orchestrator (session-scoped if provided)
        orch = orchestrator or self.orchestrator

        # Check if campaign is already active to prevent duplicate activation
        if hasattr(orch, 'active_campaign_id') and orch.active_campaign_id == campaign_id:
            logger.info(f"Campaign {campaign_id} is already active, skipping duplicate activation")
            # Get the common campaign data without re-activating
            data = self._get_campaign_data(campaign_id)
            return self._build_campaign_response(campaign_id, data, activated=True)
        
        # Activate the campaign in the orchestrator (loads history and characters)
        activated = await orch.activate_campaign(campaign_id)
        
        # Get the common campaign data
        data = self._get_campaign_data(campaign_id)
        
        # Build response with activation flags
        return self._build_campaign_response(campaign_id, data, activated=True)

    async def read_simple_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Read a campaign without activating it in the orchestrator (for player view).
        
        This method:
        - Loads campaign data from disk without activating it in the orchestrator
        - Extracts structured data and message history
        - Returns data formatted for the player interface (read-only)
        
        Args:
            campaign_id: The campaign identifier
            
        Returns:
            Campaign data with activated=False and needs_response=False for player view
        """
        # Get the common campaign data without activation
        data = self._get_campaign_data(campaign_id)
        
        # Build response without activation flags
        return self._build_campaign_response(campaign_id, data, activated=False)

    async def get_active_campaign_structured(self) -> ActiveCampaignResponse:
        """
        Get the currently active campaign ID using structured response.
        
        Returns:
            ActiveCampaignResponse with the active campaign ID
        """
        active_id = self.orchestrator.get_active_campaign_id()
        return ActiveCampaignResponse(active_campaign_id=active_id)

    async def read_campaign_structured(self, campaign_id: str) -> PlayerCampaignResponse:
        """
        Read campaign data for player view using structured response.
        
        Args:
            campaign_id: The campaign identifier
            
        Returns:
            PlayerCampaignResponse with structured campaign data
        """
        # Get the raw campaign data
        data = self._get_campaign_data(campaign_id)
        
        # Convert structured data to StructuredGameData
        structured_data = data.get("structured_data", {})
        
        # Helper to ensure dict fields are actually dicts or None
        def ensure_dict_or_none(value):
            if value is None or value == "":
                return None
            if isinstance(value, dict):
                return value
            # If it's a string or other non-dict, return None to avoid validation errors
            return None

        audio_payload: Optional[AudioArtifactPayload] = None
        audio_raw = structured_data.get("audio")
        if isinstance(audio_raw, AudioArtifactPayload):
            audio_payload = audio_raw
        elif isinstance(audio_raw, dict):
            try:
                audio_payload = AudioArtifactPayload(**audio_raw)
            except ValidationError as exc:
                logger.warning("Failed to parse audio payload for campaign %s: %s", campaign_id, exc)
            except Exception as exc:  # noqa: BLE001 - defensive guard
                logger.warning("Unexpected error parsing audio payload for campaign %s: %s", campaign_id, exc)

        player_state = StructuredGameData(
            narrative=structured_data.get("narrative") or "",
            turn=structured_data.get("turn") or "",
            status=structured_data.get("status") or None,  # Can be dict or None
            characters=structured_data.get("characters") or None,  # Can be list or None
            turn_info=ensure_dict_or_none(structured_data.get("turn_info")),
            combat_status=ensure_dict_or_none(structured_data.get("combat_status")),
            combat_state=ensure_dict_or_none(structured_data.get("combat_state")),
            action_breakdown=structured_data.get("action_breakdown") or None,  # Action breakdown - convert "" to None
            turn_resolution=structured_data.get("turn_resolution") or None,  # Turn resolution - convert "" to None
            environmental_conditions=structured_data.get("environmental_conditions") or "",
            immediate_threats=structured_data.get("immediate_threats") or "",
            story_progression=structured_data.get("story_progression") or "",
            # Include answer and player_options for player view
            answer=structured_data.get("answer") or "",
            player_options=_extract_player_options_from_turn(structured_data),
            # Image generation fields (may be used in player view)
            generated_image_url=structured_data.get("generated_image_url") or "",
            generated_image_path=structured_data.get("generated_image_path") or "",
            generated_image_prompt=structured_data.get("generated_image_prompt") or "",
            generated_image_type=structured_data.get("generated_image_type") or "",
            audio=audio_payload,
        )
        
        # Convert messages to PlayerCampaignMessage
        messages = []
        for msg in data.get("messages", []):
            player_msg = PlayerCampaignMessage(
                message_id=msg.get("message_id", ""),
                timestamp=datetime.fromisoformat(msg.get("timestamp", datetime.now().isoformat())),
                role=msg.get("role", ""),
                content=msg.get("content"),  # Can be complex object
                agent_name=msg.get("agent_name")
            )
            messages.append(player_msg)
        
        return PlayerCampaignResponse(
            success=True,
            campaign_id=campaign_id,
            session_id=campaign_id,
            timestamp=datetime.now(),
            activated=False,  # Always False for player view
            needs_response=False,  # Always False for player view
            structured_data=player_state,
            messages=messages,
            message_count=len(messages)
        )

    async def load_structured_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Explicitly load a structured campaign using the legacy/structured manager."""
        campaign = self.campaign_manager.load_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail=f"Structured campaign {campaign_id} not found")
        return campaign.to_dict()

    async def start_campaign_from_seats(self, campaign_id: str, campaign_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a campaign by loading characters from room seats.

        This method is used for seat-based game rooms where characters are created
        by players before the campaign starts.

        Args:
            campaign_id: The campaign identifier
            campaign_info: Optional campaign metadata (title, description, setting)

        Returns:
            Dict with success status and initialization info
        """
        logger.info(f"🎮 Starting campaign from seats: {campaign_id}")

        # Load characters from room_seats
        from db.src.connection import db_manager
        from gaia_private.session.session_models import RoomSeat
        from sqlalchemy import select
        from datetime import datetime, timezone as tz

        characters: List[CharacterInfo] = []
        character_payloads: List[Dict[str, Any]] = []
        character_entries: List[Dict[str, Any]] = []
        try:
            with db_manager.get_sync_session() as db:
                session_row = db.get(CampaignSession, campaign_id)
                if session_row and session_row.campaign_status == "active":
                    logger.info(f"Campaign {campaign_id} is already active, skipping duplicate activation")
                    raise HTTPException(
                        status_code=409,
                        detail="Campaign already active"
                    )
                # Get all player seats with characters
                stmt = (
                    select(RoomSeat)
                    .where(
                        RoomSeat.campaign_id == campaign_id,
                        RoomSeat.seat_type == 'player',
                        RoomSeat.character_id.isnot(None)
                    )
                    .order_by(RoomSeat.slot_index)
                )
                seats = db.execute(stmt).scalars().all()

                if not seats:
                    raise HTTPException(
                        status_code=400,
                        detail="No characters found in seats. Players must create characters before starting."
                    )

                # Load character data for each seat
                character_manager = self.campaign_manager.get_character_manager(campaign_id)
                for seat in seats:
                    if seat.character_id:
                        char_data = character_manager.get_character(seat.character_id)
                        if char_data:
                            characters.append(char_data)
                            try:
                                character_payloads.append(char_data.to_dict())
                            except Exception:
                                # Fallback: best-effort conversion if to_dict is unavailable
                                character_payloads.append(character_manager.converter.to_dict(char_data))
                            character_entries.append(
                                {
                                    "seat_id": str(seat.seat_id),
                                    "slot_index": seat.slot_index,
                                    "character_id": seat.character_id,
                                    "character": char_data,
                                }
                            )
                        else:
                            logger.warning(f"Character {seat.character_id} not found for seat {seat.seat_id}")

                logger.info(f"✅ Loaded {len(characters)} characters from seats")

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Failed to load characters from seats: {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to load seat characters: {str(exc)}")

        if not characters:
            raise HTTPException(
                status_code=400,
                detail="No valid characters found. At least one character is required to start."
            )
        if not character_payloads:
            character_payloads = [char.to_dict() for char in characters]

        # Load or create campaign data
        campaign_data = self.campaign_manager.load_campaign(campaign_id)
        if not campaign_data:
            # Create new campaign if it doesn't exist
            campaign_info = campaign_info or {}
            campaign_data = CampaignData(
                campaign_id=campaign_id,
                title=campaign_info.get('title', 'Adventure'),
                description=campaign_info.get('description', ''),
                game_style=self._parse_game_style(campaign_info.get('game_style', 'balanced')),
                game_theme=GameTheme.FANTASY
            )

        # Use default campaign info if not provided
        if not campaign_info:
            # Load world settings (campaign metadata saved during create_campaign)
            world_settings = self._load_world_settings(campaign_id)
            campaign_info = {
                'title': campaign_data.title,
                'description': campaign_data.description,
                'setting': world_settings.get('setting', 'Forgotten Realms'),
                'game_style': campaign_data.game_style.value,
                # Load additional campaign metadata if available
                'theme': world_settings.get('theme', ''),
                'starting_location': world_settings.get('starting_location', ''),
                'main_conflict': world_settings.get('main_conflict', ''),
                'key_npcs': world_settings.get('key_npcs', []),
                'potential_quests': world_settings.get('potential_quests', [])
            }

        # Persist campaign data (ensure characters are in campaign)
        if hasattr(self.campaign_manager, "save_campaign_data"):
            self.campaign_manager.save_campaign_data(campaign_id, campaign_data)

        # Build initial prompt with campaign_info + characters
        # The LLM will generate the opening narrative with all context
        initial_prompt = self.initializer.build_initial_prompt(campaign_info, character_payloads)

        # Update database status to 'active' BEFORE creating async task
        # This ensures the endpoint can broadcast after this method returns but before task starts streaming
        with db_manager.get_sync_session() as db:
            session_row = db.get(CampaignSession, campaign_id)
            if session_row:
                session_row.campaign_status = "active"
                session_row.started_at = datetime.now(tz.utc)
                db.commit()
                logger.info(f"✅ Campaign {campaign_id} status updated to 'active'")

        # Trigger first turn generation asynchronously
        logger.info(f"🚀 Campaign {campaign_id} starting, generating first turn in background")
        asyncio.create_task(
            self._generate_first_turn_async(campaign_id, initial_prompt, campaign_info, character_payloads)
        )

        # Return immediately - client will receive narrative via WebSocket
        return {
            "success": True,
            "campaign_id": campaign_id,
            "campaign_info": campaign_info,
            "character_count": len(characters),
            "initializing": True,
            "message": "Campaign started successfully. Opening narrative is being generated..."
        }

    # Legacy method for backwards compatibility (redirects to auto_fill_campaign)
    async def generate_campaign(self, request: CampaignGenerateRequest) -> Dict[str, Any]:
        """Legacy method - redirects to auto_fill_campaign."""
        auto_fill_request = AutoFillCampaignRequest(style=request.style)
        return await self.auto_fill_campaign(auto_fill_request)
    
    def _get_next_campaign_id(self) -> str:
        """Generate the next campaign ID."""
        return self.campaign_manager.get_next_campaign_id()
    
    def _parse_game_style(self, style: Optional[str]) -> GameStyle:
        """Parse game style string to enum."""
        try:
            if style:
                return GameStyle[style.upper()]
            else:
                return GameStyle.BALANCED
        except (KeyError, AttributeError):
            return GameStyle.BALANCED

    def _persist_world_settings(
        self,
        campaign_id: str,
        world_settings: Dict[str, Any],
        max_player_seats: int,
    ) -> None:
        """Store wizard metadata so we can build campaigns from seats later."""
        metadata = {
            "campaign_id": campaign_id,
            "world_settings": world_settings or {},
            "max_player_seats": max_player_seats,
            "status": "setup",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.campaign_manager.storage.save_metadata(campaign_id, metadata)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save world metadata for %s: %s", campaign_id, exc)

    def _ensure_room_structure(
        self,
        campaign_id: str,
        *,
        owner_user_id: Optional[str],
        owner_email: Optional[str],
        max_player_seats: int,
    ) -> None:
        """Provision campaign_sessions row + seats for the new campaign."""
        try:
            db_manager.initialize()
            with db_manager.get_sync_session() as session:
                campaign = session.get(CampaignSession, campaign_id)
                if not campaign:
                    campaign = CampaignSession(session_id=campaign_id)
                    session.add(campaign)

                if owner_user_id:
                    campaign.owner_user_id = owner_user_id
                if owner_email:
                    campaign.owner_email = owner_email
                    campaign.normalized_owner_email = owner_email.lower()

                campaign.max_player_seats = max_player_seats
                campaign.room_status = campaign.room_status or "waiting_for_dm"
                campaign.campaign_status = campaign.campaign_status or "setup"

                seat_exists = session.execute(
                    select(RoomSeat.seat_id).where(RoomSeat.campaign_id == campaign_id)
                ).first()

                if seat_exists:
                    session.commit()
                    return

                room_service = RoomService(session)
                room_service.create_room(
                    campaign_id=campaign_id,
                    owner_user_id=owner_user_id or "",
                    max_player_seats=max_player_seats,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to set up room seats for %s: %s", campaign_id, exc)

    def _load_world_settings(self, campaign_id: str) -> Dict[str, Any]:
        """Load stored wizard metadata."""
        try:
            metadata = self.campaign_manager.storage.load_metadata(campaign_id)
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(metadata, dict):
            return {}
        return metadata.get("world_settings") or {}
