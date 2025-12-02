import pytest

from gaia_private.session.session_registry import SessionRegistry


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPAIGN_STORAGE_PATH", str(tmp_path))
    monkeypatch.delenv("ENVIRONMENT_NAME", raising=False)
    monkeypatch.setenv("SESSION_REGISTRY_DISABLE_DB", "1")
    reg = SessionRegistry()
    return reg


def test_create_and_consume_invite_token(registry):
    registry.register_session(
        "campaign_xyz",
        owner_user_id="owner-123",
        title="Test Campaign",
        owner_email="owner@example.com",
    )

    invite = registry.create_invite_token(
        "campaign_xyz",
        created_by="owner-123",
        created_by_email="owner@example.com",
        expires_in_minutes=60,
        multi_use=False,
    )

    assert "token" in invite
    token = invite["token"]
    assert registry._data["invite_tokens"][token]["created_by_email"] == "owner@example.com"

    consume_result = registry.consume_invite_token(
        token,
        user_id="player-456",
        user_email="player@example.com",
    )
    assert consume_result is not None
    assert consume_result["session_id"] == "campaign_xyz"

    metadata = registry.get_metadata("campaign_xyz")
    assert metadata is not None
    assert "player-456" in metadata.get("member_user_ids", [])
    assert "player@example.com" in metadata.get("member_emails", [])

    sessions_for_email = registry.get_sessions_for_user(user_email="player@example.com")
    assert "campaign_xyz" in sessions_for_email

    # Token should be consumed after first use
    assert (
        registry.consume_invite_token(
            token,
            user_id="another-user",
            user_email="another@example.com",
        )
        is None
    )


def test_invalidate_invites(registry):
    registry.register_session(
        "campaign_abc",
        owner_user_id="owner-1",
        owner_email="owner@example.com",
    )

    token_one = registry.create_invite_token(
        "campaign_abc",
        created_by="owner-1",
        created_by_email="owner@example.com",
    )["token"]
    token_two = registry.create_invite_token(
        "campaign_abc",
        created_by="owner-1",
        created_by_email="owner@example.com",
    )["token"]

    assert token_one != token_two

    removed = registry.invalidate_invites("campaign_abc")
    assert removed == 2

    # Tokens should no longer be valid
    assert (
        registry.consume_invite_token(
            token_one,
            user_id="player",
            user_email="player@example.com",
        )
        is None
    )
    assert (
        registry.consume_invite_token(
            token_two,
            user_id="player",
            user_email="player@example.com",
        )
        is None
    )


def test_authorization_checks(registry):
    assert not registry.is_authorized("missing-session", user_id="owner")

    registry.touch_session("campaign_open", user_id=None)
    assert registry.is_authorized("campaign_open", user_id=None)
    assert registry.is_authorized("campaign_open", user_id="any-user")

    registry.register_session(
        "campaign_secure",
        owner_user_id="owner-123",
        owner_email="owner@example.com",
    )

    assert not registry.is_authorized("campaign_secure", user_id="owner-123")
    assert registry.is_authorized("campaign_secure", user_email="owner@example.com")
    assert not registry.is_authorized("campaign_secure", user_id="intruder")
    assert not registry.is_authorized("campaign_secure", user_email="intruder@example.com")

    registry.touch_session(
        "campaign_secure",
        user_id="member-789",
        user_email="member@example.com",
    )

    assert not registry.is_authorized("campaign_secure", user_id="member-789")
    assert registry.is_authorized("campaign_secure", user_email="member@example.com")


def test_register_session_invokes_db_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPAIGN_STORAGE_PATH", str(tmp_path))
    monkeypatch.delenv("ENVIRONMENT_NAME", raising=False)
    monkeypatch.setenv("SESSION_REGISTRY_DISABLE_DB", "1")

    call_args = {}

    def fake_persist(self, session_id, entry):
        call_args["session_id"] = session_id
        call_args["entry_owner"] = entry.get("owner_user_id")

    monkeypatch.setattr(SessionRegistry, "_persist_session_db", fake_persist, raising=False)

    registry = SessionRegistry()
    registry.register_session(
        "campaign_persist",
        owner_user_id="owner-xyz",
        title="Persisted Campaign",
        owner_email="owner@example.com",
    )

    assert call_args["session_id"] == "campaign_persist"
    assert call_args["entry_owner"] == "owner-xyz"
