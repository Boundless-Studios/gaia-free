"""
Test script for preferences and campaign settings models

This script validates the model definitions and structure.
"""

import sys
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_model_imports():
    """Test that models can be imported successfully"""
    try:
        from db.src.models import DMPreferences, PlayerPreferences, CampaignSettings
        print("✓ Successfully imported all preference models")
        return True
    except ImportError as e:
        print(f"✗ Failed to import models: {e}")
        return False

def test_model_structure():
    """Test model structure and attributes"""
    from db.src.models import DMPreferences, PlayerPreferences, CampaignSettings

    # Test DMPreferences
    dm_attrs = ['preference_id', 'user_id', 'preferred_dm_model', 'preferred_npc_model',
                'preferred_combat_model', 'show_dice_rolls', 'auto_generate_portraits',
                'narration_style', 'default_difficulty', 'enable_critical_success',
                'enable_critical_failure', 'preferences_metadata']

    missing_dm = [attr for attr in dm_attrs if not hasattr(DMPreferences, attr)]
    if missing_dm:
        print(f"✗ DMPreferences missing attributes: {missing_dm}")
        return False
    print("✓ DMPreferences has all expected attributes")

    # Test PlayerPreferences
    player_attrs = ['preference_id', 'user_id', 'theme', 'font_size', 'show_animations',
                    'enable_audio', 'audio_volume', 'enable_background_music',
                    'enable_sound_effects', 'enable_turn_notifications',
                    'enable_combat_notifications', 'preferences_metadata']

    missing_player = [attr for attr in player_attrs if not hasattr(PlayerPreferences, attr)]
    if missing_player:
        print(f"✗ PlayerPreferences missing attributes: {missing_player}")
        return False
    print("✓ PlayerPreferences has all expected attributes")

    # Test CampaignSettings
    campaign_attrs = ['settings_id', 'campaign_id', 'tone', 'pace', 'difficulty',
                      'max_players', 'min_players', 'allow_pvp', 'dm_model',
                      'npc_model', 'combat_model', 'narration_model', 'allow_homebrew',
                      'use_milestone_leveling', 'starting_level', 'max_level',
                      'session_length_minutes', 'breaks_enabled', 'settings_metadata']

    missing_campaign = [attr for attr in campaign_attrs if not hasattr(CampaignSettings, attr)]
    if missing_campaign:
        print(f"✗ CampaignSettings missing attributes: {missing_campaign}")
        return False
    print("✓ CampaignSettings has all expected attributes")

    return True

def test_model_table_names():
    """Test that models have correct table names"""
    from db.src.models import DMPreferences, PlayerPreferences, CampaignSettings

    expected = {
        DMPreferences: 'dm_preferences',
        PlayerPreferences: 'player_preferences',
        CampaignSettings: 'campaign_settings'
    }

    for model, expected_name in expected.items():
        actual_name = model.__tablename__
        if actual_name != expected_name:
            print(f"✗ {model.__name__} has wrong table name: {actual_name} (expected {expected_name})")
            return False
        print(f"✓ {model.__name__} has correct table name: {actual_name}")

    return True

def test_model_schemas():
    """Test that models are in the correct schema"""
    from db.src.models import DMPreferences, PlayerPreferences, CampaignSettings

    models = [DMPreferences, PlayerPreferences, CampaignSettings]

    for model in models:
        schema = model.__table_args__[-1]['schema'] if isinstance(model.__table_args__, tuple) else model.__table_args__.get('schema')
        if schema != 'game':
            print(f"✗ {model.__name__} has wrong schema: {schema} (expected 'game')")
            return False
        print(f"✓ {model.__name__} is in the 'game' schema")

    return True

def main():
    """Run all tests"""
    print("Testing preferences and campaign settings models...\n")

    tests = [
        ("Model imports", test_model_imports),
        ("Model structure", test_model_structure),
        ("Table names", test_model_table_names),
        ("Schema names", test_model_schemas)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        result = test_func()
        results.append(result)

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
