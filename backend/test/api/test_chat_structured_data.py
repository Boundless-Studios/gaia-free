"""Tests for chat structured data transformation."""

from gaia.api.routes.chat import transform_structured_data


def test_transform_structured_data_includes_combat_fields():
    """Ensure combat-specific fields are preserved for the frontend."""
    raw_data = {
        "narrative": "Battle rages on.",
        "turn": "Lyra acts",
        "combat_status": {
            "Lyra": {"hp": "10/28", "ap": "2/4", "status": []}
        },
        "combat_state": {"round": 3},
        "action_breakdown": [{"name": "Attack", "result": "Hit"}],
        "turn_resolution": {"next_combatant": "Gorak"},
    }

    structured = transform_structured_data(raw_data)

    assert structured.combat_status == raw_data["combat_status"]
    assert structured.combat_state == raw_data["combat_state"]
    assert structured.action_breakdown == raw_data["action_breakdown"]
    assert structured.turn_resolution == raw_data["turn_resolution"]


def test_transform_structured_data_null_combat_defaults():
    """Absent combat fields should remain None for downstream checks."""
    structured = transform_structured_data({})

    assert structured.combat_status is None
    assert structured.combat_state is None
    assert structured.action_breakdown is None
    assert structured.turn_resolution is None
