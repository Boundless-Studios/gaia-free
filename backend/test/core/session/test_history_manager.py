from gaia_private.session.history_manager import (
    ConversationHistoryManager,
    HistoryManager,
)


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


def test_history_manager_recent_user_messages_respects_limit_and_exclude():
    manager = HistoryManager()

    for message in ["first", "second", "third", "fourth", "fifth", "sixth"]:
        manager.add_message("user", message)
    manager.add_message("assistant", "narration")

    recent = manager.get_recent_user_messages(exclude="sixth", limit=3, lookback=10)

    assert recent == ["third", "fourth", "fifth"]


def test_conversation_history_recent_user_messages_uses_full_history_slice():
    manager = ConversationHistoryManager()

    manager.add_message("assistant", "setup")
    manager.add_message("user", "alpha")
    manager.add_message("user", "beta")
    manager.add_message("user", "gamma")

    recent = manager.get_recent_user_messages(exclude="gamma", limit=2, lookback=2)

    assert recent == ["beta"]
