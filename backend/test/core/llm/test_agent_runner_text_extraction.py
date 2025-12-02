import types

from gaia.infra.llm.agent_runner import AgentRunner


def _make_result(**attrs):
    """Helper to create a simple object with arbitrary attributes."""
    return types.SimpleNamespace(**attrs)


def test_extract_text_from_final_output_dict():
    result = _make_result(
        final_output={"text": "Greetings adventurer!"},
        new_items=None,
        messages=None,
    )

    assert AgentRunner.extract_text_response(result) == "Greetings adventurer!"


def test_extract_text_from_new_items_via_raw_item():
    class DummyItem:
        def __init__(self, text: str):
            self.raw_item = {"content": [{"text": text}]}

    result = _make_result(
        final_output=None,
        new_items=[DummyItem("The torches flicker ominously.")],
        messages=None,
    )

    assert AgentRunner.extract_text_response(result) == "The torches flicker ominously."


def test_extract_text_falls_back_to_messages():
    class DummyMessage:
        def __init__(self, text: str):
            self.content = [{"text": text}]

    result = _make_result(
        final_output=None,
        new_items=None,
        messages=[DummyMessage("You sense something lurking in the shadows.")],
    )

    assert AgentRunner.extract_text_response(result) == "You sense something lurking in the shadows."
