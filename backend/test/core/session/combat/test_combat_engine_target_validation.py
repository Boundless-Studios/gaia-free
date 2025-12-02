"""Tests for combat engine target validation logic."""

import pytest
import sys
from pathlib import Path

# Add src to path to avoid circular imports
sys.path.insert(0, str(Path(__file__).parent / "../../../../src"))

# Import directly from modules to avoid __init__.py circular imports
from gaia.mechanics.combat.combat_engine import CombatEngine
from gaia.mechanics.combat.combat_action_results import InvalidTargetActionResult
from gaia.models.combat.persistence.combat_session import CombatSession
from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia.models.combat.mechanics.action_points import ActionPointState
from gaia.models.combat.mechanics.enums import CombatStatus


def create_test_session():
    """Create a test combat session with sample combatants."""
    session = CombatSession(
        session_id="test_validation_001",
        scene_id="test_scene",
        status=CombatStatus.IN_PROGRESS,
        round_number=1,
        turn_order=["fighter", "goblin", "wizard"],
        current_turn_index=0
    )

    session.combatants = {
        "fighter": CombatantState(
            character_id="fighter",
            name="Fighter",
            initiative=15,
            hp=25,
            max_hp=25,
            ac=16,
            level=3,
            is_npc=False,
            is_conscious=True,
            action_points=ActionPointState(max_ap=3, current_ap=3)
        ),
        "goblin": CombatantState(
            character_id="goblin",
            name="Goblin",
            initiative=12,
            hp=7,
            max_hp=7,
            ac=13,
            level=1,
            is_npc=True,
            is_conscious=True,
            action_points=ActionPointState(max_ap=3, current_ap=3)
        ),
        "wizard": CombatantState(
            character_id="wizard",
            name="Wizard",
            initiative=10,
            hp=18,
            max_hp=18,
            ac=12,
            level=3,
            is_npc=False,
            is_conscious=True,
            action_points=ActionPointState(max_ap=3, current_ap=3)
        ),
    }

    return session


class TestTargetValidation:
    """Test combat engine target validation."""

    def test_validate_target_success(self):
        """Test that valid targets pass validation."""
        engine = CombatEngine()
        session = create_test_session()

        target = engine._validate_target(session, "goblin")

        assert target is not None
        assert target.name == "Goblin"
        assert target.character_id == "goblin"

    def test_validate_target_not_found(self):
        """Test that missing targets raise helpful errors."""
        engine = CombatEngine()
        session = create_test_session()

        with pytest.raises(ValueError) as exc_info:
            engine._validate_target(session, "dragon")

        error_msg = str(exc_info.value)
        assert "'dragon' not in combat" in error_msg
        assert "Fighter" in error_msg  # Shows available targets
        assert "Goblin" in error_msg
        assert "Wizard" in error_msg

    def test_validate_target_unconscious(self):
        """Test that unconscious targets can't be targeted by default."""
        engine = CombatEngine()
        session = create_test_session()

        # Make goblin unconscious
        session.combatants["goblin"].is_conscious = False

        with pytest.raises(ValueError) as exc_info:
            engine._validate_target(session, "goblin")

        assert "unconscious" in str(exc_info.value).lower()

    def test_validate_target_defeated(self):
        """Test that defeated targets (HP <= 0) can't be targeted."""
        engine = CombatEngine()
        session = create_test_session()

        # Defeat the goblin
        session.combatants["goblin"].hp = 0

        with pytest.raises(ValueError) as exc_info:
            engine._validate_target(session, "goblin")

        assert "defeated" in str(exc_info.value).lower()

    def test_validate_target_unconscious_allowed(self):
        """Test that healing can target unconscious allies."""
        engine = CombatEngine()
        session = create_test_session()

        # Make fighter unconscious
        session.combatants["fighter"].is_conscious = False

        # Should succeed with allow_unconscious=True
        target = engine._validate_target(session, "fighter", allow_unconscious=True)

        assert target is not None
        assert target.name == "Fighter"
        assert not target.is_conscious

    def test_invalid_target_returns_proper_result(self):
        """Test that invalid targets return InvalidTargetActionResult."""
        engine = CombatEngine()
        session = create_test_session()
        actor = session.combatants["fighter"]

        result = engine._handle_basic_attack(session, actor, "dragon")

        # Check by class name instead of isinstance (handles import path differences)
        assert result.__class__.__name__ == "InvalidTargetActionResult"
        assert result.success == False
        assert "invalid_target" in result.effects_applied
        assert "'dragon' not in combat" in result.description
        assert result.damage is None
        assert result.attack_roll is None

    def test_attack_unconscious_target_fails(self):
        """Test that attacking unconscious targets returns InvalidTargetActionResult."""
        engine = CombatEngine()
        session = create_test_session()
        actor = session.combatants["fighter"]

        # Make goblin unconscious
        session.combatants["goblin"].is_conscious = False

        result = engine._handle_basic_attack(session, actor, "goblin")

        # Check by class name instead of isinstance (handles import path differences)
        assert result.__class__.__name__ == "InvalidTargetActionResult"
        assert result.success == False
        assert "invalid_target" in result.effects_applied
        assert "unconscious" in result.description.lower()

    def test_attack_defeated_target_fails(self):
        """Test that attacking defeated targets returns InvalidTargetActionResult."""
        engine = CombatEngine()
        session = create_test_session()
        actor = session.combatants["fighter"]

        # Defeat the goblin
        session.combatants["goblin"].hp = 0

        result = engine._handle_basic_attack(session, actor, "goblin")

        # Check by class name instead of isinstance (handles import path differences)
        assert result.__class__.__name__ == "InvalidTargetActionResult"
        assert result.success == False
        assert "invalid_target" in result.effects_applied
        assert "defeated" in result.description.lower()

    def test_spell_attack_uses_validation(self):
        """Test that spell attacks also use target validation."""
        engine = CombatEngine()
        session = create_test_session()
        actor = session.combatants["wizard"]

        result = engine._handle_simple_spell(session, actor, "dragon")

        # Check by class name instead of isinstance (handles import path differences)
        assert result.__class__.__name__ == "InvalidTargetActionResult"
        assert result.success == False
        assert "'dragon' not in combat" in result.description
