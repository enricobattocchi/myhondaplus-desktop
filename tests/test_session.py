"""Tests for application session orchestration."""

from myhondaplus_desktop.config import Settings
from myhondaplus_desktop.session import AppSession


class DummyStorage:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1


class DummyTokens:
    def __init__(self):
        self.access_token = ""
        self.refresh_token = ""
        self.is_expired = False


class DummyAPI:
    def __init__(self, storage):
        self.storage = storage
        self.tokens = DummyTokens()
        self.refresh_auth_calls = 0
        self.set_tokens_calls = []

    def refresh_auth(self):
        self.refresh_auth_calls += 1
        self.tokens.is_expired = False

    def set_tokens(self, **kwargs):
        self.set_tokens_calls.append(kwargs)


def test_restore_authenticated_session_without_access_token():
    session = AppSession(settings=Settings(), storage=DummyStorage(), api=DummyAPI(DummyStorage()))

    assert session.restore_authenticated_session() is False


def test_restore_authenticated_session_refreshes_expired_token():
    storage = DummyStorage()
    api = DummyAPI(storage)
    api.tokens.access_token = "access"
    api.tokens.refresh_token = "refresh"
    api.tokens.is_expired = True
    session = AppSession(settings=Settings(), storage=storage, api=api)

    assert session.restore_authenticated_session() is True
    assert api.refresh_auth_calls == 1


def test_restore_authenticated_session_returns_false_on_refresh_failure():
    storage = DummyStorage()
    api = DummyAPI(storage)
    api.tokens.access_token = "access"
    api.tokens.refresh_token = "refresh"
    api.tokens.is_expired = True

    def fail():
        raise RuntimeError("boom")

    api.refresh_auth = fail
    session = AppSession(settings=Settings(), storage=storage, api=api)

    assert session.restore_authenticated_session() is False


def test_apply_login_tokens_sets_user_id(monkeypatch):
    storage = DummyStorage()
    api = DummyAPI(storage)
    session = AppSession(settings=Settings(), storage=storage, api=api)
    monkeypatch.setattr("myhondaplus_desktop.session.HondaAuth.extract_user_id", lambda token: "user-123")

    session.apply_login_tokens({
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 7200,
    })

    assert api.set_tokens_calls == [{
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 7200,
        "user_id": "user-123",
    }]


def test_reset_clears_storage_and_replaces_api(monkeypatch):
    storage = DummyStorage()
    initial_api = DummyAPI(storage)
    created_apis = []

    def fake_honda_api(*, storage):
        api = DummyAPI(storage)
        created_apis.append(api)
        return api

    monkeypatch.setattr("myhondaplus_desktop.session.HondaAPI", fake_honda_api)
    session = AppSession(settings=Settings(), storage=storage, api=initial_api)

    new_api = session.reset()

    assert storage.clear_calls == 1
    assert new_api is created_apis[0]
    assert session.api is new_api


def test_save_settings_delegates_to_settings(monkeypatch):
    settings = Settings()
    calls = {"count": 0}

    monkeypatch.setattr(settings, "save", lambda: calls.update(count=calls["count"] + 1))
    session = AppSession(settings=settings, storage=DummyStorage(), api=DummyAPI(DummyStorage()))

    session.save_settings()

    assert calls["count"] == 1
