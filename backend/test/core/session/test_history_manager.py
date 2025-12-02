from gaia_private.session.history_manager import HistoryManager


def test_user_message_defaults_character_name_to_player():
    manager = HistoryManager()

    manager.add_message("user", "Hello there")

    stored = manager.get_full_history()[-1]
    assert stored["character_name"] == "Player"


def test_user_message_preserves_trimmed_character_name():
    manager = HistoryManager()

    manager.add_message("user", "Acting as Grasha", character_name="  Grasha Ironhide  ")

    stored = manager.get_full_history()[-1]
    assert stored["character_name"] == "Grasha Ironhide"
