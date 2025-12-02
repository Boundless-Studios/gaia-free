"""API routes for combat management."""
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from gaia.mechanics.combat.combat_state_manager import CombatStateManager
from gaia_private.models.combat.agent_io import AgentCombatResponse
from gaia.models.character.character_info import CharacterInfo
from gaia.models.combat import StatusEffect, StatusEffectType
from gaia.api.routes.internal import optional_auth


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/combat", tags=["combat"])

# Global combat state manager (would be dependency injected in production)
combat_manager = CombatStateManager()


# Request/Response models
class InitCombatRequest(BaseModel):
    """Request to initialize combat."""
    scene_id: str
    character_ids: List[str]
    battlefield_config: Optional[Dict[str, Any]] = None


class CombatActionRequest(BaseModel):
    """Request to perform a combat action."""
    session_id: str
    actor_id: str
    action_name: str
    target_id: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None


class ApplyEffectRequest(BaseModel):
    """Request to apply a status effect."""
    session_id: str
    target_id: str
    effect_type: str
    duration_rounds: int
    source: str
    description: str


class HealRequest(BaseModel):
    """Request to heal a combatant."""
    session_id: str
    target_id: str
    amount: int


@router.post("/initialize")
async def initialize_combat(
    request: InitCombatRequest,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Initialize a new combat session.

    Args:
        request: Combat initialization parameters

    Returns:
        Combat session details
    """
    try:
        # TODO: Load actual character data from character manager
        # For now, create placeholder characters
        characters = []
        for char_id in request.character_ids:
            char = CharacterInfo(
                character_id=char_id,
                name=f"Character_{char_id}",
                character_class="Fighter",
                level=5,
                hit_points_current=30,
                hit_points_max=30,
                armor_class=15
            )
            characters.append(char)

        # Initialize combat
        session = combat_manager.initialize_combat(
            scene_id=request.scene_id,
            characters=characters,
            battlefield_config=request.battlefield_config
        )

        return {
            "success": True,
            "session_id": session.session_id,
            "combat_state": session.get_summary()
        }

    except Exception as e:
        logger.error(f"Failed to initialize combat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current/{scene_id}")
async def get_current_combat(
    scene_id: str,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Get the current combat session for a scene.

    Args:
        scene_id: Scene ID

    Returns:
        Current combat state or None
    """
    session = combat_manager.get_active_session_for_scene(scene_id)

    if not session:
        return {"active": False, "message": "No active combat for this scene"}

    return {
        "active": True,
        "session_id": session.session_id,
        "combat_state": session.to_dict()
    }


@router.get("/session/{session_id}")
async def get_combat_session(
    session_id: str,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Get a specific combat session.

    Args:
        session_id: Combat session ID

    Returns:
        Combat session data
    """
    session = combat_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Combat session not found")

    return session.to_dict()


@router.get("/turn-order/{session_id}")
async def get_turn_order(
    session_id: str,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Get the turn order for a combat session.

    Args:
        session_id: Combat session ID

    Returns:
        Turn order information
    """
    session = combat_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Combat session not found")

    return {
        "round": session.round_number,
        "current_turn": session.resolve_current_character(),
        "turn_order": [
            {
                "character_id": cid,
                "name": session.combatants[cid].name,
                "initiative": session.combatants[cid].initiative,
                "hp": f"{session.combatants[cid].hp}/{session.combatants[cid].max_hp}",
                "conscious": session.combatants[cid].is_conscious,
                "active": session.combatants[cid].can_act(),
                "has_taken_turn": session.combatants[cid].has_taken_turn
            }
            for cid in session.turn_order
        ]
    }


@router.get("/combatant/{session_id}/{character_id}")
async def get_combatant_state(
    session_id: str,
    character_id: str,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Get a specific combatant's state.

    Args:
        session_id: Combat session ID
        character_id: Character ID

    Returns:
        Combatant state
    """
    session = combat_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Combat session not found")

    combatant = session.combatants.get(character_id)

    if not combatant:
        raise HTTPException(status_code=404, detail="Combatant not found")

    return combatant.to_dict()


@router.post("/action")
async def perform_combat_action(
    request: CombatActionRequest,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Perform a combat action.

    Args:
        request: Combat action parameters

    Returns:
        Action result
    """
    try:
        kwargs = request.additional_params or {}

        result = combat_manager.process_action(
            session_id=request.session_id,
            actor_id=request.actor_id,
            action_name=request.action_name,
            target_id=request.target_id,
            **kwargs
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        logger.error(f"Failed to perform combat action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-actions/{session_id}/{character_id}")
async def get_available_actions(
    session_id: str,
    character_id: str,
    current_user = optional_auth()
) -> List[Dict[str, Any]]:
    """
    Get available actions for a character.

    Args:
        session_id: Combat session ID
        character_id: Character ID

    Returns:
        List of available actions
    """
    actions = combat_manager.get_available_actions(session_id, character_id)
    return actions




@router.post("/apply-effect")
async def apply_status_effect(
    request: ApplyEffectRequest,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Apply a status effect to a combatant.

    Args:
        request: Effect application parameters

    Returns:
        Success status
    """
    try:
        # Map string to enum
        effect_type = StatusEffectType[request.effect_type.upper()]

        effect = StatusEffect(
            effect_type=effect_type,
            duration_rounds=request.duration_rounds,
            source=request.source,
            description=request.description
        )

        success = combat_manager.apply_status_effect(
            request.session_id,
            request.target_id,
            effect
        )

        return {"success": success}

    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid effect type: {request.effect_type}")
    except Exception as e:
        logger.error(f"Failed to apply status effect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heal")
async def heal_combatant(
    request: HealRequest,
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    Heal a combatant.

    Args:
        request: Healing parameters

    Returns:
        Amount healed
    """
    healed = combat_manager.heal_combatant(
        request.session_id,
        request.target_id,
        request.amount
    )

    return {"healed": healed}


@router.post("/end/{session_id}")
async def end_combat(
    session_id: str,
    reason: str = "manual",
    current_user = optional_auth()
) -> Dict[str, Any]:
    """
    End a combat session.

    Args:
        session_id: Combat session ID
        reason: Reason for ending

    Returns:
        Combat summary
    """
    summary = combat_manager.end_combat(session_id, reason)

    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])

    return summary
