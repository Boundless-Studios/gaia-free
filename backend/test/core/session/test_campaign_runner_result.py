from gaia_private.session.campaign_runner import CampaignRunner


def _make_runner() -> CampaignRunner:
    """Create a CampaignRunner instance without invoking __init__ for unit testing."""
    return CampaignRunner.__new__(CampaignRunner)


def test_create_campaign_result_preserves_streaming_answer() -> None:
    runner = _make_runner()
    structured_data = {
        "answer": "Narrative chunk\n\nPlayer response.",
        "turn": "",
        "turn_info": {},
    }

    result = runner.create_campaign_result(structured_data, "session-123", "Player response.")
    final_answer = result["structured_data"]["answer"]

    assert final_answer.startswith("Narrative chunk")
    assert final_answer.count("Player response.") == 1
    assert final_answer.endswith("\n")


def test_create_campaign_result_uses_player_response_when_missing_answer() -> None:
    runner = _make_runner()
    structured_data: dict = {"turn": ""}

    result = runner.create_campaign_result(structured_data, "session-123", "Player says hi.")
    final_answer = result["structured_data"]["answer"]

    assert final_answer.startswith("Player says hi.")
    assert final_answer.endswith("\n")
