from gaia_private.agents.generators.character_generator import (
    AbilityScores,
    CharacterGeneratorOutput,
)


def _base_payload(**overrides):
    payload = {
        "name": "Valid Name",
        "character_class": "Fighter",
        "race": "Human",
        "level": 1,
        "description": "Placeholder description",
        "backstory": "Placeholder backstory",
        "stats": AbilityScores(
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=12,
            wisdom=10,
            charisma=8,
        ),
        "alignment": "Neutral Good",
        "background": "Soldier",
    }
    payload.update(overrides)
    return payload


def test_character_name_is_sanitized():
    result = CharacterGeneratorOutput(**_base_payload(name=" ,  Kyra  ,"))
    assert result.name == "Kyra"


def test_invalid_character_name_uses_placeholder():
    result = CharacterGeneratorOutput(**_base_payload(name=",,,"))
    assert result.name == "Unnamed Human Fighter"
