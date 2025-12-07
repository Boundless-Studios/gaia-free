"""Scene data model for narrative structure."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from gaia.models.character.enums import CharacterRole
from gaia.models.scene_participant import SceneParticipant


@dataclass
class SceneInfo:
    """Scene information for narrative structure.
    
    Fields are organized into two categories:
    - Creation fields: Set when scene is first created
    - Update fields: Modified as the scene progresses
    """
    
    # === Creation Fields (set once when scene is created) ===
    scene_id: str
    title: str
    description: str
    scene_type: str  # combat, exploration, social, puzzle, etc.
    objectives: List[str] = field(default_factory=list)  # Initial scene objectives
    participants: List[SceneParticipant] = field(default_factory=list)
    npcs_involved: List[str] = field(default_factory=list)  # NPCs present at scene start
    npcs_present: List[str] = field(default_factory=list)  # Current NPCs/creatures present
    pcs_present: List[str] = field(default_factory=list)  # Player character IDs present at scene start
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional scene metadata
    timestamp: datetime = field(default_factory=datetime.now)
      
    # === Update Fields (modified as scene progresses) ===
    outcomes: List[str] = field(default_factory=list)  # What happened during the scene
    npcs_added: List[str] = field(default_factory=list)  # NPCs who joined during scene
    npcs_removed: List[str] = field(default_factory=list)  # NPCs who left during scene
    duration_turns: int = 0  # How many turns the scene lasted
    last_updated: Optional[datetime] = None

    # === Turn Order Fields (for non-combat scenes) ===
    turn_order: List[str] = field(default_factory=list)  # Ordered list of character IDs for turn rotation
    current_turn_index: int = 0  # Current position in the turn_order list

    # === Combat Fields (only used when scene_type is "combat") ===
    in_combat: bool = False  # Whether combat is currently active
    combat_data: Optional[Dict[str, Any]] = None  # Stores CombatInitiation data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        pcs_snapshot = self.pcs_present or self.snapshot_role_names(CharacterRole.PLAYER)
        npcs_snapshot = self.npcs_present or [
            participant.character_id or participant.display_name
            for participant in self.participants
            if participant.is_present and participant.role != CharacterRole.PLAYER
        ]

        return {
            # Creation fields
            "scene_id": self.scene_id,
            "title": self.title,
            "description": self.description,
            "scene_type": self.scene_type,
            "objectives": self.objectives,
            "participants": [participant.to_dict() for participant in self.participants],
            "npcs_involved": self.npcs_involved or npcs_snapshot,
            "npcs_present": npcs_snapshot,
            "pcs_present": pcs_snapshot,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            # Update fields
            "outcomes": self.outcomes,
            "npcs_added": self.npcs_added,
            "npcs_removed": self.npcs_removed,
            "duration_turns": self.duration_turns,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            # Turn order fields
            "turn_order": self.turn_order,
            "current_turn_index": self.current_turn_index,
            # Combat fields
            "in_combat": self.in_combat,
            "combat_data": self.combat_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SceneInfo':
        """Create from dictionary."""
        # Convert timestamp strings to datetime objects
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("last_updated"), str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        
        # Ensure all required fields have defaults
        data.setdefault("metadata", {})
        if not isinstance(data["metadata"], dict):
            data["metadata"] = {}
        data.setdefault("npcs_added", [])
        data.setdefault("npcs_removed", [])
        data.setdefault("duration_turns", 0)
        data.setdefault("last_updated", None)
        data.setdefault("turn_order", [])
        data.setdefault("current_turn_index", 0)
        data.setdefault("in_combat", False)
        data.setdefault("combat_data", None)

        # Remove deprecated fields if present
        data.pop("objectives_completed", None)
        data.pop("objectives_added", None)
        data.pop("description_updates", None)
        data.pop("completion_status", None)
        data.pop("entity_display_names", None)
        legacy_location_id = data.pop("location_id", None)
        legacy_location_description = data.pop("location_description", None)
        legacy_notes = data.pop("narrative_notes", None)

        # Preserve legacy location/notes data inside metadata if present
        if legacy_location_id:
            location_meta = data["metadata"].get("location")
            if not location_meta:
                location_meta = {}
                data["metadata"]["location"] = location_meta
            if isinstance(location_meta, dict):
                location_meta.setdefault("id", legacy_location_id)
                if legacy_location_description and "description" not in location_meta:
                    location_meta["description"] = legacy_location_description
        if legacy_notes and "narrative_notes" not in data["metadata"]:
            data["metadata"]["narrative_notes"] = legacy_notes
        participants_raw = data.get("participants", []) or []
        if participants_raw and isinstance(participants_raw, list):
            parsed_participants = []
            for participant in participants_raw:
                if isinstance(participant, SceneParticipant):
                    parsed_participants.append(participant)
                elif isinstance(participant, dict):
                    parsed_participants.append(SceneParticipant.from_dict(participant))
            data["participants"] = parsed_participants
        else:
            data["participants"] = []

        data.setdefault("npcs_present", [])
        data.setdefault("pcs_present", [])

        # Backfill legacy presence fields from participants when absent.
        if data["participants"]:
            pcs_snapshot = [
                participant.character_id or participant.display_name
                for participant in data["participants"]
                if participant.is_present and participant.role == CharacterRole.PLAYER
            ]
            npcs_snapshot = [
                participant.character_id or participant.display_name
                for participant in data["participants"]
                if participant.is_present and participant.role != CharacterRole.PLAYER
            ]

            if not data.get("pcs_present"):
                data["pcs_present"] = pcs_snapshot
            if not data.get("npcs_present"):
                data["npcs_present"] = npcs_snapshot
            if not data.get("npcs_involved"):
                data["npcs_involved"] = npcs_snapshot

        return cls(**data)

    def snapshot_role_names(self, role: CharacterRole) -> List[str]:
        """Return identifiers for participants in the given role who are present."""
        if not self.participants:
            return []
        return [
            participant.character_id or participant.display_name
            for participant in self.participants
            if participant.is_present and participant.role == role
        ]

    def start_combat(self, combat_initiation_data: Dict[str, Any]):
        """Mark scene as in combat and store combat data.

        Args:
            combat_initiation_data: Data from CombatInitiation model
        """
        self.in_combat = True
        self.combat_data = combat_initiation_data
        self.last_updated = datetime.now()

    def end_combat(self):
        """Mark combat as ended but keep combat data for history."""
        self.in_combat = False
        self.last_updated = datetime.now()

    def to_agent_context(self) -> str:
        """Generate concise scene representation for agent context.

        Returns a formatted string with key scene information for LLM agents,
        including title, objectives, combat status, and participants.

        Returns:
            Formatted scene context string
        """
        context_parts = []

        # Scene title and type
        if self.title:
            type_suffix = f" ({self.scene_type})" if self.scene_type else ""
            context_parts.append(f"Scene: {self.title}{type_suffix}")

        # Current objectives
        if self.objectives:
            context_parts.append(f"Objectives: {'; '.join(self.objectives)}")

        # Location (from metadata)
        location_meta = self.metadata.get("location") if isinstance(self.metadata, dict) else None
        if location_meta:
            location_text = None
            if isinstance(location_meta, dict):
                location_text = location_meta.get("description") or location_meta.get("id")
            else:
                location_text = str(location_meta)
            if location_text:
                context_parts.append(f"Location: {location_text}")

        # Combat status
        if self.in_combat:
            context_parts.append("Status: In Combat")
            if self.combat_data:
                round_num = self.combat_data.get('round_number', 1)
                context_parts.append(f"Combat Round: {round_num}")

        # NPCs present (use display names from participants)
        npc_display_names = []
        npc_ids_from_metadata = self.metadata.get('npc_display_names', {}) if self.metadata else {}

        for participant in self.participants:
            if participant.is_present and participant.role != CharacterRole.PLAYER:
                npc_display_names.append(participant.display_name or participant.character_id)

        # Fall back to npcs_present if no participant data
        if not npc_display_names:
            # Compute dynamic list from npcs_involved + npcs_added - npcs_removed
            base = list(self.npcs_involved or [])
            added = list(self.npcs_added or [])
            removed = set(self.npcs_removed or [])
            active_npcs = [n for n in base + added if n and n not in removed]

            # Use npcs_present if available, otherwise use computed list
            npc_ids = self.npcs_present if self.npcs_present else active_npcs

            for npc_id in npc_ids:
                # Try to get display name from metadata
                display = npc_ids_from_metadata.get(npc_id)
                if not display and isinstance(npc_id, str):
                    # Convert IDs to friendly names (e.g., "npc:guard_captain" -> "Guard Captain")
                    display = npc_id
                    if display.lower().startswith(("npc:", "npc_profile:")):
                        display = display.split(":", 1)[1]
                    display = display.replace("_", " ").title()
                if display:
                    npc_display_names.append(display)

        if npc_display_names:
            context_parts.append(f"NPCs Present: {', '.join(npc_display_names)}")

        # PCs present
        if self.pcs_present:
            context_parts.append(f"PCs Present: {', '.join(self.pcs_present)}")

        # Recent outcomes (last 2 for context)
        if self.outcomes:
            recent_outcomes = self.outcomes[-2:]
            context_parts.append(f"Recent Events: {'; '.join(recent_outcomes)}")

        return "\n".join(context_parts) if context_parts else "Scene context unavailable"
